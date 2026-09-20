"""Korean localization layer for hermes-agent's hardcoded user-facing strings.

hermes-agent has no i18n infrastructure.  ``display.language`` exists but only
covers approval prompts and a few slash-command replies, its supported set is
``en, zh, ja, de, es, fr, tr, uk`` (no Korean), and its own docstring says it
does not affect agent responses, log lines or tool outputs.  Everything the
bots actually surface on Discord — the cron delivery wrapper, the
``💾 Self-improvement review`` notice, the ``⏰ Scheduling update`` tool label,
gateway lifecycle bumps — is a hardcoded English f-string.

This plugin translates those at four seams, all of which are module-global
lookups patched in place (so import order does not matter):

  1. ``agent.display._TOOL_VERBS``            — friendly tool labels
  2. ``cron.scheduler._deliver_result``       — cron delivery wrapper
  3. ``agent.background_review
         .summarize_background_review_actions`` — 💾 review action items
  4. ``DiscordAdapter.send``                  — fixed system notices, matched
                                                on anchored patterns only

It lives in ``~/.hermes/plugins-shared/`` (symlinked into each profile's
``plugins/``) rather than as a site-packages edit, for the same reason as
discord-add-reaction: the 0.19.0 upgrade on 2026-09-19 silently wiped an
in-tree patch, and a plugin survives that.

Every patch is individually try/except'd and idempotent — a seam that upstream
renames degrades to untranslated English and logs a warning, it never breaks
the gateway.

Config (``config.yaml``):
  cron.wrap_response_ko: true   # Korean cron header/footer (default false).
                                # Requires cron.wrap_response: false, else the
                                # English wrapper is applied on top.
"""

from __future__ import annotations

import logging

from .strings import (
    BG_ACTION_REWRITES,
    CRON_WRAP_KO,
    LABEL_KO,
    SEND_REWRITES,
    TOOL_VERBS_KO,
)

logger = logging.getLogger(__name__)

_MARK = "_hermes_korean_ui_patched"


def _apply(rewrites, text: str) -> str:
    """Return ``text`` with the first matching rewrite applied, else unchanged."""
    for pattern, replacement in rewrites:
        new, n = pattern.subn(replacement, text, count=1)
        if n:
            return new
    return text


# ---------------------------------------------------------------------------
# 1. Friendly tool labels — "Scheduling update" -> "일정 관리 update"
# ---------------------------------------------------------------------------

def _patch_tool_verbs() -> None:
    from agent import display

    if getattr(display, _MARK, False):
        return

    # Mutate in place: get_tool_verb()/build_tool_label() read the module-level
    # dict at call time, so this takes effect for already-imported callers.
    applied_verbs = set()
    for tool_name, verb_ko in TOOL_VERBS_KO.items():
        if tool_name in display._TOOL_VERBS:
            display._TOOL_VERBS[tool_name] = verb_ko
            applied_verbs.add(verb_ko)

    # Only report a tool whose Korean verb reached NO upstream name.  The
    # table carries both spellings of the entries upstream renamed in 0.21.x
    # (cronjob/cronjob_manage, todo/todo_list) so it works on either build —
    # the unused spelling is expected, not a gap worth warning about.
    unmatched = sorted(
        name
        for name, verb_ko in TOOL_VERBS_KO.items()
        if name not in display._TOOL_VERBS and verb_ko not in applied_verbs
    )
    if unmatched:
        logger.warning(
            "hermes-korean-ui: tool verbs not present upstream (left in English): %s",
            ", ".join(unmatched),
        )

    # Upstream renders "Searching the web for <query>" for these two.  Korean
    # puts the object first, so the English " for " connector reads as
    # "웹 검색 for foo" — drop it and fall back to a plain space.
    display._TOOL_VERBS_FOR_CONNECTOR = frozenset()

    setattr(display, _MARK, True)


# ---------------------------------------------------------------------------
# 2. Cron delivery wrapper
# ---------------------------------------------------------------------------

