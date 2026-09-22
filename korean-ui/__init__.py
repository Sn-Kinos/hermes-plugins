"""Korean localization layer for hermes-agent's hardcoded user-facing strings.

hermes-agent has no i18n infrastructure.  ``display.language`` exists but only
covers approval prompts and a few slash-command replies, its supported set is
``en, zh, ja, de, es, fr, tr, uk`` (no Korean), and its own docstring says it
does not affect agent responses, log lines or tool outputs.  Everything the
bots actually surface on Discord — the cron delivery wrapper, the
``💾 Self-improvement review`` notice, the ``⏰ Scheduling update`` tool label,
gateway lifecycle bumps — is a hardcoded English f-string.

This plugin translates those at these seams:

  1. ``agent.display._TOOL_VERBS``            — friendly tool labels
  1b. the tool-progress renderers             — the bare tool name upstream
                                                falls back to when a tool has
                                                no curated verb
  2. ``cron.scheduler._deliver_result``       — cron delivery wrapper
  3. ``agent.background_review
         .summarize_background_review_actions`` — 💾 review action items
  4. every live ``DiscordAdapter``            — fixed system notices, matched
                                                on anchored patterns only, plus
                                                the exec-approval prompt

Most are module-global lookups, so import order does not matter.  The adapter
is the exception: it is a per-profile directory plugin, so its classes are
found dynamically and the platform registry is hooked for late arrivals.

It lives in ``~/.hermes/plugins-shared/`` (symlinked into each profile's
``plugins/``) rather than as a site-packages edit, for the same reason as
discord-add-reaction: the 0.19.0 upgrade on 2026-09-19 silently wiped an
in-tree patch, and a plugin survives that.

Every patch is individually try/except'd and idempotent — a seam that upstream
renames degrades to untranslated English and logs a warning, it never breaks
the gateway.

No configuration is required: installing the plugin is what switches the
strings to Korean.  ``cron.wrap_response`` keeps its upstream meaning (whether
a cron header/footer is emitted at all, default true); set
``cron.wrap_response_ko: false`` to hand that wrapper back to upstream in
English.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import re

from .strings import (
    APPROVAL_WINDOW_KO,
    BG_ACTION_REWRITES,
    CRON_WRAP_KO,
    DEADLINE_LINE_KO,
    EXEC_APPROVAL_KO,
    LABEL_KO,
    SEND_REWRITES,
    TOOL_NAMES_KO,
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
# 1b. Tool-progress head: "⚙️ tool_search..." -> "⚙️ 툴 검색..."
#
# Three renderers fall back to the bare tool name — no preview, no curated verb,
# and the terminal code-block header — and all three build it as
# ``f"{emoji} {tool_name}"`` at the very start of the line.  So the head is
# rewritten on the way out instead of reproducing each branch: anchored at the
# start and matched against that exact tool's name, so a preview, a command or
# an argument that happens to repeat the name is never touched.
# ---------------------------------------------------------------------------

def _localize_tool_head(text, tool_name: str):
    """Swap a leading ``<emoji> <tool_name>`` for its Korean name."""
    if not isinstance(text, str) or not tool_name:
        return text
    name_ko = TOOL_NAMES_KO.get(tool_name) or TOOL_VERBS_KO.get(tool_name)
    if not name_ko:
        return text
    pattern = re.compile(r"^(\s*\S+[ \t]+)" + re.escape(tool_name) + r"(?![\w-])")
    return pattern.sub(lambda m: m.group(1) + name_ko, text, count=1)


def _wrap_tool_head_renderer(owner, method_name: str, tool_name_arg: str) -> bool:
    """Patch a renderer so the tool name in its returned line comes out Korean."""
    import functools
    import inspect

    original = getattr(owner, method_name, None)
    if original is None or getattr(original, _MARK, False):
        return original is not None

    signature = inspect.signature(original)

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            bound = signature.bind(*args, **kwargs)
            tool_name = bound.arguments.get(tool_name_arg)
            if not isinstance(tool_name, str):
                # format_tool_event takes the event, not the name.
                tool_name = getattr(tool_name, "tool_name", None)
            return _localize_tool_head(result, tool_name)
        except Exception:
            logger.debug("hermes-korean-ui: %s rewrite skipped", method_name, exc_info=True)
            return result

    setattr(wrapper, _MARK, True)
    setattr(owner, method_name, wrapper)
    return True


def _patch_tool_progress_names() -> None:
    from gateway import run_turn_runner
    from gateway.platforms.base import BasePlatformAdapter

    # The progress builder's owning class is located by attribute rather than by
    # name so an upstream split/rename degrades to a warning, not a crash.
    owners = [
        obj
        for obj in vars(run_turn_runner).values()
        if isinstance(obj, type) and "_progress_build_message" in vars(obj)
    ]
    if not owners:
        logger.warning(
            "hermes-korean-ui: no _progress_build_message owner (tool names left in English)"
        )
    for owner in owners:
        _wrap_tool_head_renderer(owner, "_progress_build_message", "tool_name")

    _wrap_tool_head_renderer(BasePlatformAdapter, "format_tool_event", "event")


# ---------------------------------------------------------------------------
# 2. Cron delivery wrapper
# ---------------------------------------------------------------------------

def _cron_wrap_enabled() -> bool:
    """Whether a cron header/footer should be emitted at all.

    ``cron.wrap_response`` keeps its upstream meaning (default true).  The
    Korean wrapper replaces the English one in place, so the user configures
    the wrapper, not the language.  ``cron.wrap_response_ko: false`` is the
    escape hatch that hands the wrapper back to upstream in English.
    """
    try:
        from hermes_cli.config import load_config

        cron_cfg = (load_config() or {}).get("cron") or {}
        return (
            bool(cron_cfg.get("wrap_response", True))
            and bool(cron_cfg.get("wrap_response_ko", True))
        )
    except Exception:
        return True


# Set only for the duration of our own _deliver_result call: while it is true,
# the config that upstream's wrapper decision reads says wrap_response=false,
# because we have already applied the Korean wrapper ourselves.  A ContextVar
# (not a plain flag) so concurrent cron deliveries cannot see each other's
# state — every thread starts from an empty context.
_suppress_english_wrap: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "hermes_korean_ui_suppress_english_wrap", default=False
)


def _patch_cron_delivery() -> None:
    """Translate the cron header/footer with no configuration at all.

    ``cron/scheduler_delivery.py`` builds the wrapper inline, reading the config
    through ``_sched.load_config()`` — a late-bound lookup its own module
    docstring documents as the monkeypatch seam.  So we wrap the content in
    Korean first and make that one config read report ``wrap_response: false``,
    which suppresses upstream's English wrapper instead of stacking on top of
    it.  Patching the config read (rather than asking the user to turn the
    English wrapper off) is what keeps this a drop-in install.
    """
    import cron.scheduler as scheduler

    if getattr(scheduler, _MARK, False):
        return

    _orig_deliver_result = scheduler._deliver_result
    _orig_load_config = scheduler.load_config

    def load_config(*args, **kwargs):
        cfg = _orig_load_config(*args, **kwargs)
        if not _suppress_english_wrap.get() or not isinstance(cfg, dict):
            return cfg
        # Shallow copy, one key changed: every other consumer of this config
        # (media policy, notify + mirror gates) must see it unchanged.
        patched = dict(cfg)
        patched["cron"] = {**(cfg.get("cron") or {}), "wrap_response": False}
        return patched

    def _deliver_result(job, content, adapters=None, loop=None, **kwargs):
        token = None
        try:
            if _cron_wrap_enabled():
                content = CRON_WRAP_KO.format(
                    task_name=job.get("name", job.get("id", "")),
                    job_id=job.get("id", ""),
                    content=content,
                )
                token = _suppress_english_wrap.set(True)
        except Exception:
            logger.debug("hermes-korean-ui: cron wrapper failed", exc_info=True)
        try:
            return _orig_deliver_result(job, content, adapters=adapters, loop=loop, **kwargs)
        finally:
            if token is not None:
                _suppress_english_wrap.reset(token)

    scheduler.load_config = load_config
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


def _patch_exec_approval(cls) -> None:
    """Translate the exec-approval prompt.

    Its body never reaches ``send()`` — the adapter assembles it from class
    attributes and sends the result as an interactive component — so the
    attributes are replaced directly.  Only the ones upstream still defines are
    touched, so a rename degrades to English instead of inventing an attribute.
    """
    for attr, text_ko in EXEC_APPROVAL_KO.items():
        if hasattr(cls, attr):
            setattr(cls, attr, text_ko)
        else:
            logger.warning(
                "hermes-korean-ui: approval prompt has no %s (left in English)", attr
            )


def _patch_approval_deadline_line() -> None:
    """The "doing nothing means it will NOT run" line.

    ``base.py`` calls ``format_approval_deadline_line`` as a module global, so
    replacing it on the defining module is enough for every adapter.
    """
    from gateway.platforms import base

    if getattr(base, _MARK, False):
        return

    _orig = base.format_approval_deadline_line

    def format_approval_deadline_line(timeout_s):
        try:
            from gateway.platforms.base_exec_approval import format_approval_window

            return DEADLINE_LINE_KO.format(
                _apply(APPROVAL_WINDOW_KO, format_approval_window(timeout_s))
            )
        except Exception:
            logger.debug("hermes-korean-ui: deadline line skipped", exc_info=True)
            return _orig(timeout_s)

    base.format_approval_deadline_line = format_approval_deadline_line
    setattr(base, _MARK, True)


def _patch_adapter_class(cls) -> bool:
    """Patch one DiscordAdapter class.  Idempotent per class object."""
    if cls is None or getattr(cls, _MARK, False):
        return False
    _patch_exec_approval(cls)
    missing = [
        name
        for name, params in _DISCORD_TEXT_PARAMS
        if not _wrap_text_params(cls, name, params)
    ]
    if missing:
        logger.warning(
            "hermes-korean-ui: Discord adapter has no %s (left in English)",
            ", ".join(missing),
        )
    setattr(cls, _MARK, True)
    logger.debug("hermes-korean-ui: patched %s.%s", cls.__module__, cls.__qualname__)
    return True


def _loaded_discord_adapter_classes() -> list:
    """Every DiscordAdapter class object currently imported.

    The Discord adapter ships as a *directory plugin* (``plugins/platforms/discord``
    with ``kind: platform``), so the loader imports it as ``hermes_plugins
    .discord_platform`` — and, for every profile after the first to claim that
    name, as ``hermes_plugins.discord_platform__home_<digest>``.  Each is a
    separate module object with its own class.  Importing
    ``plugins.platforms.discord.adapter`` by its in-tree path therefore yields a
    class the gateway never instantiates, which is why this seam silently did
    nothing on a multi-profile install.
    """
    import sys

    found = {}
    for name, module in list(sys.modules.items()):
        if module is None or "discord" not in name or not name.endswith(".adapter"):
            continue
        cls = getattr(module, "DiscordAdapter", None)
        if isinstance(cls, type):
            found.setdefault(id(cls), cls)
    return list(found.values())


def _wrap_platform_entry(entry) -> None:
    """Patch the adapter class an entry builds, and its standalone cron sender."""
    factory = getattr(entry, "adapter_factory", None)
    if factory is not None and not getattr(factory, _MARK, False):
        def adapter_factory(config, _orig=factory):
            adapter = _orig(config)
            try:
                _patch_adapter_class(type(adapter))
            except Exception:
                logger.debug("hermes-korean-ui: adapter patch skipped", exc_info=True)
            return adapter

        setattr(adapter_factory, _MARK, True)
        with contextlib.suppress(Exception):
            entry.adapter_factory = adapter_factory

    sender = getattr(entry, "standalone_sender_fn", None)
    if sender is not None and not getattr(sender, _MARK, False):
        async def standalone_sender_fn(pconfig, chat_id, message, _orig=sender, **kwargs):
            try:
                message = _tr(message)
                if kwargs.get("caption"):
                    kwargs["caption"] = _tr(kwargs["caption"])
            except Exception:
                logger.debug("hermes-korean-ui: standalone rewrite skipped", exc_info=True)
            return await _orig(pconfig, chat_id, message, **kwargs)

        setattr(standalone_sender_fn, _MARK, True)
        with contextlib.suppress(Exception):
            entry.standalone_sender_fn = standalone_sender_fn


def _patch_discord_sends() -> None:
    """Cover every Discord adapter class, whenever it appears.

    Three lanes, because plugin load order is not guaranteed and one gateway
    process serves every profile:

      1. classes already imported when we run;
      2. entries already in the platform registry (any scope);
      3. ``PlatformRegistry.register`` itself, for the profiles whose Discord
         plugin loads after this one.
    """
    from gateway.platform_registry import PlatformRegistry, platform_registry

    for cls in _loaded_discord_adapter_classes():
        _patch_adapter_class(cls)

    for entry in _registered_discord_entries(platform_registry):
        _wrap_platform_entry(entry)

    # Process-global, so only the first profile's plugin instance installs it.
    if not getattr(PlatformRegistry, _MARK, False):
        _orig_register = PlatformRegistry.register

        def register(self, entry, **kwargs):
            try:
                if getattr(entry, "name", "") == "discord":
                    _wrap_platform_entry(entry)
            except Exception:
                logger.debug("hermes-korean-ui: registry hook skipped", exc_info=True)
            return _orig_register(self, entry, **kwargs)

        PlatformRegistry.register = register
        setattr(PlatformRegistry, _MARK, True)


def _registered_discord_entries(registry) -> list:
    """The "discord" entry from the process-global map and from every profile scope."""
    entries = []
    with contextlib.suppress(Exception):
        maps = [registry._entries] + list(registry._scoped_entries.values())
        for scope_map in maps:
            entry = scope_map.get("discord")
            if entry is not None:
                entries.append(entry)
    return entries


# ---------------------------------------------------------------------------

_PATCHES = (
    ("tool verbs", _patch_tool_verbs),
    ("tool progress names", _patch_tool_progress_names),
    ("cron delivery wrapper", _patch_cron_delivery),
    ("background review", _patch_background_review),
    ("approval deadline line", _patch_approval_deadline_line),
    # Covers the live adapter classes and the standalone (cron) sender alike.
    ("discord send paths", _patch_discord_sends),
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
