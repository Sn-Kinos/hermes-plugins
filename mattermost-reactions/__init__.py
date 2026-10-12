"""Discord-style processing reactions for Mattermost.

The Discord adapter marks the triggering message 👀 while the agent works and
swaps it for ✅ / ❌ when the turn ends.  The Mattermost adapter has no
reaction code at all, so the bot gives no sign it picked a post up until the
reply lands.  This plugin adds the same lifecycle to ``MattermostAdapter``::

    on_processing_start     ->  + :eyes:
    on_processing_complete  ->  - :eyes:, + :white_check_mark: / :x:
                                (CANCELLED: just - :eyes:)

Mattermost reactions are keyed by emoji *name* (shortcode), not the unicode
glyph, over REST:

    POST   /api/v4/reactions                                  {user_id, post_id, emoji_name}
    DELETE /api/v4/users/{user_id}/posts/{post_id}/reactions/{emoji_name}

Both go through the adapter's own ``_api`` helper (its session, auth and path
guard).  Reactions are cosmetic: every call is best-effort and never raises
into the message flow.

If upstream ever ships its own Mattermost lifecycle hooks, the class is left
alone (see ``_patch_adapter_class``) so the two never double-react.

Like the Discord adapter, the Mattermost platform is a directory plugin loaded
once per profile under its own module name, so classes are found by scanning
``sys.modules`` and ``PlatformRegistry.register`` is hooked for late arrivals.

On/off is per profile, matching Discord's ``reactions`` flag:
``MATTERMOST_REACTIONS`` env → ``mattermost.reactions`` (YAML) → on.

Settings (``plugins.entries.mattermost-reactions.settings``, read per call):

  ack    "eyes"               while the agent works
  ok     "white_check_mark"   turn succeeded
  fail   "x"                  turn failed
"""

from __future__ import annotations

import contextlib
import logging

logger = logging.getLogger(__name__)

_MARK = "_hermes_mattermost_reactions_patched"

_DEFAULTS = {
    "ack": "eyes",
    "ok": "white_check_mark",
    "fail": "x",
}

_ctx = None


def _setting(key: str) -> str:
    default = _DEFAULTS[key]
    if _ctx is None or not hasattr(_ctx, "get_config"):
        return default
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    # Accept ":eyes:" as well as "eyes" — the API wants the bare name.
    value = str(value or "").strip().strip(":")
    return value or default


def _reactions_enabled(adapter) -> bool:
    try:
        from gateway.platforms._shared import extra_or_secret

        extra = getattr(adapter.config, "extra", None)
        value = extra_or_secret(extra if isinstance(extra, dict) else None,
                                "reactions", "MATTERMOST_REACTIONS", "true")
    except Exception:
        return True
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"false", "0", "no", "off"}


def _ids(adapter, event):
    """(bot_user_id, post_id) or None when there is nothing to react to."""
    user_id = getattr(adapter, "_bot_user_id", "")
    post_id = getattr(event, "message_id", None)
    if not user_id or not post_id or getattr(adapter, "_session", None) is None:
        return None
    return user_id, str(post_id)


async def _add(adapter, event, emoji_name: str) -> bool:
    ids = _ids(adapter, event)
    if ids is None or not emoji_name:
        return False
    user_id, post_id = ids
    try:
        return bool(await adapter._api("POST", "reactions", {
            "user_id": user_id, "post_id": post_id, "emoji_name": emoji_name}))
    except Exception as e:
        logger.debug("mattermost-reactions: add %s failed: %s", emoji_name, e)
        return False


async def _remove(adapter, event, emoji_name: str) -> bool:
    ids = _ids(adapter, event)
    if ids is None or not emoji_name:
        return False
    user_id, post_id = ids
    try:
        return bool(await adapter._api(
            "DELETE", f"users/{user_id}/posts/{post_id}/reactions/{emoji_name}"))
    except Exception as e:
        logger.debug("mattermost-reactions: remove %s failed: %s", emoji_name, e)
        return False


async def on_processing_start(self, event) -> None:
    if _reactions_enabled(self):
        await _add(self, event, _setting("ack"))


async def on_processing_complete(self, event, outcome) -> None:
    if not _reactions_enabled(self):
        return
    await _remove(self, event, _setting("ack"))
    name = getattr(outcome, "name", str(outcome)).upper()
    emoji = {"SUCCESS": _setting("ok"), "FAILURE": _setting("fail")}.get(name)
    if emoji:
        await _add(self, event, emoji)


# ---------------------------------------------------------------------------
# seams: adapter class (already loaded, or via the registry's factory)
# ---------------------------------------------------------------------------

def _patch_adapter_class(cls) -> bool:
    if getattr(cls, _MARK, False):
        return False
    # Upstream grew its own hooks/reactions -> step aside rather than double-react.
    if any(name in cls.__dict__ for name in
           ("on_processing_start", "on_processing_complete", "_add_reaction")):
        logger.info("mattermost-reactions: %s already handles reactions; not patching",
                    cls.__qualname__)
        setattr(cls, _MARK, True)
        return False
    cls.on_processing_start = on_processing_start
    cls.on_processing_complete = on_processing_complete
    setattr(cls, _MARK, True)
    logger.debug("mattermost-reactions: patched %s.%s", cls.__module__, cls.__qualname__)
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
                logger.debug("mattermost-reactions: registry hook skipped", exc_info=True)
            return _orig_register(self, entry, **kwargs)

        PlatformRegistry.register = register
        setattr(PlatformRegistry, _MARK, True)


def register(ctx) -> None:  # noqa: ANN001 — hermes plugin contract
    global _ctx
    _ctx = ctx
    try:
        _patch_all()
        logger.info("mattermost-reactions: installed")
    except Exception as e:  # noqa: BLE001 — a bad seam must not break startup
        logger.warning("mattermost-reactions: not installed (no reactions): %s", e)
