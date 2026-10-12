"""Answer un-mentioned replies in Mattermost threads the bot is already part of.

Upstream ``MattermostAdapter`` gates every non-DM post through
``_apply_channel_gating``: unless the channel is in ``free_response_channels``
(or ``require_mention`` is off), a post without ``@<bot>`` is dropped.  It never
looks at ``root_id``, so even a reply under the bot's own post needs a mention.
Discord has a "threads don't need a mention" switch; Mattermost has none.

This plugin wraps ``MattermostAdapter._handle_ws_event``.  For a ``posted``
event that

  * is a thread reply (``root_id`` set) in a non-DM channel,
  * comes from a human (no ``from_bot`` prop, not a system post),
  * does not already mention this bot, and mentions nobody else,

it fetches the thread and decides whether this bot "owns" it:

  mode ``last_bot`` (default)  the most recent *bot* post in the thread is ours
                                (so with several bots in a channel, only the one
                                you were just talking to answers)
  mode ``participated``         we posted anywhere in the thread (root included)

If so, ``@<bot_username>`` is prepended to the post text and the event goes on
to the untouched upstream handler, whose own gating sees the mention, strips it
and dispatches normally (allowed_channels, allowed users, dedup, thread_id all
still apply).  Any failure falls through to upstream behaviour (= ignored).

Bot posts are never promoted, so peer agents still need explicit mentions to
talk to each other — the mention/no-mention ping-pong convention is unchanged.

Seams: adapter classes already in ``sys.modules`` + ``PlatformRegistry.register``
for late arrivals (the Mattermost platform is a directory plugin loaded once per
profile under its own module name).

Settings (``plugins.entries.mattermost-thread-followup.settings``, read per event):

  mode       "last_bot"   "last_bot" | "participated"
  channels   []           channel-id whitelist; empty = every channel
"""

from __future__ import annotations

import contextlib
import functools
import json
import logging
import re

logger = logging.getLogger(__name__)

_MARK = "_hermes_mattermost_thread_followup_patched"

_DEFAULTS = {
    "mode": "last_bot",
    "channels": [],
}

_ctx = None

# Mattermost usernames: letters, digits, '.', '-', '_'.  A trailing '.' is
# sentence punctuation, not part of the name.
_MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9_-]|[A-Za-z0-9])")


def _setting(key: str):
    default = _DEFAULTS[key]
    if _ctx is None or not hasattr(_ctx, "get_config"):
        return default
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    return default if value is None else value


def _channel_whitelist() -> set:
    raw = _setting("channels")
    if isinstance(raw, str):
        raw = raw.split(",")
    return {str(c).strip() for c in raw or [] if str(c).strip()}


def _is_bot_post(post: dict) -> bool:
    props = post.get("props") or {}
    return str(props.get("from_bot", "")).lower() == "true" or bool(props.get("from_webhook"))


def mentions(text: str) -> set:
    return {m.lower() for m in _MENTION_RE.findall(text or "")}


def owns_thread(posts: list, bot_user_id: str, exclude_post_id: str, mode: str) -> bool:
    """Pure decision over a thread's posts (any order)."""
    posts = [p for p in posts if p.get("id") != exclude_post_id and not p.get("type")
             and not p.get("delete_at")]
    if mode == "participated":
        return any(p.get("user_id") == bot_user_id for p in posts)
    bot_posts = [p for p in posts if p.get("user_id") == bot_user_id or _is_bot_post(p)]
    if not bot_posts:
        return False
    last = max(bot_posts, key=lambda p: p.get("create_at", 0))
    return last.get("user_id") == bot_user_id


async def _should_promote(adapter, post: dict, channel_type: str) -> bool:
    root_id = post.get("root_id")
    if not root_id or channel_type == "D" or post.get("type") or _is_bot_post(post):
        return False
    bot_id = getattr(adapter, "_bot_user_id", "")
    bot_name = (getattr(adapter, "_bot_username", "") or "").lower()
    if not bot_id or not bot_name or post.get("user_id") == bot_id:
        return False
    whitelist = _channel_whitelist()
    if whitelist and post.get("channel_id") not in whitelist:
        return False
    named = mentions(post.get("message", ""))
    if bot_name in named or f"@{bot_id}" in (post.get("message") or ""):
        return False  # already mentioned: upstream handles it
    if named:
        return False  # addressed to someone else (@miu, @channel, @jay …)
    thread = await adapter._api_get(f"posts/{root_id}/thread")
    if not thread or "posts" not in thread:
        return False
    mode = str(_setting("mode") or "last_bot").lower()
    return owns_thread(list(thread["posts"].values()), bot_id, post.get("id", ""), mode)


def _patch_adapter_class(cls) -> bool:
    if getattr(cls, _MARK, False):
        return False
    orig = getattr(cls, "_handle_ws_event", None)
    if orig is None:
        return False

    @functools.wraps(orig)
    async def _handle_ws_event(self, event, *args, **kwargs):
        try:
            if isinstance(event, dict) and event.get("event") == "posted":
                data = event.get("data") or {}
                post = json.loads(data.get("post") or "")
                if isinstance(post, dict) and await _should_promote(self, post, data.get("channel_type", "O")):
                    post["message"] = f"@{self._bot_username} " + (post.get("message") or "")
                    event = {**event, "data": {**data, "post": json.dumps(post)}}
                    logger.info("mattermost-thread-followup: answering un-mentioned reply %s in thread %s",
                                post.get("id"), post.get("root_id"))
        except Exception:
            logger.debug("mattermost-thread-followup: check skipped", exc_info=True)
        return await orig(self, event, *args, **kwargs)

    cls._handle_ws_event = _handle_ws_event
    setattr(cls, _MARK, True)
    logger.debug("mattermost-thread-followup: patched %s.%s", cls.__module__, cls.__qualname__)
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
                logger.debug("mattermost-thread-followup: registry hook skipped", exc_info=True)
            return _orig_register(self, entry, **kwargs)

        PlatformRegistry.register = register
        setattr(PlatformRegistry, _MARK, True)


def register(ctx) -> None:  # noqa: ANN001 — hermes plugin contract
    global _ctx
    _ctx = ctx
    try:
        _patch_all()
        logger.info("mattermost-thread-followup: installed")
    except Exception as e:  # noqa: BLE001 — a bad seam must not break startup
        logger.warning("mattermost-thread-followup: not installed (threads stay mention-gated): %s", e)
