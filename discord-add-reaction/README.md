# discord-add-reaction

hermes-agent의 내장 `discord` 툴에 **`add_reaction` 액션을 추가**합니다.

업스트림은 `fetch_messages` / `search_members` / `create_thread`(그리고 admin 툴의 여러
서버 관리 액션)를 제공하지만, **메시지에 리액션을 다는 수단이 없습니다.**

터미널 폴백도 막혀 있습니다 — `DISCORD_BOT_TOKEN`이
`tools/environments/local.py`의 `_HERMES_PROVIDER_ENV_BLOCKLIST`에 있어서 셸에서
직접 API를 부를 수 없습니다.

## 설치

```bash
hermes plugins install Sn-Kinos/hermes-plugins/discord-add-reaction
hermes plugins enable discord-add-reaction
```

## 사용

`discord` 툴의 액션으로 노출되므로, 시스템 프롬프트에서 그냥 이름으로 지시하면 됩니다.

```
add_reaction(channel_id, message_id, emoji)
```

`emoji`는 유니코드 이모지(`🫡`) 또는 커스텀 길드 이모지의 `name:id` 형식입니다.
Discord API가 요구하는 대로 URL 인코딩됩니다 (`🫡` → `%F0%9F%AB%A1`).

## 동작 방식

별도 툴을 등록하지 않고 **기존 `discord` 툴을 확장**합니다. 그래서 "discord 툴의
add_reaction 액션을 써라"는 식의 기존 프롬프트가 그대로 동작합니다.

액션 테이블(`_ACTIONS`, `_CORE_ACTIONS`), 액션 매니페스트, `_REQUIRED_PARAMS`,
`_HANDLER_DEFAULTS`에 항목을 추가하고, 스키마 빌더를 감싸 `emoji` 파라미터를 노출합니다.

`add_reaction`은 **core** 액션으로 들어갑니다 — admin 툴로 새지 않습니다.

## 버전 대응

업스트림 구조를 런타임에 감지합니다.

- **액션 매니페스트 arity** — 0.19.x는 `(name, sig, desc)`, 0.21.x는 `(name, fn, sig, desc)`.
  업스트림이 모든 행을 arity로 언패킹하므로 형식이 틀리면 플러그인 로드 전체가
  `not enough values to unpack`으로 실패합니다. 그래서 첫 행의 길이를 보고 맞춥니다.
- **`_make_handler` / `_STATIC_CORE_SCHEMA`** — 0.21.x에서 제거됐습니다. 있을 때만 정적
  스키마를 갱신하고 툴을 재등록합니다. 0.21.x는 `get_dynamic_schema_core`가 패치된
  `_build_schema`를 타고 같은 `_CORE_ACTIONS` 딕셔너리를 공유하므로 재등록이 불필요하며,
  시도하면 섀도잉 차단에 걸립니다.
- **`_ADMIN_ACTIONS`는 건드리지 않습니다.** 0.21.x의 `get_dynamic_schema_admin`이
  `functools.partial`로 그 딕셔너리 객체에 묶여 있어, 이름을 재바인딩하면 partial이
  오래된 사본을 보게 됩니다. 우리 액션은 `_ADMIN_ACTIONS`가 만들어진 뒤에 `_ACTIONS`에
  추가되므로 애초에 admin 쪽에 들어가지 않습니다.

## 유래

원래는 `site-packages/tools/discord_tool.py`를 직접 고쳐서 썼습니다. **2026-09-19의 0.19.0
업그레이드가 그 패치를 조용히 지웠습니다.** 같은 내용을 플러그인으로 옮긴 것이 이
디렉토리이고, 그 판단은 2026-09-20의 0.21.3 업그레이드에서 검증됐습니다 —
site-packages는 통째로 교체됐지만 플러그인은 살아남아 코드만 고치면 됐습니다.

## 라이선스

MIT
