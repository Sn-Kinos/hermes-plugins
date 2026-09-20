"""Add an ``add_reaction`` action to the built-in ``discord`` tool.

hermes-agent ships pin/unpin/delete/create_thread on the ``discord`` tool but
**no way to react to a message** (verified again on 0.19.0), and the terminal
fallback is blocked because ``DISCORD_BOT_TOKEN`` is in
``tools/environments/local.py``'s ``_HERMES_PROVIDER_ENV_BLOCKLIST``.  The
bots need reactions for the #qurare closing protocol ("mention = keep going,
reaction = done"), so this was originally patched straight into
``site-packages/tools/discord_tool.py`` — and the 0.19.0 upgrade on
2026-09-19 silently wiped it.

This is the same patch as a **plugin** instead: it lives in
``~/.hermes/plugins-shared/`` (symlinked into each profile's ``plugins/``),
so a hermes upgrade can no longer remove it.  It patches the module rather
than registering a separate tool so that SOUL.md's "use the discord tool's
add_reaction action" instruction keeps working unchanged.

Emoji are URL-encoded as Discord requires: Unicode directly (🫡 →
``%F0%9F%AB%A1``), custom emoji as ``name:id``.
"""

from __future__ import annotations

import json
import logging
import urllib.parse

logger = logging.getLogger(__name__)

_ACTION = "add_reaction"
_SIGNATURE = "(channel_id, message_id, emoji)"
_DESCRIPTION = "react to a message with an emoji (Unicode, or name:id for custom)"
_REQUIRED = ["channel_id", "message_id", "emoji"]


def register(ctx) -> None:  # noqa: ANN001 — hermes plugin contract
    # Import (not just reference) so the built-in tool has registered itself
    # before we extend it — plugin load order vs. tool import is not fixed.
    import tools.discord_tool as dt
    from tools.registry import registry

    if _ACTION in dt._ACTIONS:  # already patched (double register / reload)
        return

    def _add_reaction(token, channel_id="", message_id="", emoji="", **_kwargs) -> str:
        """PUT /channels/{c}/messages/{m}/reactions/{emoji}/@me — 204 on success."""
        encoded = urllib.parse.quote(emoji, safe="")
        dt._discord_request(
            "PUT",
            f"/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
            token,
        )
        return json.dumps({
            "success": True,
            "message": f"Reacted {emoji} to message {message_id}.",
        })

    # ── action tables (drive both schema construction and dispatch) ──
    dt._ACTIONS[_ACTION] = _add_reaction
    dt._CORE_ACTIONS[_ACTION] = _add_reaction
    dt._CORE_ACTION_NAMES = frozenset(dt._CORE_ACTION_NAMES | {_ACTION})
    # 0.19.x kept an _ADMIN_ACTION_NAMES frozenset; 0.21.x derives _ADMIN_ACTIONS
    # directly. Keep whichever the running build actually has in sync.
    if hasattr(dt, "_ADMIN_ACTION_NAMES"):
        dt._ADMIN_ACTION_NAMES = frozenset(dt._ACTIONS.keys()) - dt._CORE_ACTION_NAMES
    # _ADMIN_ACTIONS is deliberately left alone: on 0.21.x it is derived at
    # import time and ``get_dynamic_schema_admin`` is a functools.partial bound
    # to that exact dict, so rebinding the name would strand the partial on a
    # stale copy. Our action is added to _ACTIONS afterwards, so it never lands
    # in the admin subset to begin with.
    # ``_ACTION_MANIFEST`` rows were ``(name, sig, desc)`` through 0.19.x and
    # gained the handler in 0.21.x: ``(name, fn, sig, desc)``.  Upstream
    # unpacks every row by arity, so appending the wrong shape aborts the
    # whole plugin load ("not enough values to unpack"). Match whatever the
    # running build uses instead of pinning one layout.
    _arity = len(dt._ACTION_MANIFEST[0]) if dt._ACTION_MANIFEST else 4
    if _arity == 4:
        dt._ACTION_MANIFEST.append((_ACTION, _add_reaction, _SIGNATURE, _DESCRIPTION))
    else:
        dt._ACTION_MANIFEST.append((_ACTION, _SIGNATURE, _DESCRIPTION))
    dt._REQUIRED_PARAMS[_ACTION] = list(_REQUIRED)
    dt._HANDLER_DEFAULTS["emoji"] = ""

    # ── dispatch: _run_discord_action forwards a fixed kwarg list that has no
    # `emoji`, so handle our action before delegating to the original ──
    _orig_run = dt._run_discord_action

    def _run_discord_action(action, valid_actions, tool_label, emoji="", **kwargs):
        if action != _ACTION or _ACTION not in valid_actions:
            return _orig_run(action, valid_actions, tool_label, **kwargs)

        token = dt._get_bot_token()
        if not token:
            return json.dumps({"error": "DISCORD_BOT_TOKEN not configured."})

        values = {"emoji": emoji, **{k: kwargs.get(k, "") for k in ("channel_id", "message_id")}}
        missing = [p for p in _REQUIRED if not values.get(p)]
        if missing:
            return json.dumps({
                "error": f"Missing required parameters for '{_ACTION}': {', '.join(missing)}",
            })

        try:
            return _add_reaction(token, values["channel_id"], values["message_id"], values["emoji"])
        except dt.DiscordAPIError as e:
            logger.warning("Discord API error in %s action '%s': %s", tool_label, _ACTION, e)
            if e.status == 403:
                return json.dumps({"error": dt._enrich_403(_ACTION, e.body)})
            return json.dumps({"error": str(e)})
        except Exception as e:  # noqa: BLE001 — must not raise into the agent loop
            logger.exception("Unexpected error in %s action '%s'", tool_label, _ACTION)
            return json.dumps({"error": f"Unexpected error: {e}"})

    dt._run_discord_action = _run_discord_action

    # ── schema: add the `emoji` property (covers the static schema below and
    # the dynamic one _get_dynamic_schema builds) ──
    _orig_build_schema = dt._build_schema

    def _build_schema(actions, caps, tool_name):
        schema = _orig_build_schema(actions, caps, tool_name)
        if _ACTION in actions:
            schema["parameters"]["properties"]["emoji"] = {
                "type": "string",
                "description": (
                    "Emoji to react with (add_reaction): a Unicode emoji such as "
                    "🫡, or 'name:id' for a custom guild emoji."
                ),
            }
        return schema

    dt._build_schema = _build_schema

    # The built-in registered its schema at import time, before this ran —
    # rebuild it so the model actually sees the new action.
    schema = _build_schema(
        list(dt._CORE_ACTIONS.keys()), caps={"detected": False}, tool_name="discord",
    )
    # 0.19.x cached it as a module global and wrapped handlers with
    # ``_make_handler``; 0.21.x dropped both and registers an inline lambda
    # that injects the ``action`` key. Support either shape.
    if hasattr(dt, "_STATIC_CORE_SCHEMA") and hasattr(dt, "_make_handler"):
        dt._STATIC_CORE_SCHEMA = schema
        registry.register(
            name="discord",
            toolset="discord",
            schema=schema,
            handler=dt._make_handler(dt.discord_core),
            check_fn=dt.check_discord_tool_requirements,
            requires_env=["DISCORD_BOT_TOKEN"],
        )
    logger.info("discord-add-reaction: 'add_reaction' action installed on the discord tool")
