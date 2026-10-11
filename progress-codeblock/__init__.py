"""Render the gateway's tool-progress bubble as one code block, last N entries only.

Upstream builds the editable progress bubble by ``"\\n".join``-ing every tool
line of the turn and re-sending the whole list on each edit.  On a long turn
that bubble grows into a wall of ``💻 실행 중 ...`` lines, and there is no
display setting to frame or bound it — only the ``terminal`` tool gets a fence,
and only per command on adapters with ``supports_code_blocks``.

This plugin changes the bubble, not the lines:

  window     — ``_progress_absorb`` trims the bubble's line buffer to the last
               N entries after each append, so every send/edit path (normal,
               flush, cancel-drain) already sees the window.  Trimming the list
               rather than the joined string keeps a multi-line entry whole.
  codeblock  — ``_send_progress_text`` / ``_edit_progress_message`` wrap the
               outgoing text in one fence.  The per-command terminal fence is
               turned off on those platforms (it would nest and break the
               block), and Discord's ``[label](<url>)`` previews are unwrapped
               to their label since markdown does not render inside a fence.

Only the editable progress bubble (``_ProgressEditState``) is touched: Slack
task cards, the final answer and every other message go out unchanged.

Settings live under ``plugins.entries.progress-codeblock.settings`` and are
read per call, so a config edit applies without a restart:

  codeblock      true                    wrap the bubble in a code block
  window         3                       entries kept; 0 = no limit
  show_hidden    true                    first line counts the dropped entries
  hidden_format  "… 외 {count}건"        that line's text
  platforms      [discord, mattermost]   platform keys this applies to

Every patch is individually try/except'd and idempotent — a seam upstream
renames degrades to the stock bubble and logs a warning, never breaks the
gateway.
"""

from __future__ import annotations

import functools
import logging
import re

logger = logging.getLogger(__name__)

_MARK = "_hermes_progress_codeblock_patched"
_HIDDEN_ATTR = "_progress_codeblock_hidden"

_DEFAULTS = {
    "codeblock": True,
    "window": 3,
    "show_hidden": True,
    "hidden_format": "… 외 {count}건",
    "platforms": ["discord", "mattermost"],
}

_FENCE = "```"
# A literal fence inside a line would close the block early; a zero-width
# space between the backticks keeps it visible but inert.
_FENCE_BREAK = "`​``"
# Discord's ``format_tool_preview``: ``[label](<url>)`` with ``\``-escaped label.
_MD_LINK_RE = re.compile(r"\[((?:\\.|[^\]\\])*)\]\(<[^>\s]*>\)")
_MD_ESCAPE_RE = re.compile(r"\\(.)")

_ctx = None  # PluginContext, for get_config


def _setting(key: str):
    default = _DEFAULTS[key]
    if _ctx is None or not hasattr(_ctx, "get_config"):
        return default
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    return default if value is None else value


def _platform_key(adapter) -> str:
    platform = getattr(adapter, "platform", None)
    return str(getattr(platform, "value", platform) or "").lower()


def _applies(adapter) -> bool:
    platforms = _setting("platforms")
    if isinstance(platforms, str):
        platforms = [platforms]
    try:
        wanted = {str(p).strip().lower() for p in platforms}
    except TypeError:
        return False
    return _platform_key(adapter) in wanted


def _window() -> int:
    try:
        return max(0, int(_setting("window")))
    except (TypeError, ValueError):
        return _DEFAULTS["window"]


def _codeblock() -> bool:
    return bool(_setting("codeblock"))


def _is_bubble(owner, st) -> bool:
    """True for the editable progress bubble only (not Slack task cards)."""
    state_cls = getattr(owner, "_ProgressEditState", None)
    return state_cls is not None and isinstance(st, state_cls)


def _render(st, text):
    """Window header + one fence around the bubble text."""
    if not isinstance(text, str) or not text.strip():
        return text
    hidden = getattr(st, _HIDDEN_ATTR, 0) if st.can_edit else 0
    lines = []
    if hidden and _setting("show_hidden"):
        try:
            lines.append(str(_setting("hidden_format")).format(count=hidden))
        except (KeyError, IndexError, ValueError):
            lines.append(_DEFAULTS["hidden_format"].format(count=hidden))
    if _codeblock():
        body = _MD_LINK_RE.sub(lambda m: _MD_ESCAPE_RE.sub(r"\1", m.group(1)), text)
        lines.append(body.replace(_FENCE, _FENCE_BREAK))
        return f"{_FENCE}\n" + "\n".join(lines) + f"\n{_FENCE}"
    return "\n".join(lines + [text])


