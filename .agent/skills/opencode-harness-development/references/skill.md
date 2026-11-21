# OpenCode Skill 규격

> 출처: https://opencode.ai/docs/skills/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

- **탐색 위치**: 프로젝트 `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`(작업 디렉터리에서 프로젝트 루트까지 각 단계), 전역 `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/`.
  설정의 최상위 `skills` 배열로 경로(작업 디렉터리 기준 상대 경로, `~/`, 절대 경로)나 `http(s)://` 카탈로그(`index.json`)를 추가할 수 있다.
- **형식**: 디렉터리에 `SKILL.md`가 있으면 skill 하나다. 숨김 디렉터리와 `node_modules`는 건너뛴다. skill ID는 경로에서 정해진다.
- **frontmatter**: `name`(표시 이름), `description`(모델에게 보이는 요약, 없으면 모델에게 알리지 않음), `license`, `compatibility`, `metadata`.
  모델 자동 호출을 막으려면 `disable-model-invocation: true` 또는 `metadata.opencode/autoinvoke: false`.
- **검증 규칙**: 문서는 이식성을 위해 1–64자 kebab-case ID(`^[a-z0-9]+(-[a-z0-9]+)*$`)와 디렉터리 이름 = `name`을 권장한다. V2는 이를 강제하지 않지만 Claude Code·Codex 호환을 위해 지킨다.
  description 길이 제한은 OpenCode 문서에 없다. Agent Skills 호환 상한인 1024자를 지킨다.
- **로드 방식**: 매 step마다 허용된 skill의 ID, 이름, description만 모델에게 보인다. 모델이 `skill` tool(`{"id": "<skill-id>"}`)을 호출하면 frontmatter를 뗀 본문, skill base 디렉터리, 최대 10개의 supporting file 경로가 추가된다. supporting file 내용은 자동으로 읽지 않는다. 사용자는 프롬프트에 `@<skill-id>`로 직접 로드할 수 있다.
- **우선순위**: 같은 ID면 나중에 등록된 것이 이긴다. 순서: 내장 → `.claude/skills` → `.agents/skills` → `~/.config/opencode/skills` → 프로젝트 `.opencode/skills` → 설정 `skills` 항목.
- **권한**: `permissions` 배열에 `{ "action": "skill", "resource": "<skill-id 또는 glob>", "effect": "allow" | "ask" | "deny" }`. 마지막으로 매칭된 규칙이 이긴다. agent별로는 `agents.<id>.permissions`.
