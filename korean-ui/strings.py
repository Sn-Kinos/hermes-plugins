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


def tpl(template: str, korean: str) -> tuple[re.Pattern, str]:
    """Build an anchored rewrite from upstream's literal text.

    *template* is the English source string with ``{}`` where its f-string
    interpolates; each one becomes a numbered capture.  *korean* places those
    captures with ``{0}``, ``{1}`` … so Korean word order is free:

        tpl("❌ Rate limited after {} retries — {}", "❌ {0}회 재시도 후 속도 제한 — {1}")

    Writing the English side as the literal text (rather than hand-rolled
    regex) keeps an entry checkable against the source line it came from, and
    an upstream reword simply fails to match and falls back to English.
    """
    # Any ``{...}`` is a hole, so format specs (``{tokens:,}``) work too.
    hole = re.compile(r"\{[^{}]*\}")
    parts = hole.split(template)
    pattern = "^" + "(.*?)".join(re.escape(p) for p in parts)
    if hole.search(template) and template.endswith("}"):  # trailing hole takes the rest
        pattern = pattern[: -len("(.*?)")] + "(.*)"
    # ``{0}``/``{1}`` place a specific capture; a bare ``{}`` takes the next one
    # in order, so a same-order translation needs no numbering.
    counter = iter(range(1, 100))

    def place(match: re.Match) -> str:
        index = match.group(1)
        return f"\\g<{int(index) + 1}>" if index else f"\\g<{next(counter)}>"

    replacement = re.sub(r"\{(\d*)\}", place, korean.replace("\\", "\\\\"))
    return re.compile(pattern, re.S), replacement

