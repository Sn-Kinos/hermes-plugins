"""Korean translation tables for hermes-agent's hardcoded UI strings.

Edit the wording here; ``__init__.py`` holds the patching logic and should not
need to change.  Every entry is anchored on upstream's *exact* English text, so
an upstream rewording silently falls back to English rather than producing a
mangled half-translation.

Deliberately NOT translated:
  * System-prompt fragments (``• DO NOT call skill_manage ...``).  These are
    instructions sent to the model, not to the user — translating them would
    change agent behaviour.
  * Log records.  They go to ``logger``, never to a chat.
  * Shell commands, model IDs, file paths, slash-command names and job ids
    embedded in a message — captured and re-emitted verbatim.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1. Friendly tool labels  (agent/display.py::_TOOL_VERBS)
#
# Rendered as "<verb> <preview>", e.g. cronjob action=update -> "일정 관리 update".
# ---------------------------------------------------------------------------
TOOL_VERBS_KO: dict[str, str] = {
    "web_search": "웹 검색",
    "web_extract": "읽는 중",
    "browser_navigate": "브라우저 이동",
    "browser_click": "클릭",
    "browser_type": "입력",
    "read_file": "읽는 중",
    "write_file": "쓰는 중",
    "patch": "수정 중",
    "search_files": "파일 검색",
    "terminal": "실행 중",
    "execute_code": "코드 실행",
    "image_generate": "이미지 생성",
    "video_generate": "영상 생성",
    "text_to_speech": "음성 생성",
    "vision_analyze": "이미지 확인",
    "session_search": "지난 대화 검색",
    "skill_view": "스킬 확인",
    "skills_list": "스킬 목록",
    "skill_manage": "스킬 수정",
    "delegate_task": "작업 위임",
    # Renamed upstream in 0.21.x (cronjob -> cronjob_manage, todo -> todo_list).
    # Both spellings are kept so the table works on 0.19.x and 0.21.x alike;
    # the loader ignores names the running build does not define.
    "cronjob": "일정 관리",
    "cronjob_manage": "일정 관리",
    "clarify": "질문",
    "memory": "기억 갱신",
    "todo": "할 일 갱신",
    "todo_list": "할 일 갱신",
}

# ---------------------------------------------------------------------------
# 2. Cron delivery wrapper  (cron/scheduler.py::_deliver_result)
#    Replaces upstream's English header/footer whenever a wrapper is emitted
#    at all (cron.wrap_response, default true).
# ---------------------------------------------------------------------------
CRON_WRAP_KO = (
    "⏰ 크론잡 결과: {task_name}\n"
    "(job_id: {job_id})\n"
    "-------------\n\n"
    "{content}\n\n"
    '이 작업을 멈추거나 관리하려면 메시지를 보내주세요 (예: "{task_name} 알림 중지").'
)

# ---------------------------------------------------------------------------
# 3. Background-review action phrases
#    (agent/background_review.py::summarize_background_review_actions)
# ---------------------------------------------------------------------------
BG_ACTION_REWRITES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^📝 Skill '(?P<n>[^']*)' patched: (?P<d>.*)$", re.S), "📝 스킬 '\\g<n>' 수정: \\g<d>"),
    (re.compile(r"^📝 Skill '(?P<n>[^']*)' created: (?P<d>.*)$", re.S), "📝 스킬 '\\g<n>' 생성: \\g<d>"),
    (re.compile(r"^📝 Skill '(?P<n>[^']*)' rewritten: (?P<d>.*)$", re.S), "📝 스킬 '\\g<n>' 재작성: \\g<d>"),
    (re.compile(r"^(?P<p>📝 )?Skill '(?P<n>[^']*)' created\.?$"), "\\g<p>스킬 '\\g<n>' 생성됨"),
    (re.compile(r"^(?P<p>📝 )?Skill '(?P<n>[^']*)' updated\.?$"), "\\g<p>스킬 '\\g<n>' 갱신됨"),
    (re.compile(r"^(?P<p>📝 )?Skill '(?P<n>[^']*)' improved\.?$"), "\\g<p>스킬 '\\g<n>' 개선됨"),
    (re.compile(r"^(?P<p>📝 )?Skill '(?P<n>[^']*)' patched\.?$"), "\\g<p>스킬 '\\g<n>' 수정됨"),
    (re.compile(r"^(?P<p>📝 )?Skill '(?P<n>[^']*)' deleted\.?$"), "\\g<p>스킬 '\\g<n>' 삭제됨"),
    (re.compile(r"^Memory (?P<g>[➕✏️➖]) ?(?P<d>.*)$", re.S), "기억 \\g<g> \\g<d>"),
    (re.compile(r"^User profile (?P<g>[➕✏️➖]) ?(?P<d>.*)$", re.S), "사용자 프로필 \\g<g> \\g<d>"),
    (re.compile(r"^Skill (?P<g>[➕✏️➖]) ?(?P<d>.*)$", re.S), "스킬 \\g<g> \\g<d>"),
    (re.compile(r"^Memory updated$"), "기억 갱신됨"),
    (re.compile(r"^User profile updated$"), "사용자 프로필 갱신됨"),
    (re.compile(r"^Skill updated$"), "스킬 갱신됨"),
]

# ---------------------------------------------------------------------------
# 4. Outgoing platform text.
#
# ANCHORED at the start of the message against shapes a normal agent reply
# never begins with, so conversational responses are untouched.  Applied in
# order, first match wins.  Ordering matters: longer/more specific variants of
# the same lead-in must come before their shorter prefix.
# ---------------------------------------------------------------------------
SEND_REWRITES: list[tuple[re.Pattern, str]] = [

    # ---- background review -------------------------------------------------
    (re.compile(r"^💾 Self-improvement review: "), "💾 자기개선 검토: "),

    # ---- long-running turn heartbeat --------------------------------------
    (re.compile(r"^⏳ Working — (?P<m>\d+) min\b"), "⏳ 작업 중 — \\g<m>분"),

    # ---- gateway busy / queue states --------------------------------------
    (re.compile(r"^⏳ Gateway restarting — queued for the next turn after it comes back\."),
     "⏳ 게이트웨이 재시작 중 — 돌아온 뒤 다음 턴으로 예약했습니다."),
    (re.compile(r"^⏳ Gateway shutting down — queued for the next turn after it comes back\."),
     "⏳ 게이트웨이 종료 중 — 돌아온 뒤 다음 턴으로 예약했습니다."),
    (re.compile(r"^⏳ Gateway is restarting and is not accepting another turn right now\."),
     "⏳ 게이트웨이가 재시작 중이라 지금은 새 턴을 받을 수 없습니다."),
    (re.compile(r"^⏳ Gateway is shutting down and is not accepting another turn right now\."),
     "⏳ 게이트웨이가 종료 중이라 지금은 새 턴을 받을 수 없습니다."),
    (re.compile(r"^⏳ Gateway is restarting and is not accepting new work right now\."),
     "⏳ 게이트웨이가 재시작 중이라 지금은 새 작업을 받을 수 없습니다."),
    (re.compile(r"^⏳ Gateway is shutting down and is not accepting new work right now\."),
     "⏳ 게이트웨이가 종료 중이라 지금은 새 작업을 받을 수 없습니다."),
    (re.compile(r"^⏳ Subagent working(?P<d>[^—]*)— your message is queued for when it finishes "
                r"\(use /stop to cancel everything\)\."),
     "⏳ 서브에이전트 작업 중\\g<d>— 끝나면 처리하도록 메시지를 대기열에 넣었습니다 "
     "(전부 취소하려면 /stop)."),
    (re.compile(r"^⏳ Compressing context(?P<d>[^—]*)— your message is queued for when it finishes "
                r"\(use /stop to cancel everything\)\."),
     "⏳ 컨텍스트 압축 중\\g<d>— 끝나면 처리하도록 메시지를 대기열에 넣었습니다 "
     "(전부 취소하려면 /stop)."),
    (re.compile(r"^⏳ Queued for the next turn(?P<d>.*?)\. I'll respond once the current task finishes\."),
     "⏳ 다음 턴으로 예약했습니다\\g<d>. 현재 작업이 끝나면 답변할게요."),
    (re.compile(r"^⏳ Agent is running — `(?P<c>[^`]*)` can't run mid-turn\. "
                r"Wait for the current response or `/stop` first\."),
     "⏳ 에이전트 실행 중 — `\\g<c>`는 턴 중간에 실행할 수 없습니다. "
     "현재 응답을 기다리거나 먼저 `/stop`을 보내세요."),
    (re.compile(r"^⏳ This agent is draining for a maintenance action and isn't accepting new turns "
                r"right now\. It'll be back in a moment — please resend shortly\."),
     "⏳ 유지보수 작업으로 이 에이전트가 정리 중이라 지금은 새 턴을 받지 않습니다. "
     "곧 돌아오니 잠시 후 다시 보내주세요."),

    # ---- gateway lifecycle -------------------------------------------------
    (re.compile(r"^♻️? Gateway restarted successfully\. Your session continues\."),
     "♻️ 게이트웨이 재시작 완료. 세션은 그대로 이어집니다."),
    (re.compile(r"^♻️? Gateway online — Hermes is back and ready\."),
     "♻️ 게이트웨이 온라인 — Hermes 준비 완료."),
    (re.compile(r"^⚠️ Gateway (?P<a>restarting|shutting down|restart failed) — "),
     "⚠️ 게이트웨이 \\g<a> — "),

    # ---- self-update -------------------------------------------------------
    (re.compile(r"^✅ Hermes update finished successfully\."), "✅ Hermes 업데이트 완료."),
    (re.compile(r"^✅ Hermes update finished\."), "✅ Hermes 업데이트 완료."),
    (re.compile(r"^❌ Hermes update timed out after 30 minutes\."),
     "❌ Hermes 업데이트가 30분 만에 시간 초과됐습니다."),
    (re.compile(r"^❌ Hermes update failed \(exit code (?P<c>[^)]*)\)\."),
     "❌ Hermes 업데이트 실패 (종료 코드 \\g<c>)."),
    (re.compile(r"^❌ Hermes update failed\. Check the gateway logs or run `hermes update` "
                r"manually for details\."),
     "❌ Hermes 업데이트 실패. 게이트웨이 로그를 확인하거나 `hermes update`를 직접 실행해 보세요."),
    (re.compile(r"^❌ Hermes update failed\."), "❌ Hermes 업데이트 실패."),

    # ---- background terminal process watcher ------------------------------
    (re.compile(r"^\[Background process (?P<s>\S+) finished with exit code (?P<c>\S+)~ "
                r"Here's the final output:"),
     "[백그라운드 프로세스 \\g<s> 종료 (코드 \\g<c>)~ 최종 출력:"),
    (re.compile(r"^\[Background process (?P<s>\S+) is still running~ New output:"),
     "[백그라운드 프로세스 \\g<s> 실행 중~ 새 출력:"),

    # ---- background tasks --------------------------------------------------
    (re.compile(r"^✅ Background task complete\nPrompt:"), "✅ 백그라운드 작업 완료\n요청:"),
    (re.compile(r"^❌ Background task (?P<t>\S+) failed: no provider credentials configured\."),
     "❌ 백그라운드 작업 \\g<t> 실패: 제공자 자격 증명이 설정되지 않았습니다."),
    (re.compile(r"^❌ Background task (?P<t>\S+) failed: "), "❌ 백그라운드 작업 \\g<t> 실패: "),

    # ---- turn / session errors --------------------------------------------
    (re.compile(r"^⚠️ Session too large for the model's context window\.\n"
                r"Use /compact to compress the conversation, or /reset to start fresh\."),
     "⚠️ 세션이 모델의 컨텍스트 창보다 큽니다.\n"
     "/compact로 대화를 압축하거나 /reset으로 새로 시작하세요."),
    (re.compile(r"^⚠️ Your message was interrupted before processing started "
                r"\(likely by a recent /stop\)\. Please send it again\."),
     "⚠️ 처리가 시작되기 전에 메시지가 중단됐습니다 (최근 /stop 때문일 가능성이 높습니다). "
     "다시 보내주세요."),
    (re.compile(r"^⚠️ Processing completed but no response was generated\. "
                r"This may be a transient error — try sending your message again\."),
     "⚠️ 처리는 끝났지만 응답이 생성되지 않았습니다. "
     "일시적인 오류일 수 있으니 메시지를 다시 보내보세요."),
    (re.compile(r"^⚠️ Your message wasn't processed \(the previous turn was still being cleaned up\)\. "
                r"Please send it again\."),
     "⚠️ 메시지가 처리되지 않았습니다 (이전 턴이 아직 정리 중이었습니다). 다시 보내주세요."),
    (re.compile(r"^⚠️ Processing stopped: (?P<e>.*?)\. Try again\.$", re.S),
     "⚠️ 처리가 중단됐습니다: \\g<e>. 다시 시도해 주세요."),
    (re.compile(r"^⚠️ The model returned no response after processing tool results\. "
                r"This can happen with some models — try again or rephrase your question\."),
     "⚠️ 툴 결과를 처리한 뒤 모델이 응답을 반환하지 않았습니다. "
     "일부 모델에서 생길 수 있으니 다시 시도하거나 질문을 바꿔보세요."),
    (re.compile(r"^⚠️ Context compression aborted \((?P<e>[^)]*)\)\. No messages were dropped — "
                r"conversation is unchanged\."),
     "⚠️ 컨텍스트 압축이 중단됐습니다 (\\g<e>). 삭제된 메시지는 없고 대화는 그대로입니다."),

    # ---- provider errors ---------------------------------------------------
    (re.compile(r"^⚠️ Provider authentication failed\. Check the configured credentials; "
                r"raw provider details are in the gateway logs\."),
     "⚠️ 제공자 인증에 실패했습니다. 설정된 자격 증명을 확인하세요. "
     "제공자의 원본 오류는 게이트웨이 로그에 있습니다."),
    (re.compile(r"^⚠️ Provider authentication failed: "), "⚠️ 제공자 인증 실패: "),
    (re.compile(r"^⚠️ The model provider rejected the request\. I kept the raw provider error out of "
                r"chat; check gateway logs for details or try rephrasing\."),
     "⚠️ 모델 제공자가 요청을 거부했습니다. 원본 오류는 채팅에 싣지 않았으니 "
     "게이트웨이 로그를 확인하거나 표현을 바꿔보세요."),
    (re.compile(r"^⚠️ The model provider failed after retries\. I kept raw provider details out of "
                r"chat; check gateway logs for diagnostics\."),
     "⚠️ 재시도 후에도 모델 제공자가 실패했습니다. 원본 오류는 채팅에 싣지 않았으니 "
     "게이트웨이 로그를 확인하세요."),
    (re.compile(r"^⏱️ The model provider is rate-limiting requests\. "
                r"Please wait a moment and try again\."),
     "⏱️ 모델 제공자가 요청 속도를 제한하고 있습니다. 잠시 후 다시 시도해 주세요."),
    (re.compile(r"^⚠️ Billing or credits exhausted — switching to fallback provider\.\.\."),
     "⚠️ 청구 또는 크레딧 소진 — 폴백 제공자로 전환합니다..."),

    # ---- credits notices ---------------------------------------------------
    (re.compile(r"^(?P<g>[⚠•]) Credits (?P<p>\d+)% used · \$(?P<c>\S+) cap"),
     "\\g<g> 크레딧 \\g<p>% 사용 · $\\g<c> 한도"),
    (re.compile(r"^✕ Credit access paused · run /topup to top up"),
     "✕ 크레딧 사용 중지됨 · /topup으로 충전하세요"),
    (re.compile(r"^✓ Credit access restored"), "✓ 크레딧 사용 재개됨"),

    # ---- permissions / admin ----------------------------------------------
    # The {suffix} is a second English sentence built separately — both
    # variants are folded into the pattern so no English tail survives.
    (re.compile(r"^⛔ /(?P<c>\S+) is admin-only here\. You can run: (?P<l>.*?)\. "
                r"Use /whoami for the full list\.", re.S),
     "⛔ /\\g<c> 명령은 여기서 관리자 전용입니다. 사용 가능한 명령: \\g<l>. "
     "전체 목록은 /whoami로 확인하세요."),
    (re.compile(r"^⛔ /(?P<c>\S+) is admin-only here\. No slash commands are enabled for "
                r"non-admins on this platform\. Ask an admin to add you to allow_admin_from "
                r"or to set user_allowed_commands\."),
     "⛔ /\\g<c> 명령은 여기서 관리자 전용입니다. 이 플랫폼에서는 비관리자에게 허용된 슬래시 "
     "명령이 없습니다. 관리자에게 allow_admin_from에 추가하거나 user_allowed_commands를 "
     "설정해 달라고 요청하세요."),
    (re.compile(r"^⛔ /(?P<c>\S+) is admin-only here\. "), "⛔ /\\g<c> 명령은 여기서 관리자 전용입니다. "),

    # ---- approval prompts --------------------------------------------------
    (re.compile(r"^⚠️ \*\*Dangerous command requires approval:\*\*"), "⚠️ **승인이 필요한 위험 명령:**"),
    (re.compile(r"^⚠️ \*\*Smart DENY — owner override for one operation:\*\*"),
     "⚠️ **스마트 거부 — 이 작업 한 번만 소유자 권한으로 허용:**"),
    (re.compile(r"^⚠️ \*?\*?Command Approval Required\*?\*?"), "⚠️ **명령 승인 필요**"),
    (re.compile(r"^⚠️ \*\*Confirm /(?P<c>\S+?)\*\*"), "⚠️ **/\\g<c> 확인**"),
    (re.compile(r"^⚠️ \*?\*?Expensive Model Warning\*?\*?"), "⚠️ **고비용 모델 경고**"),
    (re.compile(r"^⚠️ This action is potentially dangerous \((?P<d>[^)]*)\)\. "),
     "⚠️ 이 작업은 위험할 수 있습니다 (\\g<d>). "),
    (re.compile(r"^⚠️ (?P<d>.*?)\. Asking the user for approval\.", re.S),
     "⚠️ \\g<d>. 사용자에게 승인을 요청합니다."),

    # ---- steer / misc gateway ---------------------------------------------
    (re.compile(r"^⚠️ Steer failed: "), "⚠️ 조정(steer) 실패: "),
    (re.compile(r"^❌ Could not load config: "), "❌ 설정을 불러오지 못했습니다: "),
    (re.compile(r"^❌ Failed to initialize agent: "), "❌ 에이전트 초기화 실패: "),
    (re.compile(r"^❌ Error handling confirmation: "), "❌ 확인 처리 중 오류: "),
    (re.compile(r"^✅ Enabled toolsets: "), "✅ 활성 툴셋: "),
    (re.compile(r"^🚫 Disabled toolsets: "), "🚫 비활성 툴셋: "),
    (re.compile(r"^❌ Disabled toolsets: "), "❌ 비활성 툴셋: "),

    # ---- turn-completion explainer ----------------------------------------
    (re.compile(r"^⚠️ No reply: the model returned empty content after retries and any fallback "
                r"providers\. Try `continue`, switch model/provider, or inspect the tool output above\."),
     "⚠️ 응답 없음: 재시도와 폴백 제공자를 모두 거쳤는데도 모델이 빈 응답을 반환했습니다. "
     "`continue`를 보내거나 모델/제공자를 바꾸거나, 위의 툴 출력을 확인해 보세요."),
    (re.compile(r"^⚠️ No reply: all API retries were exhausted before a response was produced "
                r"\(provider errors / rate limits\)\. Try `continue` or switch provider\."),
     "⚠️ 응답 없음: 응답이 나오기 전에 API 재시도가 모두 소진됐습니다 (제공자 오류 / 요청 한도). "
     "`continue`를 보내거나 제공자를 바꿔 보세요."),
    (re.compile(r"^⚠️ No reply: streaming stopped early and only a partial response was recovered\. "
                r"Send `continue` to resume from where it stopped\."),
     "⚠️ 응답 없음: 스트리밍이 일찍 끊겨 일부 응답만 복구됐습니다. "
     "`continue`를 보내면 멈춘 지점부터 이어집니다."),
    (re.compile(r"^⚠️ No reply: no new content was produced this turn; showing recovered prior "
                r"context\. Send `continue` to retry\."),
     "⚠️ 응답 없음: 이번 턴에 새 내용이 생성되지 않아 복구된 이전 맥락을 표시합니다. "
     "`continue`를 보내면 재시도합니다."),
    (re.compile(r"^⚠️ No reply: the request was interrupted mid-call before a reply was received\. "
                r"Send `continue` to retry\."),
     "⚠️ 응답 없음: 답변을 받기 전에 요청이 중간에 중단됐습니다. `continue`를 보내면 재시도합니다."),
    (re.compile(r"^⚠️ No reply: the per-turn iteration/cost budget was exhausted before a final "
                r"answer\. Send `continue` to keep going\."),
     "⚠️ 응답 없음: 최종 답변 전에 턴당 반복/비용 예산이 소진됐습니다. "
     "`continue`를 보내면 계속 진행합니다."),
    (re.compile(r"^⚠️ No reply: the local model's context window was too small to finish\. "
                r"Increase the context size or use a larger model\."),
     "⚠️ 응답 없음: 로컬 모델의 컨텍스트 창이 너무 작아 끝내지 못했습니다. "
     "컨텍스트 크기를 늘리거나 더 큰 모델을 쓰세요."),
    (re.compile(r"^⚠️ No reply: "), "⚠️ 응답 없음: "),

    # ---- agent-side warnings ----------------------------------------------
    (re.compile(r"^⚠ Auxiliary (?P<t>[^ ]+) failed: "), "⚠ 보조 작업(\\g<t>) 실패: "),
    (re.compile(r"^❌ All API retries exhausted with no successful response\."),
     "❌ API 재시도를 모두 소진했지만 성공한 응답이 없습니다."),
    (re.compile(r"^❌ Context length exceeded and cannot compress further\."),
     "❌ 컨텍스트 길이를 초과했고 더 압축할 수 없습니다."),
    (re.compile(r"^❌ Context overflow, but auto-compaction is disabled"),
     "❌ 컨텍스트가 넘쳤지만 자동 압축이 비활성화돼 있습니다"),
]

# ---------------------------------------------------------------------------
# 5. Exec-approval prompt.
#
# The prompt body is assembled inside the adapter from class attributes, so it
# never passes the send() seam — these replace the attributes themselves.
# ``{}`` in DEADLINE_LINE_KO takes the formatted window ("1 minute").
# ---------------------------------------------------------------------------
EXEC_APPROVAL_KO: dict[str, str] = {
    "_EA_HEADER": (
        "⚠️ **Hermes가 실행 승인을 요청합니다**\n\n"
        "이 명령을 실행할까요?\n\n"
        "**요청한 명령:**\n"
    ),
    "_EA_REASON_LABEL": "**승인이 필요한 이유:** ",
    "_EA_SMART_DENY_LINE": "\n\n**스마트 거부:** 소유자 권한은 이 작업 한 번에만 적용됩니다.",
}

DEADLINE_LINE_KO = "{}간 응답이 없으면 실행되지 **않습니다**."

# Approval window wording ("1 minute" -> "1분"), used inside DEADLINE_LINE_KO.
APPROVAL_WINDOW_KO: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(?P<n>\d+)\s+minutes?$"), "\\g<n>분"),
    (re.compile(r"^(?P<n>\d+)\s+seconds?$"), "\\g<n>초"),
    (re.compile(r"^(?P<n>\d+)\s+hours?$"), "\\g<n>시간"),
]

# ---------------------------------------------------------------------------
# 6. Interactive-component labels (approval / confirm / picker buttons) and the
#    flag reasons, which reach the adapter as ``send_exec_approval(description=)``
#    and are therefore rewritten on the way in.
#    Exact-match only — these are short, so substring rewriting would be unsafe.
# ---------------------------------------------------------------------------
LABEL_KO: dict[str, str] = {
    "✅ Approve": "✅ 승인",
    "✅ Approve Once": "✅ 한 번만 승인",
    "✅ Approved.": "✅ 승인됨.",
    "Approve Once": "한 번만 승인",
    "Approve session": "세션 동안 승인",
    "Always": "항상",
    "Always Approve": "항상 승인",
    "❌ Deny": "❌ 거부",
    "❌ Denied.": "❌ 거부됨.",
    "Deny": "거부",
    "❌ Cancel": "❌ 취소",
    "Cancel": "취소",
    "Yes": "예",
    "No": "아니오",
    # Flag reasons (tools/approval.py, tools/approval_detection.py).
    "execute_code script execution. The script can spawn subprocesses or mutate files "
    "without passing through terminal command approval; approval is one-shot for this run.":
        "execute_code 스크립트 실행. 이 스크립트는 terminal 명령 승인을 거치지 않고 하위 "
        "프로세스를 띄우거나 파일을 바꿀 수 있습니다. 승인은 이번 실행 한 번에만 적용됩니다.",
    "script execution via -e/-c flag": "-e/-c 플래그를 통한 스크립트 실행",
    "script execution via heredoc": "heredoc을 통한 스크립트 실행",
    "dangerous command": "위험한 명령",
}
