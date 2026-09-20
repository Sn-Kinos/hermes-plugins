# hermes-plugins

[hermes-agent](https://github.com/NousResearch/hermes-agent)용 로컬 플러그인 모음.

전부 같은 성격입니다 — **업스트림이 안 해주는 것을 메우되, 업그레이드에 지워지지 않게**
플러그인으로 포장한 패치들입니다.

| 플러그인 | 하는 일 |
|---|---|
| [`korean-ui/`](korean-ui/) | 하드코딩된 영어 시스템 문구를 한국어로 |
| [`discord-add-reaction/`](discord-add-reaction/) | `discord` 툴에 `add_reaction` 액션 추가 |

## 설치

`hermes plugins install`은 `owner/repo/서브디렉토리` 형식을 지원하므로, 필요한 것만 골라
설치할 수 있습니다.

```bash
hermes plugins install Sn-Kinos/hermes-plugins/korean-ui
hermes plugins install Sn-Kinos/hermes-plugins/discord-add-reaction

hermes plugins enable hermes-korean-ui
hermes plugins enable discord-add-reaction
```

설치 디렉토리 이름은 각 `plugin.yaml`의 `name`을 따르므로 서브디렉토리명과 무관합니다.

프로필을 여러 개 쓴다면 **프로필마다** 활성화해야 합니다. 게이트웨이는 각자의
`HERMES_HOME`에 있는 `config.yaml`만 읽습니다. 적용에는 게이트웨이 재시작이 필요합니다.

## 왜 모노레포인가

두 플러그인 모두 업스트림 내부 구조에 monkeypatch로 붙습니다. 그래서 hermes를 올릴 때마다
**같이** 깨지고 **같이** 고쳐야 합니다.

실제로 2026-09-20의 0.19.0 → 0.21.3 업그레이드에서 둘 다 한 번에 깨졌습니다.

- `discord-add-reaction` — 액션 매니페스트가 `(name, sig, desc)`에서 `(name, fn, sig, desc)`로
  바뀌고, `_make_handler` / `_STATIC_CORE_SCHEMA` / `_ADMIN_ACTION_NAMES`가 사라졌으며,
  툴 섀도잉 차단이 도입됨
- `korean-ui` — `_TOOL_VERBS`에서 `cronjob` → `cronjob_manage`, `todo` → `todo_list` 개명

한 리포에 두면 호환 상태를 한 곳에서 추적하고 한 번에 검증할 수 있습니다.

## 호환성

| | 0.19.0 | 0.21.3 |
|---|---|---|
| `korean-ui` | ✅ | ✅ |
| `discord-add-reaction` | ✅ | ✅ |

두 플러그인 모두 런타임에 업스트림 구조를 감지해 양쪽 버전에서 동작합니다.

## 공통 설계 원칙

- **폴백은 조용히, 실패는 시끄럽게.** 업스트림이 이름을 바꾸면 해당 부분만 원래 동작으로
  돌아가고 경고를 남깁니다. 게이트웨이를 죽이지 않습니다.
- **패치는 개별 격리.** 한 seam이 실패해도 나머지는 적용됩니다.
- **멱등적.** 중복 로드에도 안전합니다.
- **site-packages를 직접 고치지 않습니다.** 그렇게 했다가 0.19.0 업그레이드에서 조용히
  지워진 전례가 있습니다 — 이 리포가 존재하는 이유입니다.

## 라이선스

MIT
