# OpenCode Command 규격

> 출처: https://opencode.ai/docs/commands/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

- 위치: `.opencode/commands/*.md`, `~/.config/opencode/commands/*.md`(단수 `command/`는 구버전 호환).
- frontmatter: `description`, `agent`, `model`, `subagent`(`subtask`는 deprecated 별칭). 본문이 template이다.
- 치환: `$ARGUMENTS`, `$1`, `$2`, …(마지막 번호가 나머지 인자를 모두 받음). `` !`cmd` ``는 셸 출력으로 치환되며 agent 권한 흐름 밖에서 실행된다. 저장된 template의 `@path`는 확장되지 않는다.