# ---------------------------------------------------------------------------
# 1b. Tool NAMES for tools upstream has no curated verb for.
#
# Upstream's verbs cover curated built-ins only (``display.verb.*`` in its
# locale catalogs); a plugin tool — discord, kanban — still falls back to the
# raw tool name in the progress line.  These are substituted into that line's
# head only, so the preview, command and arguments after it are untouched, and
# a tool missing from this table simply keeps its English name.
#
# ``tool_search`` / ``tool_describe`` / ``tool_call`` are NOT duplicates of
# upstream's ``display.bridge_generating.*``: that label is only used on the CLI
# path (agent/display.py).  The gateway's progress line is
# ``t("gateway.progress.tool_pending", tool=tool_name)`` — the raw name.
# ---------------------------------------------------------------------------
TOOL_NAMES_KO: dict[str, str] = {
    "discord": "디스코드",
    "discord_admin": "디스코드 관리",
    "tool_search": "툴 검색",
    "tool_describe": "툴 설명",
    "tool_call": "툴 호출",
    "send_message": "메시지 전송",
    "kanban": "칸반",
    "proc": "프로세스",
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
# 4. Outgoing platform text.
#
# ANCHORED at the start of the message against shapes a normal agent reply
# never begins with, so conversational responses are untouched.  Applied in
# order, first match wins.  Ordering matters: longer/more specific variants of
# the same lead-in must come before their shorter prefix.
# ---------------------------------------------------------------------------
SEND_REWRITES: list[tuple[re.Pattern, str]] = [
    # ---- provider errors ---------------------------------------------------
    (re.compile(r"^⚠️ Billing or credits exhausted — switching to fallback provider\.\.\."),
     "⚠️ 청구 또는 크레딧 소진 — 폴백 제공자로 전환합니다..."),

    # ---- credits notices ---------------------------------------------------
    (re.compile(r"^✕ Credit access paused · run /topup to top up"),
     "✕ 크레딧 사용 중지됨 · /topup으로 충전하세요"),
    (re.compile(r"^✓ Credit access restored"), "✓ 크레딧 사용 재개됨"),

    # ---- approval prompts --------------------------------------------------
    (re.compile(r"^⚠️ This action is potentially dangerous \((?P<d>[^)]*)\)\. "),
     "⚠️ 이 작업은 위험할 수 있습니다 (\\g<d>). "),
    (re.compile(r"^⚠️ (?P<d>.*?)\. Asking the user for approval\.", re.S),
     "⚠️ \\g<d>. 사용자에게 승인을 요청합니다."),

    # ---- steer / misc gateway ---------------------------------------------
    (re.compile(r"^❌ Failed to initialize agent: "), "❌ 에이전트 초기화 실패: "),
    (re.compile(r"^❌ Error handling confirmation: "), "❌ 확인 처리 중 오류: "),
    (re.compile(r"^✅ Enabled toolsets: "), "✅ 활성 툴셋: "),
    (re.compile(r"^❌ Disabled toolsets: "), "❌ 비활성 툴셋: "),

    # ---- provider errors, retries and fallbacks ---------------------------
    # Ordered specific-before-generic: "⚠️ {} — trying fallback..." would
    # otherwise swallow the Max-retries variant that precedes it.
    tpl("⚠️ Max retries ({}) exhausted — trying fallback...",
        "⚠️ 최대 재시도 횟수({}회) 소진 — 폴백으로 전환합니다..."),
    tpl("⚠️ Max retries ({}) for invalid responses — trying fallback...",
        "⚠️ 잘못된 응답에 대한 최대 재시도 횟수({}회) 도달 — 폴백으로 전환합니다..."),
    tpl("❌ Max retries ({}) exceeded for invalid responses. Giving up.",
        "❌ 잘못된 응답에 대한 최대 재시도 횟수({}회)를 초과했습니다. 중단합니다."),
    tpl("⚠️ Empty response from model — retrying ({}/{}) in {}s{}",
        "⚠️ 모델이 빈 응답을 반환 — {2}초 후 재시도 ({0}/{1}){3}"),
    tpl("⚠️ Model returning empty responses — switching to fallback provider...",
        "⚠️ 모델이 계속 빈 응답을 반환 — 폴백 제공자로 전환합니다..."),
    tpl("⚠️ Model is repeatedly returning empty content — skipping further retries "
        "to avoid repeat charges",
        "⚠️ 모델이 반복해서 빈 응답을 반환 — 중복 과금을 피하려고 추가 재시도를 건너뜁니다"),
    tpl("⚠️ Model produced reasoning but no visible response after all retries. Returning empty.",
        "⚠️ 재시도를 모두 거쳤지만 모델이 추론만 하고 표시할 응답을 내놓지 않았습니다. 빈 응답을 반환합니다."),
    tpl("❌ Model returned no content after all retries",
        "❌ 재시도를 모두 거쳤지만 모델이 아무 내용도 반환하지 않았습니다"),
    tpl("⚠️ Empty/malformed response — switching to fallback...",
        "⚠️ 비어 있거나 형식이 잘못된 응답 — 폴백으로 전환합니다..."),
    tpl("⚠️ Model declined to respond (safety refusal) — trying fallback...",
        "⚠️ 모델이 응답을 거부했습니다 (안전 정책) — 폴백으로 전환합니다..."),
    tpl("❌ The model provider didn't answer after all retries. Send /retry, or switch models with /model.",
        "❌ 재시도를 모두 거쳤지만 모델 제공자가 응답하지 않았습니다. /retry를 보내거나 /model로 모델을 바꾸세요."),

    tpl("⚠️ Model fallback: {} via {} unavailable ({}); using {} via {}.",
        "⚠️ 모델 폴백: {0}({1}) 사용 불가 ({2}). {3}({4})으로 대체합니다."),
    tpl("✅ Primary model restored: {} via {}; fallback {} via {} is no longer active.",
        "✅ 기본 모델 복구: {0}({1}). 폴백 {2}({3})은 더 이상 사용되지 않습니다."),
    tpl("⚠️ Upstream {} rate-limited — switching to fallback model...",
        "⚠️ 업스트림 {} 속도 제한 — 폴백 모델로 전환합니다..."),
    tpl("⚠️ Provider reported usage/credit exhaustion (unverified — may be a content-filter "
        "rejection) — switching to fallback provider...",
        "⚠️ 제공자가 사용량/크레딧 소진을 알렸습니다 (미확인 — 콘텐츠 필터 거부일 수도 있습니다) "
        "— 폴백 제공자로 전환합니다..."),
    tpl("⚠️ Provider unreachable — switching to fallback provider...",
        "⚠️ 제공자에 연결할 수 없음 — 폴백 제공자로 전환합니다..."),
    tpl("⚠️ Rate limited — switching to fallback provider...",
        "⚠️ 속도 제한 — 폴백 제공자로 전환합니다..."),
    tpl("🔐 Authentication failed and could not be refreshed — switching to fallback provider...",
        "🔐 인증에 실패했고 갱신도 되지 않았습니다 — 폴백 제공자로 전환합니다..."),
    tpl("⚠️ {} — trying fallback...", "⚠️ {} — 폴백으로 전환합니다..."),

    tpl("❌ Provider reported usage/credit exhaustion (unverified — may be a content-filter "
        "rejection) — {}",
        "❌ 제공자가 사용량/크레딧 소진을 알렸습니다 (미확인 — 콘텐츠 필터 거부일 수도 있습니다) — {}"),
    tpl("❌ Billing or credits exhausted — {}", "❌ 청구 또는 크레딧 소진 — {}"),
    tpl("❌ Rate limited after {} retries — {}{}", "❌ {0}회 재시도 후 속도 제한 — {1}{2}"),
    tpl("❌ API failed after {} retries — {}", "❌ {0}회 재시도 후 API 실패 — {1}"),
    tpl("❌ {} {} attempts. The provider may be experiencing issues — try again in a moment.",
        "❌ {0} {1}회 시도. 제공자 쪽 문제일 수 있으니 잠시 후 다시 시도해 주세요."),

    tpl("⚠️ No response from provider for {}s (model: {}, context: ~{} tokens). Reconnecting...",
        "⚠️ {0}초 동안 제공자 응답 없음 (모델: {1}, 컨텍스트: 약 {2} 토큰). 다시 연결합니다..."),
    tpl("⚠️ No first stream event from provider in {}s (codex stream, model: {}). Reconnecting.",
        "⚠️ {0}초 동안 제공자의 첫 스트림 이벤트가 없습니다 (codex 스트림, 모델: {1}). 다시 연결합니다."),
    tpl("⚠️ Codex stream sent no events for {}s after {} (model: {}). Reconnecting.",
        "⚠️ {1} 이후 {0}초 동안 codex 스트림에 이벤트가 없습니다 (모델: {2}). 다시 연결합니다."),
    tpl("⚠ no output from provider for {}s — reconnecting...",
        "⚠ {}초 동안 제공자 출력 없음 — 다시 연결합니다..."),
    tpl("⚠ no response from provider in {}s — reconnecting...",
        "⚠ {}초 동안 제공자 응답 없음 — 다시 연결합니다..."),
    tpl("⚠️ Provider stream returned an empty keepalive frame — retrying this turn without "
        "streaming (streaming stays off for this session).",
        "⚠️ 제공자 스트림이 빈 keepalive 프레임을 반환 — 이번 턴은 스트리밍 없이 재시도합니다 "
        "(이 세션에서는 스트리밍이 꺼진 상태로 유지됩니다)."),
    tpl("⚠ Stream stalled mid tool-call ({}); the action was not executed. Ask me to retry if "
        "you want to continue.",
        "⚠ 툴 호출 도중 스트림이 멈췄습니다 ({}). 해당 작업은 실행되지 않았습니다. 계속하려면 "
        "다시 시도해 달라고 말씀해 주세요."),
    tpl("❌ Could not open a stream to {} after {} attempt{}",
        "❌ {1}번 시도했지만 {0}에 스트림을 열지 못했습니다{2}"),
    tpl("🔌 Detected stale connections from a previous provider issue — cleaned up "
        "automatically. Proceeding with fresh connection.",
        "🔌 이전 제공자 문제로 남아 있던 연결을 발견해 자동으로 정리했습니다. 새 연결로 진행합니다."),
    tpl("🔄 Codex soft failure ({}) — switched to the next pool credential, retrying...",
        "🔄 Codex 일시 실패 ({}) — 풀의 다음 자격 증명으로 바꿔 재시도합니다..."),

    tpl("⏳ Provider temporarily unavailable — retrying automatically in {}s (cycle {}/{})",
        "⏳ 제공자를 일시적으로 사용할 수 없습니다 — {0}초 후 자동 재시도 ({1}/{2} 주기)"),
    tpl("⏳ Automatic recovery gave up after {} cycles — the provider is still unavailable.",
        "⏳ {}주기 동안 자동 복구를 시도했지만 제공자를 여전히 사용할 수 없습니다."),
    tpl("⏳ Retrying in {}s (attempt {}/{})...", "⏳ {0}초 후 재시도합니다 ({1}/{2})..."),
    tpl("⏳ Retrying in {}s ({})...", "⏳ {0}초 후 재시도합니다 ({1})..."),
    tpl("⏳ {} retrying in {}s (attempt {}/{})", "⏳ {0} {1}초 후 재시도 ({2}/{3})"),
    tpl("🔄 Retrying API call ({}/2)...", "🔄 API 호출 재시도 ({}/2)..."),
    tpl("🔄 Retrying API call ({}/3)...", "🔄 API 호출 재시도 ({}/3)..."),

    # ---- gateway-facing provider copy -------------------------------------
    tpl("♻️ Recovered reply — the messaging platform's rate limit refused the original, so part "
        "of it may already have arrived above:",
        "♻️ 복구된 응답 — 메신저 플랫폼의 속도 제한으로 원본이 거부됐습니다. 일부는 위에 이미 "
        "도착했을 수 있습니다:"),

    # ---- compression / context (provider-adjacent) ------------------------
    tpl("⚠ Compression aborted: {}. No messages were dropped — conversation continues "
        "unchanged. Run /compress to retry, or /new to start a fresh session.",
        "⚠ 압축이 중단됐습니다: {}. 삭제된 메시지는 없고 대화는 그대로입니다. /compress로 다시 "
        "시도하거나 /new로 새 세션을 시작하세요."),
    tpl("⚠ Compression summary failed: {}. Inserted a fallback context marker.",
        "⚠ 압축 요약에 실패했습니다: {}. 대체 컨텍스트 표식을 넣었습니다."),
    tpl("⚠ Skipping concurrent compression — another path is already compressing this session. "
        "Will retry after it finishes.",
        "⚠ 동시 압축을 건너뜁니다 — 다른 경로에서 이미 이 세션을 압축 중입니다. 끝난 뒤 재시도합니다."),
    tpl("⚠ Context compression reached its total ceiling after {}s{}. No messages were dropped "
        "— continuing without compression. Run /compress to retry or /new for a clean session.",
        "⚠ 컨텍스트 압축이 {0}초 만에 총 한도에 도달했습니다{1}. 삭제된 메시지는 없으며 압축 없이 "
        "계속합니다. /compress로 다시 시도하거나 /new로 새 세션을 시작하세요."),
    tpl("⚠ Context compression timed out after {}s with no output from the summary model. No "
        "messages were dropped — continuing without compression. Run /compress to retry, /new "
        "for a clean session, or check auxiliary.compression.",
        "⚠ 요약 모델이 아무 출력도 내지 않아 컨텍스트 압축이 {}초 만에 시간 초과됐습니다. 삭제된 "
        "메시지는 없으며 압축 없이 계속합니다. /compress로 다시 시도하거나, /new로 새 세션을 "
        "시작하거나, auxiliary.compression 설정을 확인하세요."),
    tpl("⚠ Configured auxiliary compression provider '{}' is unavailable, so older messages in "
        "long chats will be cut without a summary. Sign in to that provider again, or change "
        "auxiliary.compression in your config.",
        "⚠ 설정된 보조 압축 제공자 '{}'을(를) 사용할 수 없어, 긴 대화의 오래된 메시지가 요약 없이 "
        "잘려 나갑니다. 해당 제공자에 다시 로그인하거나 설정의 auxiliary.compression을 바꾸세요."),
    tpl("⚠ No auxiliary LLM provider configured: Hermes has no helper model for summarising "
        "long chats, so older messages will be cut without a summary. Run `hermes setup` to add one.",
        "⚠ 보조 LLM 제공자가 설정되지 않았습니다: 긴 대화를 요약할 보조 모델이 없어 오래된 메시지가 "
        "요약 없이 잘려 나갑니다. `hermes setup`으로 하나 추가하세요."),
    tpl("⚠ Context is over the compression threshold (~{} tokens >= {}) but compression is "
        "currently blocked ({}). The model may stop responding. Run /new to start a fresh "
        "session or /compress to retry immediately.",
        "⚠ 컨텍스트가 압축 임계값을 넘었지만 (약 {0} 토큰 >= {1}) 현재 압축이 막혀 있습니다 ({2}). "
        "모델이 응답을 멈출 수 있습니다. /new로 새 세션을 시작하거나 /compress로 즉시 재시도하세요."),
    tpl("🗜️ Context reduced to {} tokens (was {}), retrying...",
        "🗜️ 컨텍스트를 {0} 토큰으로 줄였습니다 (이전 {1}). 재시도합니다..."),
    tpl("🗜️ Compressed {} → {} payload bytes, retrying...",
        "🗜️ 페이로드를 {0} → {1} 바이트로 압축했습니다. 재시도합니다..."),
    tpl("📐 Compression could not reduce the request further — removed retained vision payloads "
        "and retrying...",
        "📐 요청을 더 줄일 수 없어 보관 중이던 이미지 페이로드를 제거하고 재시도합니다..."),
    tpl("❌ The provider rejected the request because the requested output length exceeds its "
        "output cap for this model, and the error did not state the allowed limit.",
        "❌ 요청한 출력 길이가 이 모델의 출력 상한을 넘어 제공자가 요청을 거부했습니다. 오류에 "
        "허용 한도는 나와 있지 않았습니다."),
    tpl("💡 Wait a moment and /retry; another request on the same server (e.g. a background "
        "review) may have been holding its context.",
        "💡 잠시 후 /retry를 해보세요. 같은 서버의 다른 요청(예: 배경 검토)이 컨텍스트를 점유하고 "
        "있었을 수 있습니다."),
    tpl("💡 Try /new to start a fresh conversation, or /compress to retry compression.",
        "💡 /new로 새 대화를 시작하거나 /compress로 압축을 다시 시도해 보세요."),
    tpl("⚠️ Turn aborted by the liveness watchdog ({}s without activity); lease renewal stopped "
        "so the session can be reclaimed. You can retry your message.",
        "⚠️ 활동이 {}초 동안 없어 liveness 워치독이 턴을 중단했습니다. 세션을 회수할 수 있도록 "
        "리스 갱신을 멈췄습니다. 메시지를 다시 보내셔도 됩니다."),

    # ---- tools / subagents ------------------------------------------------
    tpl("⚠️ Subagent timed out{}{} without finishing. I will carry on without it; ask me to "
        "retry it, or raise delegation.child_timeout_seconds in config.yaml if these tasks "
        "legitimately take longer.",
        "⚠️ 서브에이전트가 끝내지 못하고 시간 초과됐습니다{0}{1}. 이것 없이 계속 진행합니다. "
        "다시 시도하라고 말씀하시거나, 이런 작업이 원래 오래 걸린다면 config.yaml의 "
        "delegation.child_timeout_seconds를 늘리세요."),
    tpl("⚠ SUBAGENT MODEL REJECTED: the configured Subagent Model \"{}\" was rejected by "
        "provider \"{}\" (HTTP 400: not a valid model ID).",
        "⚠ 서브에이전트 모델 거부됨: 설정된 서브에이전트 모델 \"{0}\"이(가) 제공자 \"{1}\"에서 "
        "거부됐습니다 (HTTP 400: 유효하지 않은 모델 ID)."),
    tpl("⚠ Lightpanda fallback: Chrome was used for this browser action. {}",
        "⚠ Lightpanda 폴백: 이번 브라우저 작업에는 Chrome을 사용했습니다. {}"),
    tpl("⚠️ Sudo authentication failed — cached password cleared. You will be prompted again on "
        "the next sudo command.",
        "⚠️ sudo 인증에 실패해 캐시된 비밀번호를 지웠습니다. 다음 sudo 명령에서 다시 물어봅니다."),
    tpl("⚠ {}: upstream moved this skill to {}, but your modified copy at {} was kept — it will "
        "not receive updates. Run `hermes skills reset {} --restore` to move to the new location.",
        "⚠ {0}: 업스트림이 이 스킬을 {1}(으)로 옮겼지만, {2}에 있는 수정본을 그대로 뒀습니다 — "
        "업데이트는 반영되지 않습니다. 새 위치로 옮기려면 `hermes skills reset {3} --restore`를 "
        "실행하세요."),

    # ---- agent-side warnings ----------------------------------------------
    (re.compile(r"^⚠ Auxiliary (?P<t>[^ ]+) failed: "), "⚠ 보조 작업(\\g<t>) 실패: "),
]

# ---------------------------------------------------------------------------
# 6. Interactive-component labels (approval / confirm / picker buttons) and the
#    flag reasons, which reach the adapter as ``send_exec_approval(description=)``
#    and are therefore rewritten on the way in.
#    Exact-match only — these are short, so substring rewriting would be unsafe.
# ---------------------------------------------------------------------------
LABEL_KO: dict[str, str] = {
    "✅ Approve": "✅ 승인",
    "Approve Once": "한 번만 승인",
    "Always": "항상",
    "Always Approve": "항상 승인",
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

# ---------------------------------------------------------------------------
# 7. Busy-input / tool-progress first-time tips (agent/onboarding.py).
#
# Replaced at the SOURCE, not matched on output: the busy tip is appended as a
# second paragraph to the (already Korean) busy ack, and the tool-progress tip
# lands inside the progress bubble — which progress-codeblock fences — so a
# start-anchored output rule can never see either.  Keys mirror upstream's
# _BUSY_INPUT_HINTS_GATEWAY modes.
# ---------------------------------------------------------------------------
BUSY_HINTS_KO: dict[str, str] = {
    "queue": (
        "💡 처음 안내 — 작업을 끊지 않고 메시지를 대기열에 넣었어요. 새 메시지가 현재 작업을 바로 "
        "멈추게 하려면 `/busy interrupt`, 상태를 보려면 `/busy status`를 보내세요. 이 안내는 다시 "
        "나오지 않아요."
    ),
    "steer": (
        "💡 처음 안내 — 메시지를 현재 실행에 끼워 넣었어요. 작업을 끊지 않고 다음 도구 호출 뒤에 "
        "전달돼요. 바꾸려면 `/busy interrupt`나 `/busy queue`, 상태를 보려면 `/busy status`를 "
        "보내세요. 이 안내는 다시 나오지 않아요."
    ),
    "redirect": (
        "💡 처음 안내 — 보내신 메시지로 현재 실행의 방향을 바꿨어요. 끝난 작업은 맥락에 그대로 "
        "남고, `/stop`으로 작업을 취소할 수 있어요. 별도 턴으로 기다리게 하려면 `/busy queue`, "
        "상태를 보려면 `/busy status`를 보내세요. 이 안내는 다시 나오지 않아요."
    ),
}
BUSY_HINT_DEFAULT_KO = (
    "💡 처음 안내 — 답하려고 하던 작업을 방금 중단했어요. 이어지는 메시지를 현재 작업 뒤로 "
    "미루려면 `/busy queue`, 끊지 않고 실행 중에 끼워 넣으려면 `/busy steer`, 상태를 보려면 "
    "`/busy status`를 보내세요. 이 안내는 다시 나오지 않아요."
)
TOOL_PROGRESS_HINT_KO = (
    "💡 처음 안내 — 그 도구가 시간이 좀 걸려서 진행 상황을 단계마다 보내고 있어요. 진행 메시지가 "
    "번잡하면 `/verbose`로 모드를 바꾸세요 (all → new → off). 이 안내는 다시 나오지 않아요."
)

# ---------------------------------------------------------------------------
# 8. Status-detail slots: the heartbeat's trailing action and the busy ack's
#    "실행 중: {tool}".  Upstream fills both with internal values never meant
#    for the catalog — a raw tool id or an agent._touch_activity() string.
# ---------------------------------------------------------------------------
# Nouns, not verbs: these fill a "what is running" slot ("실행 중: 터미널").
# Plugin tools fall back to TOOL_NAMES_KO.
TOOL_NOUNS_KO: dict[str, str] = {
    "terminal": "터미널",
    "read_file": "파일 읽기",
    "write_file": "파일 쓰기",
    "patch": "파일 수정",
    "search_files": "파일 검색",
    "execute_code": "코드 실행",
    "web_search": "웹 검색",
    "web_extract": "웹 페이지 읽기",
    "browser_navigate": "브라우저 이동",
    "browser_click": "브라우저 클릭",
    "browser_type": "브라우저 입력",
    "image_generate": "이미지 생성",
    "video_generate": "영상 생성",
    "text_to_speech": "음성 생성",
    "vision_analyze": "이미지 분석",
    "session_search": "지난 세션 검색",
    "skill_view": "스킬 보기",
    "skills_list": "스킬 목록",
    "skill_manage": "스킬 관리",
    "delegate_task": "작업 위임",
    "cronjob_manage": "예약 관리",
    "clarify": "질문",
    "memory": "메모리",
    "todo_list": "할 일 목록",
}


def _full(entry):
    """A tpl() entry that must match the WHOLE activity string."""
    pattern, replacement = entry
    return re.compile(pattern.pattern + r"\Z", pattern.flags), replacement


# agent._touch_activity() descriptions.  Specific before generic.
ACTIVITY_KO: list[tuple[re.Pattern, str]] = [_full(e) for e in (
    tpl("starting new turn (cached)", "새 턴 시작 (캐시)"),
    tpl("starting new turn", "새 턴 시작"),
    tpl("starting API call #{}", "API 호출 #{} 시작"),
    tpl("API call #{} completed", "API 호출 #{} 완료"),
    tpl("receiving stream response", "스트림 응답 수신 중"),
    tpl("waiting for non-streaming API response", "비스트리밍 API 응답 대기 중"),
    tpl("waiting for stream response ({}s, no chunks yet)", "스트림 응답 대기 중 ({}초, 아직 수신 없음)"),
    tpl("waiting for stream response ({}s, {})", "스트림 응답 대기 중 ({0}초, {1})"),
    tpl("waiting for provider response (streaming)", "제공자 응답 대기 중 (스트리밍)"),
    tpl("waiting for provider response ({}s, {})", "제공자 응답 대기 중 ({0}초, {1})"),
    tpl("tool results posted, continuing iteration #{}", "도구 결과 전달, 반복 #{} 계속"),
    tpl("tool completed: {} ({}s){}", "도구 완료: {0} ({1}초){2}"),
    tpl("executing tool: {}", "도구 실행 중: {}"),
    tpl("executing {} tools concurrently: {}", "도구 {0}개 동시 실행 중: {1}"),
    tpl("sequential tool running ({}s): {}", "도구 순차 실행 중 ({0}초): {1}"),
    tpl("stream retry {}/{} after {}", "{2} 이후 스트림 재시도 {0}/{1}"),
    tpl("stale stream detected after {}s, reconnecting", "{}초 동안 스트림이 멈춰 다시 연결 중"),
    tpl("stale non-streaming call killed after {}s", "{}초 동안 멈춘 비스트리밍 호출을 종료함"),
    tpl("codex stream killed after {}s with no SSE events", "{}초 동안 SSE 이벤트가 없어 codex 스트림을 종료함"),
    tpl("codex stream killed after {}s without model progress", "{}초 동안 모델 진행이 없어 codex 스트림을 종료함"),
    tpl("codex stream killed after {}s with no first stream event", "{}초 동안 첫 스트림 이벤트가 없어 codex 스트림을 종료함"),
    tpl("API error recovery (attempt {}/{})", "API 오류 복구 중 (시도 {0}/{1})"),
    tpl("compression blocked ({})", "압축 차단됨 ({})"),
    tpl("local model loading", "로컬 모델 로딩 중"),
    tpl("{}, {}s remaining", "{0}, {1}초 남음"),
)]