def _cron_wrap_ko_enabled() -> tuple[bool, bool]:
    """Return (korean_wrap_enabled, english_wrap_also_on)."""
    try:
        from hermes_cli.config import load_config

        cron_cfg = (load_config() or {}).get("cron") or {}
        return (
            bool(cron_cfg.get("wrap_response_ko", False)),
            bool(cron_cfg.get("wrap_response", True)),
        )
    except Exception:
        return (False, True)


def _patch_cron_delivery() -> None:
    import cron.scheduler as scheduler

    if getattr(scheduler, _MARK, False):
        return

    _orig_deliver_result = scheduler._deliver_result

    def _deliver_result(job, content, adapters=None, loop=None):
        try:
            ko_on, en_on = _cron_wrap_ko_enabled()
            if ko_on:
                if en_on:
                    # Upstream would add its own English header/footer around
                    # ours.  Bail out rather than emit a double wrapper.
                    logger.warning(
                        "hermes-korean-ui: cron.wrap_response_ko is on but "
                        "cron.wrap_response is also true — skipping the Korean "
                        "wrapper to avoid double-wrapping. Set "
                        "cron.wrap_response: false."
                    )
                else:
                    content = CRON_WRAP_KO.format(
                        task_name=job.get("name", job.get("id", "")),
                        job_id=job.get("id", ""),
                        content=content,
                    )
        except Exception:
            logger.debug("hermes-korean-ui: cron wrapper failed", exc_info=True)
        return _orig_deliver_result(job, content, adapters=adapters, loop=loop)

    scheduler._deliver_result = _deliver_result
    setattr(scheduler, _MARK, True)


# ---------------------------------------------------------------------------
# 3. Background-review action items (the text after the 💾 prefix)
# ---------------------------------------------------------------------------

def _patch_background_review() -> None:
    from agent import background_review

    if getattr(background_review, _MARK, False):
        return

    _orig_summarize = background_review.summarize_background_review_actions

    def summarize_background_review_actions(*args, **kwargs):
        actions = _orig_summarize(*args, **kwargs)
        try:
            return [_apply(BG_ACTION_REWRITES, str(a)) for a in actions]
        except Exception:
            logger.debug("hermes-korean-ui: bg-review rewrite failed", exc_info=True)
            return actions

    background_review.summarize_background_review_actions = (
        summarize_background_review_actions
    )
    setattr(background_review, _MARK, True)


# ---------------------------------------------------------------------------
# 4. Outgoing text on every Discord delivery path.
#
# ``DiscordAdapter.send`` is only ONE of the adapter's outbound methods, and
# ``_send_with_retry`` / ``send_private_notice`` are the only two that funnel
# back through it (verified: both call ``self.send``).  The interactive
# surfaces build their own embeds and therefore bypass it entirely, and cron
# delivery for Discord skips the live adapter altogether — ``_send_to_platform``
# routes it to the registry's ``standalone_sender_fn`` over HTTP.
#
# So each text-carrying parameter is patched by name.  Parameters that are NOT
# prose — ``command`` on an approval prompt, choice values, model ids — are
# deliberately left untouched.
# ---------------------------------------------------------------------------

_BG_PREFIX_KO = "💾 자기개선 검토: "


def _tr(value):
    """Translate one user-facing string; pass through anything else."""
    if not isinstance(value, str) or not value:
        return value
    exact = LABEL_KO.get(value.strip())
    if exact is not None:
        return exact
    text = _apply(SEND_REWRITES, value)
    # Safety net: the 💾 review items are normally localized upstream by the
    # patched summarize_background_review_actions, but the CLI print path and
    # any future emitter bypass it.  Re-run the item table over the tail so a
    # Korean prefix is never left with an English body.
    if text.startswith(_BG_PREFIX_KO):
        head, _, tail = text.partition(_BG_PREFIX_KO)
        items = [_apply(BG_ACTION_REWRITES, i.strip()) for i in tail.split(" · ")]
        text = head + _BG_PREFIX_KO + " · ".join(items)
    return text


