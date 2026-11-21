# OpenCode 설정 파일 규격

> 출처: https://opencode.ai/docs/config/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

- 이름: `opencode.json` 또는 `opencode.jsonc`(주석·trailing comma 허용). `$schema`: `https://opencode.ai/config.json`.
- 위치: 전역 `~/.config/opencode/opencode.json(c)`, 프로젝트 `<dir>/opencode.json(c)` 또는 `<dir>/.opencode/opencode.json(c)`, 시스템(Linux `/etc/opencode`).
- 병합: 작업 디렉터리에서 루트 방향으로 찾고, 먼 것 → 가까운 것 순으로 직접 파일을 병합한 뒤 `.opencode/` 설정을 같은 순서로 병합한다. 충돌하지 않는 값은 유지된다. 시스템·관리 설정이 가장 우선한다.
- 치환(JSON 문자열 안): `{env:NAME}`(미설정이면 빈 문자열), `{file:path}`(설정 파일 기준 상대 경로, `~/`, 절대 경로).
- 주요 최상위 키: `skills`, `mcp`, `plugins`, `agents`, `commands`, `permissions`, `instructions`, `default_agent`. 각 키의 세부 형식은 해당 산출물의 규격 파일(`skill.md`, `mcp-server.md`, `plugin.md`, `agent.md`, `command.md`, `instructions.md`)에 있다.
- V1 형식 주의: `mcp.<name>`, `enabled`, `plugin`, `agent`, `command`, `permission` 객체, `tools`는 구버전 형식이다.
