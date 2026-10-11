# progress-codeblock

게이트웨이의 **툴 진행 말풍선**을 코드블록 하나로 감싸고, 마지막 N건만 보이는
슬라이딩 윈도우로 만듭니다.

```
… 외 5건
💻 실행 중 for p in sella delphine miu + 명령 5개
💻 실행 중 hermes gateway restart + 명령 3개
📖 읽는 중 config.yaml
```

업스트림은 한 턴의 툴 줄을 전부 `"\n".join`해서 매번 말풍선 전체를 다시 보냅니다.
긴 턴이면 말풍선이 `💻 실행 중 ...` 줄로 끝없이 늘어나는데, 이를 감싸거나 줄이는
`display` 설정은 없습니다. 펜스는 `terminal` 툴 명령 하나하나에만, 그것도
`supports_code_blocks` 어댑터(Discord 등 — Mattermost는 아님)에서만 붙습니다.

## 설치

```bash
hermes plugins install Sn-Kinos/hermes-plugins/progress-codeblock
hermes plugins enable progress-codeblock
```

## 설정

`config.yaml`의 `plugins.entries.progress-codeblock.settings` 아래에 둡니다. 전부
선택이며, 호출마다 읽으므로 바꾸면 재시작 없이 다음 말풍선부터 적용됩니다.

```yaml
plugins:
  entries:
    progress-codeblock:
      settings:
        codeblock: true                  # 말풍선을 코드블록으로 감싸기
        window: 3                        # 보여줄 건수, 0 = 제한 없음
        show_hidden: true                # 첫 줄에 밀려난 건수 표시
        hidden_format: "… 외 {count}건"  # 그 줄의 문구
        platforms: [discord, mattermost] # 적용할 플랫폼 키
```

## 동작 방식

`gateway.run_turn_runner`의 말풍선 소유 클래스(`TurnRunner`)에 붙습니다.

| seam | 하는 일 |
|---|---|
| `_progress_absorb` | 줄을 추가한 직후 버퍼를 마지막 N건으로 자르고, 잘린 수를 센다 |
| `_reset_progress_bubble` | 새 말풍선이 시작되면 잘린 수를 0으로 |
| `_progress_terminal_blocks` | 대상 플랫폼에선 명령별 펜스를 끈다 (바깥 펜스 안에 중첩되면 깨짐) |
| `_send_progress_text` · `_edit_progress_message` | 보내는 텍스트를 헤더 + 펜스로 감싼다 |

- 문자열이 아니라 **줄 목록**에서 자르므로 여러 줄짜리 항목도 통째로 남거나 빠집니다.
- 줄 안의 ```` ``` ````는 백틱 사이에 zero-width space를 넣어 블록을 닫지 못하게 합니다.
- Discord의 URL 미리보기 `[label](<url>)`는 코드블록 안에서 렌더링되지 않으므로
  label만 남깁니다.
- **편집 가능한 진행 말풍선만** 건드립니다. Slack 태스크 카드, 최종 답변, 그 밖의
  메시지는 그대로입니다. `tool_progress_grouping: separate`(툴마다 별도 메시지)면
  윈도우 헤더 없이 각 메시지만 감쌉니다.

## 알아둘 점

- 턴이 끝나도 말풍선엔 마지막 N건만 남습니다. 앞선 툴 호출은 채팅에서 볼 수 없습니다.
- 편집 간격이 1.5초라, 그 사이 지나간 툴은 화면에 한 번도 안 나오고 밀려날 수 있습니다.
- 💬 thinking 줄, `(×2)` 중복 표시도 같은 말풍선의 항목이라 함께 감싸지고 윈도우에 셉니다.
