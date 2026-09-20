# hermes-korean-ui

[hermes-agent](https://github.com/NousResearch/hermes-agent)가 사용자에게 보여주는 **하드코딩된 영어 시스템 문구를 한국어로 바꾸는 플러그인**입니다.

```
⏰ Scheduling update                    →  ⏰ 일정 관리 update
💾 Self-improvement review: ...         →  💾 자기개선 검토: 스킬 'x' 생성됨
♻ Gateway restarted successfully...     →  ♻️ 게이트웨이 재시작 완료...
⚠️ No reply: streaming stopped early... →  ⚠️ 응답 없음: 스트리밍이 일찍 끊겨...
```

## 왜 필요한가

hermes-agent에는 i18n 인프라가 없습니다. `display.language` 설정이 있긴 하지만:

- 지원 언어가 `en, zh, ja, de, es, fr, tr, uk` — **한국어가 없습니다**
- 적용 범위가 승인 프롬프트와 일부 슬래시 커맨드 응답뿐이고, 소스 주석에
  *"does NOT affect agent responses, log lines, tool outputs"* 라고 명시돼 있습니다

봇이 디스코드에 실제로 뿌리는 문구는 전부 f-string 하드코딩이라, 설정으로는
끄는 것(`memory_notifications: off`, `friendly_tool_labels: false`)만 가능하고
번역은 불가능합니다.

## 설치

```bash
hermes plugins install Sn-Kinos/hermes-korean-logger
hermes plugins enable hermes-korean-ui
```

게이트웨이를 재시작하면 적용됩니다. 프로필을 여러 개 쓴다면 **프로필마다** 활성화해야 합니다
(게이트웨이는 각자의 `HERMES_HOME`에 있는 `config.yaml`만 읽습니다).

> `plugin.yaml`의 `name`이 디렉토리명보다 우선하므로, 리포지토리 이름과 무관하게
> `hermes-korean-ui`로 설치됩니다.

## 동작 방식

hermes에는 표시 문자열용 훅이 없어서(`VALID_HOOKS`에 해당 항목 없음), 모듈 단위
monkeypatch로 동작합니다. 패치 지점은 전부 module-global 조회라 import 순서와 무관합니다.

| seam | 대상 |
|---|---|
| `agent.display._TOOL_VERBS` | 친근한 툴 라벨 24종 |
| `cron.scheduler._deliver_result` | 크론 배달 헤더/푸터 |
| `agent.background_review.summarize_background_review_actions` | `💾` 알림 항목 |
| `DiscordAdapter.send` / `send_clarify` / `send_slash_confirm` / `send_exec_approval` / `send_update_prompt` / `send_choice_picker` | 고정 시스템 문구 |
| `platform_registry["discord"].standalone_sender_fn` | 크론 HTTP 직행 경로 |

`_send_with_retry`와 `send_private_notice`는 내부적으로 `self.send()`를 호출하므로
별도 패치가 필요 없습니다.

인터랙티브 메서드는 `inspect.signature().bind()`로 인자를 묶어 처리하기 때문에
positional/keyword 호출 양쪽에서 동작합니다.

## 안전장치

- **평범한 대화는 건드리지 않습니다.** 모든 패턴이 문자열 시작에 앵커돼 있고,
  일반 응답이 시작할 리 없는 형태만 매칭합니다. 문장 중간에 인용된 영어 문구나
  코드 블록 안의 텍스트는 그대로 통과합니다.
- **명령·경로·모델 ID는 보존됩니다.** 예를 들어 `send_exec_approval`은 `description`만
  번역하고 승인 대기 중인 `command`는 절대 건드리지 않습니다.
- **멱등적입니다.** 두 번 적용해도 결과가 같습니다.
- **업스트림이 문구를 바꾸면** 매칭에 실패해 영어로 폴백합니다. 깨지지 않습니다.
- **패치가 실패해도 게이트웨이는 죽지 않습니다.** 각 seam이 개별 try/except로 감싸져
  있고, 실패 시 경고만 남기고 영어 상태로 둡니다.

## 번역하지 않는 것

의도적으로 제외한 범주입니다.

- **시스템 프롬프트 조각** (`• DO NOT call skill_manage with action=patch ...`) —
  모델에게 가는 지시문이라 번역하면 에이전트 동작이 바뀝니다.
- **로그 레코드** — `logger`로 가지 채팅에 도달하지 않습니다.
- **모델이 직접 생성한 문장** — 예를 들어 `Tiny tool gap — retrying that step.` 같은
  문구는 소스 어디에도 없는, LLM이 그때그때 작성한 텍스트입니다. 이건 플러그인이 아니라
  `SOUL.md` / 시스템 프롬프트에서 언어를 지시해야 합니다.

## 설정

크론 배달 헤더/푸터의 한국어판은 기본적으로 꺼져 있습니다. 켜려면 `config.yaml`에:

```yaml
cron:
  wrap_response: false      # 업스트림 영어 래퍼는 꺼야 합니다
  wrap_response_ko: true    # 한국어 래퍼
```

둘 다 켜면 이중으로 감싸지므로, 그 경우 플러그인이 한국어 래퍼를 건너뛰고 경고를 남깁니다.

출력 예시:

```
⏰ 크론잡 결과: 아침 브리핑
(job_id: job_42)
-------------

오늘 일정 3건.

이 작업을 멈추거나 관리하려면 메시지를 보내주세요 (예: "아침 브리핑 알림 중지").
```

## 문구 수정

번역 문구는 전부 `strings.py`에 모여 있습니다. 패치 로직(`__init__.py`)은 건드릴 필요가 없습니다.

| 테이블 | 용도 |
|---|---|
| `TOOL_VERBS_KO` | 툴 라벨 |
| `CRON_WRAP_KO` | 크론 래퍼 템플릿 |
| `BG_ACTION_REWRITES` | `💾` 알림 항목 |
| `SEND_REWRITES` | 고정 시스템 문구 |
| `LABEL_KO` | 버튼 라벨 (완전일치) |

## 호환성

hermes-agent 0.19.0에서 개발·검증했습니다. 사용자에게 보이는 영어 문구를 대상으로 하는
특성상 업스트림 변경에 영향을 받지만, 앞서 적은 대로 매칭 실패는 영어 폴백으로 끝납니다.

플러그인으로 만든 이유도 이것입니다 — `site-packages`를 직접 수정하면
hermes 업데이트 때 조용히 지워집니다.

## 라이선스

MIT