def _wrap_text_params(cls, method_name: str, params: tuple[str, ...]) -> bool:
    """Patch ``cls.method_name`` so the named parameters are translated.

    Works for both positional and keyword call sites by binding the call
    against the original signature.  Returns False when the method does not
    exist upstream (logged by the caller, never fatal).
    """
    import functools
    import inspect

    original = getattr(cls, method_name, None)
    if original is None:
        return False

    signature = inspect.signature(original)

    @functools.wraps(original)
    async def wrapper(*args, **kwargs):
        try:
            bound = signature.bind(*args, **kwargs)
            for name in params:
                if name in bound.arguments:
                    bound.arguments[name] = _tr(bound.arguments[name])
            args, kwargs = bound.args, bound.kwargs
        except Exception:
            logger.debug(
                "hermes-korean-ui: %s rewrite skipped", method_name, exc_info=True
            )
        return await original(*args, **kwargs)

    setattr(cls, method_name, wrapper)
    return True


# (method name, parameters carrying user-facing prose)
_DISCORD_TEXT_PARAMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("send", ("content",)),
    ("send_clarify", ("question",)),
    ("send_slash_confirm", ("title", "message")),
    # NOT ``command`` — that is the shell command awaiting approval.
    ("send_exec_approval", ("description",)),
    ("send_update_prompt", ("prompt",)),
    ("send_choice_picker", ("title",)),
)


def _patch_discord_sends() -> None:
    from plugins.platforms.discord.adapter import DiscordAdapter

    if getattr(DiscordAdapter, _MARK, False):
        return

    missing = [
        name
        for name, params in _DISCORD_TEXT_PARAMS
        if not _wrap_text_params(DiscordAdapter, name, params)
    ]
    if missing:
        logger.warning(
            "hermes-korean-ui: Discord adapter has no %s (left in English)",
            ", ".join(missing),
        )
    setattr(DiscordAdapter, _MARK, True)


def _patch_discord_standalone() -> None:
    """Cron/out-of-gateway deliveries, which never touch the live adapter."""
    from gateway.platform_registry import platform_registry

    entry = platform_registry.get("discord")
    if entry is None or getattr(entry, "standalone_sender_fn", None) is None:
        raise RuntimeError("discord platform entry has no standalone_sender_fn")
    if getattr(entry.standalone_sender_fn, _MARK, False):
        return

    _orig_standalone = entry.standalone_sender_fn

    async def standalone_sender_fn(pconfig, chat_id, message, **kwargs):
        try:
            message = _tr(message)
            if kwargs.get("caption"):
                kwargs["caption"] = _tr(kwargs["caption"])
        except Exception:
            logger.debug("hermes-korean-ui: standalone rewrite skipped", exc_info=True)
        return await _orig_standalone(pconfig, chat_id, message, **kwargs)

    setattr(standalone_sender_fn, _MARK, True)
    try:
        entry.standalone_sender_fn = standalone_sender_fn
    except Exception:
        # Frozen dataclass / namedtuple entry — fall back to replacing the
        # module-level function the registry captured at import time.
        import plugins.platforms.discord.adapter as da
        da._standalone_send = standalone_sender_fn


# ---------------------------------------------------------------------------

_PATCHES = (
    ("tool verbs", _patch_tool_verbs),
    ("cron delivery wrapper", _patch_cron_delivery),
    ("background review", _patch_background_review),
    ("discord send paths", _patch_discord_sends),
    ("discord standalone (cron) send", _patch_discord_standalone),
)


def register(ctx) -> None:  # noqa: ANN001 — hermes plugin contract
    applied, failed = [], []
    for label, patch in _PATCHES:
        try:
            patch()
            applied.append(label)
        except Exception as e:  # noqa: BLE001 — a bad seam must not break startup
            failed.append(label)
            logger.warning(
                "hermes-korean-ui: could not patch %s (left in English): %s",
                label, e,
            )
    logger.info(
        "hermes-korean-ui: Korean UI strings installed for %s%s",
        ", ".join(applied) or "nothing",
        f" (failed: {', '.join(failed)})" if failed else "",
    )
