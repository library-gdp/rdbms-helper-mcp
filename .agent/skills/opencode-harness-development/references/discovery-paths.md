# 개발용 에이전트의 자동 탐색 경로 (격리 기준)

> 2026-11-20 기준. OpenCode 항목은 공식 문서의 skills, config, rules 페이지(V2 설정 모델)를 요약했다.
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

`src/` 안에 아래 이름이 생기면 개발용 에이전트가 제품 하네스를 로드할 수 있다. SKILL.md Rule 2의 근거다.

| 에이전트 | 자동으로 읽는 경로 | 비고 |
|---|---|---|
| Claude Code | 시작 디렉터리~저장소 루트의 `.claude/skills/`, 하위 디렉터리의 `.claude/skills/` | 하위 디렉터리 skill은 그 디렉터리 파일을 처음 읽거나 편집할 때 로드 |
| Claude Code | `CLAUDE.md`, `AGENTS.md`(하위 디렉터리 포함), 루트 `.mcp.json`, `.claude/settings*.json` | 하위 디렉터리 지침은 그 디렉터리 파일을 읽을 때 로드 |
| OpenCode | 작업 디렉터리에서 위로 올라가며 `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` | 전역: `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` |
| OpenCode | 작업 디렉터리에서 위로 올라가며 `opencode.json(c)`, `.opencode/opencode.json(c)` | `.opencode/` 아래의 `agents/`, `commands/`, `plugins/`도 로드 |
| OpenCode | `AGENTS.md`(없으면 `CLAUDE.md`), 작업 디렉터리 아래의 것은 해당 파일을 읽을 때 로드 | 전역: `~/.config/opencode/AGENTS.md`, 없으면 `~/.claude/CLAUDE.md` |
| Codex | `.agents/skills/`, `AGENTS.md`, `.codex/` | |
