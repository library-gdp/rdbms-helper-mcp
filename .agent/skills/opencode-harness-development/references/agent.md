# OpenCode Agent 규격

> 출처: https://opencode.ai/docs/agents/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

- 위치: `.opencode/agents/<id>.md`, `~/.config/opencode/agents/<id>.md`. 하위 경로는 ID에 포함된다(`team/reviewer`).
- frontmatter: `description`, `mode`(`primary` | `subagent` | `all`), `model`(`provider/model`, 선택적으로 `#variant`), `permissions`(배열), `steps`, `hidden`, `color`, `disabled`. 본문이 system prompt다.
- JSON은 `agents.<id>`에 같은 필드와 `system` 문자열. `temperature`, `prompt`, `permission`, `tools`, `maxSteps` 같은 V1 필드는 쓰지 않는다.
