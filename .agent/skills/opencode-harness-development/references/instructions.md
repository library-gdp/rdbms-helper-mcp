# OpenCode 지침 파일 규격

> 출처: https://opencode.ai/docs/rules/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

- `AGENTS.md`: 전역 `~/.config/opencode/AGENTS.md`와 작업 디렉터리에서 프로젝트 루트까지의 `AGENTS.md`. 같은 디렉터리에 `AGENTS.md`가 없으면 `CLAUDE.md`를 읽는다.
- 설정 `instructions`: 상대 경로·glob·`~/`·절대 경로·URL 배열. `AGENTS.md` 다음에 순서대로 로드된다.
- 환경 변수: `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1`(CLAUDE.md 무시), `OPENCODE_DISABLE_CLAUDE_CODE=1`(`.claude` skill까지 무시), `OPENCODE_DISABLE_PROJECT_CONFIG=1`(프로젝트 AGENTS.md 탐색 생략).
