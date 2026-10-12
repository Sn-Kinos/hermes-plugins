"""Unwrap redirect-wrapped Mattermost permalinks on the way out to Mattermost.

Discord does not make ``mattermost://`` clickable, so the cron reports wrap
every permalink in an https redirect page that swaps the scheme and opens the
desktop app::

    https://qr.kinos.co.kr/mm?q=https%3A%2F%2Fchat.sweech.io%2Fsherry%2Fpl%2F<id>

Inside Mattermost that detour is pure cost: the native permalink already opens
in-app (desktop, web and mobile), while the redirect pops a browser tab first
and can dead-end on mobile.  One cron run delivers the *same* text to Discord
and Mattermost (``deliver: discord:…,mattermost:…``), so the prompt cannot pick
a per-platform link form.  This plugin rewrites at the Mattermost egress
instead, leaving Discord untouched:

  * ``<prefix>?q=<urlencoded https URL>``  ->  the decoded https URL
  * ``mattermost://host/...``             ->  ``https://host/...``

Seams (both every-profile, both idempotent):

  1. ``MattermostAdapter.format_message`` — every live send/edit path
     (``send``, ``edit_message``) already routes text through it.
  2. the registry entry's ``standalone_sender_fn`` — out-of-process cron
     delivery posts over REST and never calls ``format_message``.

Like the Discord adapter, the Mattermost platform is a directory plugin loaded
once per profile under its own module name, so classes are found by scanning
``sys.modules`` and ``PlatformRegistry.register`` is hooked for late arrivals.

Settings (``plugins.entries.mattermost-direct-links.settings``, read per call):

  prefixes   ["https://qr.kinos.co.kr/mm"]   redirect pages to unwrap
  scheme     true                            also rewrite mattermost:// -> https://
"""

from __future__ import annotations

import contextlib
import functools
import logging
import re
import urllib.parse

logger = logging.getLogger(__name__)

_MARK = "_hermes_mattermost_direct_links_patched"

_DEFAULTS = {
    "prefixes": ["https://qr.kinos.co.kr/mm"],
    "scheme": True,
}

_ctx = None


def _setting(key: str):
    default = _DEFAULTS[key]
    if _ctx is None or not hasattr(_ctx, "get_config"):
        return default
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    return default if value is None else value


# The q value is percent-encoded, so it never contains whitespace or markdown
# delimiters; stop at the first one so ``(link)`` / ``<link>`` survive intact.
_Q_TAIL = r"/?\?(?:[^\s()<>\[\]]*?&)?q=([^\s()<>\[\]&]+)"
_SCHEME_RE = re.compile(r"mattermost://(?=[A-Za-z0-9.-]+/)")


def _prefix_res():
    prefixes = _setting("prefixes")
    if isinstance(prefixes, str):
        prefixes = [p.strip() for p in prefixes.split(",") if p.strip()]
    return [re.compile(re.escape(str(p).rstrip("/")) + _Q_TAIL) for p in prefixes or []]


def _unwrap(match: re.Match) -> str:
    target = urllib.parse.unquote(match.group(1))
    # Only unwrap to a plain web URL; anything else stays as the original link.
    if not re.match(r"https?://[^\s]+$", target):
        return match.group(0)
    return target


def rewrite(text):
    if not isinstance(text, str) or not text:
        return text
    try:
        for rx in _prefix_res():
            text = rx.sub(_unwrap, text)
        if _setting("scheme"):
            text = _SCHEME_RE.sub("https://", text)
    except Exception:
        logger.debug("mattermost-direct-links: rewrite skipped", exc_info=True)
    return text


# ---------------------------------------------------------------------------
# 1. live adapter: format_message
# ---------------------------------------------------------------------------

def _patch_adapter_class(cls) -> bool:
    if getattr(cls, _MARK, False):
        return False
    orig = getattr(cls, "format_message", None)
    if orig is None:
        return False

    @functools.wraps(orig)
    def format_message(self, content, *args, **kwargs):
        return orig(self, rewrite(content), *args, **kwargs)

    cls.format_message = format_message
    setattr(cls, _MARK, True)
    logger.debug("mattermost-direct-links: patched %s.%s", cls.__module__, cls.__qualname__)
    return True


def _loaded_adapter_classes() -> list:
    import sys

    found = {}
    for name, module in list(sys.modules.items()):
        if module is None or "mattermost" not in name or not name.endswith(".adapter"):
            continue
        cls = getattr(module, "MattermostAdapter", None)
        if isinstance(cls, type):
            found.setdefault(id(cls), cls)
    return list(found.values())


# ---------------------------------------------------------------------------
# 2. registry entry: adapter factory + standalone (cron) sender
# ---------------------------------------------------------------------------

def _wrap_entry(entry) -> None:
    factory = getattr(entry, "adapter_factory", None)
    if isinstance(factory, type):
        _patch_adapter_class(factory)
    elif factory is not None and not getattr(factory, _MARK, False):
        def adapter_factory(config, _orig=factory):
            adapter = _orig(config)
            with contextlib.suppress(Exception):
                _patch_adapter_class(type(adapter))
            return adapter

        setattr(adapter_factory, _MARK, True)
        with contextlib.suppress(Exception):
            entry.adapter_factory = adapter_factory

    sender = getattr(entry, "standalone_sender_fn", None)
    if sender is not None and not getattr(sender, _MARK, False):
        async def standalone_sender_fn(pconfig, chat_id, message, *args, _orig=sender, **kwargs):
            return await _orig(pconfig, chat_id, rewrite(message), *args, **kwargs)

        setattr(standalone_sender_fn, _MARK, True)
        with contextlib.suppress(Exception):
            entry.standalone_sender_fn = standalone_sender_fn


def _registered_entries(registry) -> list:
    entries = []
    with contextlib.suppress(Exception):
        for scope_map in [registry._entries] + list(registry._scoped_entries.values()):
            entry = scope_map.get("mattermost")
            if entry is not None:
                entries.append(entry)
    return entries


def _patch_all() -> None:
    from gateway.platform_registry import PlatformRegistry, platform_registry

    for cls in _loaded_adapter_classes():
        _patch_adapter_class(cls)
    for entry in _registered_entries(platform_registry):
        _wrap_entry(entry)

    if not getattr(PlatformRegistry, _MARK, False):
        _orig_register = PlatformRegistry.register

        def register(self, entry, **kwargs):
            try:
                if getattr(entry, "name", "") == "mattermost":
                    _wrap_entry(entry)
            except Exception:
                logger.debug("mattermost-direct-links: registry hook skipped", exc_info=True)
            return _orig_register(self, entry, **kwargs)

        PlatformRegistry.register = register
        setattr(PlatformRegistry, _MARK, True)


def register(ctx) -> None:  # noqa: ANN001 — hermes plugin contract
    global _ctx
    _ctx = ctx
    try:
        _patch_all()
        logger.info("mattermost-direct-links: installed")
    except Exception as e:  # noqa: BLE001 — a bad seam must not break startup
        logger.warning("mattermost-direct-links: not installed (links left wrapped): %s", e)