# ---------------------------------------------------------------------------
# Patches on the TurnRunner class that owns the progress bubble
# ---------------------------------------------------------------------------

def _patch(owner, name: str, make_wrapper) -> None:
    original = vars(owner).get(name)
    if original is None:
        raise AttributeError(f"{owner.__name__}.{name} not found")
    if getattr(original, _MARK, False):
        return
    if isinstance(original, staticmethod):
        raise TypeError(f"{owner.__name__}.{name} became a staticmethod")
    wrapper = functools.wraps(original)(make_wrapper(original))
    setattr(wrapper, _MARK, True)
    setattr(owner, name, wrapper)


def _wrap_absorb(owner):
    def make(original):
        def wrapper(self, st, raw):
            result = original(self, st, raw)
            try:
                if _is_bubble(owner, st) and _applies(st.adapter):
                    window = _window()
                    lines = st.progress_lines
                    if window and len(lines) > window:
                        dropped = len(lines) - window
                        del lines[:dropped]
                        setattr(st, _HIDDEN_ATTR, getattr(st, _HIDDEN_ATTR, 0) + dropped)
            except Exception:
                logger.debug("progress-codeblock: window trim skipped", exc_info=True)
            return result
        return wrapper
    _patch(owner, "_progress_absorb", make)


def _wrap_reset(owner):
    def make(original):
        def wrapper(self, st):
            result = original(self, st)
            # The next bubble starts fresh, so does its dropped count.
            if hasattr(st, _HIDDEN_ATTR):
                setattr(st, _HIDDEN_ATTR, 0)
            return result
        return wrapper
    _patch(owner, "_reset_progress_bubble", make)


def _wrap_terminal_blocks(owner):
    def make(original):
        def wrapper(self, adapter, tool_name, args, emoji):
            try:
                if _codeblock() and _applies(adapter):
                    # A per-command fence would nest inside the bubble's fence.
                    return None, None
            except Exception:
                logger.debug("progress-codeblock: terminal fence check skipped", exc_info=True)
            return original(self, adapter, tool_name, args, emoji)
        return wrapper
    _patch(owner, "_progress_terminal_blocks", make)


def _wrap_send(owner):
    def make(original):
        async def wrapper(self, st, text):
            try:
                if _is_bubble(owner, st) and _applies(st.adapter):
                    text = _render(st, text)
            except Exception:
                logger.debug("progress-codeblock: send render skipped", exc_info=True)
            return await original(self, st, text)
        return wrapper
    _patch(owner, "_send_progress_text", make)


def _wrap_edit(owner):
    def make(original):
        async def wrapper(self, st, message_id, content):
            try:
                if _is_bubble(owner, st) and _applies(st.adapter):
                    content = _render(st, content)
            except Exception:
                logger.debug("progress-codeblock: edit render skipped", exc_info=True)
            return await original(self, st, message_id, content)
        return wrapper
    _patch(owner, "_edit_progress_message", make)


_PATCHES = (
    ("window", _wrap_absorb),
    ("window reset", _wrap_reset),
    ("terminal fence", _wrap_terminal_blocks),
    ("send", _wrap_send),
    ("edit", _wrap_edit),
)


def _owner():
    from gateway import run_turn_runner

    # Located by attribute rather than by class name so an upstream rename
    # degrades to a warning, not a crash.
    owners = [
        obj
        for obj in vars(run_turn_runner).values()
        if isinstance(obj, type) and "_progress_absorb" in vars(obj)
    ]
    if not owners:
        raise LookupError("no _progress_absorb owner in gateway.run_turn_runner")
    return owners[0]


def register(ctx) -> None:  # noqa: ANN001 — hermes plugin contract
    global _ctx
    _ctx = ctx
    try:
        owner = _owner()
    except Exception as e:  # noqa: BLE001 — a bad seam must not break startup
        logger.warning("progress-codeblock: progress bubble not found (left stock): %s", e)
        return
    applied, failed = [], []
    for label, patch in _PATCHES:
        try:
            patch(owner)
            applied.append(label)
        except Exception as e:  # noqa: BLE001
            failed.append(label)
            logger.warning("progress-codeblock: could not patch %s: %s", label, e)
    logger.info(
        "progress-codeblock: installed %s%s",
        ", ".join(applied) or "nothing",
        f" (failed: {', '.join(failed)})" if failed else "",
    )
