# mattermost-thread-followup

Mattermost **스레드 안에서는 멘션 없이도** 봇이 답하게 합니다.

업스트림 `MattermostAdapter`는 DM이 아닌 글을 채널 단위로만 거릅니다
(`require_mention` / `free_response_channels`). `root_id`는 보지 않기 때문에, 봇이 직접
올린 글 아래에 다는 답글에도 `@봇이름`이 있어야 반응합니다. Discord에는 "스레드에서는 멘션
불필요" 설정이 있지만 Mattermost에는 없습니다.

## 동작

`MattermostAdapter._handle_ws_event`를 감쌉니다. 새 글이 아래 조건을 **모두** 만족하면
본문 앞에 `@<봇이름>`을 붙여 원래 핸들러로 넘깁니다. 원래 핸들러가 멘션을 확인하고 다시
떼어 내므로, 에이전트가 받는 본문은 사용자가 쓴 그대로입니다.

- 스레드 답글이다 (`root_id` 있음). DM은 원래 게이팅이 없으므로 건드리지 않음
- 사람이 쓴 글이다 (`props.from_bot` 아님, 시스템 글 아님)
- 이미 이 봇을 멘션하지 않았고, **다른 누구도 멘션하지 않았다** (`@miu`, `@channel` 등이 있으면 그쪽에 맡김)
- 그 스레드를 이 봇이 "맡고" 있다 (`mode` 참고)

`allowed_channels`, 허용 사용자, 중복 제거, 스레드 답장 같은 나머지 처리는 업스트림을
그대로 탑니다. 확인 중 오류가 나면 업스트림 동작(= 무시)으로 돌아갑니다.

봇끼리 주고받는 글은 대상이 아닙니다. 에이전트끼리는 여전히 명시적 멘션이 필요하므로
"멘션 = 계속, 멘션 없음 = 끝" 규칙이 그대로 유지됩니다.

## 설정

`plugins.entries.mattermost-thread-followup.settings` (선택, 이벤트마다 읽음)

```yaml
plugins:
  entries:
    mattermost-thread-followup:
      settings:
        mode: last_bot   # last_bot: 스레드에서 마지막으로 말한 봇이 나일 때만
                         # participated: 스레드에 내가 한 번이라도 글을 썼으면
        channels: []     # 적용할 채널 ID 목록, 비면 전체
```

`last_bot`이 기본값입니다. 봇 여럿이 같은 스레드에 있어도 방금 대화하던 봇 하나만
답합니다. `participated`로 바꾸면 참여한 봇이 모두 답할 수 있습니다.

## 비용

멘션 없는 스레드 답글이 올 때마다 `GET /posts/{root}/thread`를 한 번 부릅니다. 멘션이 있거나
최상위 글이면 호출하지 않습니다.
