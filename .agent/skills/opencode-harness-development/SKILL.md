---
name: opencode-harness-development
description: 이 저장소의 제품인 OpenCode 하네스(Skill, MCP 서버, Plugin, Agent, Command, opencode 설정)를 `src/` 아래에서 설계·구현·수정·리뷰·테스트할 때 따르는 규칙. Use when creating, editing, reviewing, or testing any OpenCode-targeted artifact or any file under `src/` — e.g. "ERD로 그래프를 만드는 skill 만들어줘", "MCP tool 추가해줘", "OpenCode plugin/agent/command 작성". Do NOT use for meta-harness work on the coding agent's own setup (`AGENTS.md`, `.agent/`, `.claude/`, `.agents/`, `.opencode/`, `opencode.json`, `.mcp.json`, `script/`, guardrails) or for tasks unrelated to the OpenCode product.
---

# OpenCode 하네스 개발 Rule

## 이 스킬의 역할

이 저장소에는 성격이 다른 하네스 두 개가 공존한다. 이 스킬은 둘을 섞지 않고 **제품 하네스**를 개발하기 위한 규칙이다.

| 구분 | 무엇인가 | 위치 | 누가 로드하는가 |
|---|---|---|---|
| 제품 하네스 | OpenCode 사용자에게 제공할 Skill, MCP 서버, Plugin, Agent, Command, 설정 조각 | `src/` | 배포·설치된 뒤의 OpenCode |
| 메타 하네스 | 이 저장소를 개발하는 코딩 에이전트(현재 Claude Code)의 설정 | `AGENTS.md`, `.agent/` 정본과 그 링크(`.claude/`, `.agents/`, `.opencode/`, `opencode.json`, `.mcp.json`, `CLAUDE.md`) | 이 저장소를 연 개발용 에이전트 |

이 스킬이 하는 일:

- 제품 하네스를 `src/` 아래에 두고, 메타 하네스가 그것을 로드하지 않게 격리한다.
- OpenCode 규격(버전 포함)에 맞춰 각 산출물을 작성하는 기준을 제시한다.
- 메타 하네스와 격리된 환경에서 검증하는 방법을 제시한다.

이 스킬이 하지 않는 일:

- 메타 하네스(`.agent/` 등)를 수정하는 작업의 규칙을 정하지 않는다. 그 작업에는 이 스킬을 적용하지 않는다.
- 언어·런타임·MCP SDK·배포 방식을 정하지 않는다. `src/`의 기존 선택을 따르고, 없으면 사용자에게 확인한다.
- 제품 도메인(예: ERD 해석 규칙, 그래프 모델)을 정의하지 않는다. 확정된 요구사항과 문서를 따른다.

## 참고 문서

OpenCode 규격과 격리 기준은 `references/`에 주제별 파일로 나눠 두었다. 산출물을 만들거나 고치기 전에 아래 표에서 해당 파일만 골라 읽는다.

| 파일 | 내용 | 읽는 시점 |
|---|---|---|
| `references/discovery-paths.md` | 개발용 에이전트(Claude Code, OpenCode, Codex)의 자동 탐색 경로 | `src/`의 파일·디렉터리 이름을 정할 때 (Rule 2) |
| `references/skill.md` | Skill 탐색 위치, frontmatter, 로드 방식, 우선순위, 권한 | Skill 작성·수정 |
| `references/mcp-server.md` | MCP 서버 설정 형식, timeout, tool 이름 규칙, `.mcp.json`과의 차이 | MCP 서버 작성·수정, 설정에 MCP 등록 |
| `references/plugin.md` | Plugin 탐색, 등록, 코드 형식, tool 등록, hook | Plugin 작성·수정 |
| `references/agent.md` | Agent 위치, frontmatter, JSON 형식 | Agent 작성·수정 |
| `references/command.md` | Command 위치, frontmatter, template 치환 | Command 작성·수정 |
| `references/instructions.md` | `AGENTS.md`·`instructions` 로드 규칙, 비활성화 환경 변수 | 지침 파일 배포 설계, 통합 검증 환경 구성 |
| `references/config.md` | 설정 파일 이름·위치·병합·치환, V1 형식 주의 | 설정 조각 작성, 다른 산출물을 설정에 등록할 때 |
| `references/isolated-verification.md` | 저장소 밖 임시 디렉터리에서의 OpenCode 통합 검증 예시 | 통합 검증 (Rule 6) |

## 핵심 Rule

### Rule 1. 제품 하네스는 `src/` 아래에만 둔다

- 제품 하네스의 모든 파일(코드, `SKILL.md`, 설정 조각, 테스트, fixture)은 `src/` 아래에 만든다.
- `.agent/`, `.claude/`, `.agents/`, `.opencode/`, `.codex/`, 루트 `opencode.json(c)`, `.mcp.json`, `AGENTS.md`에 제품 하네스를 추가하거나 등록하지 않는다.
- 반대로 메타 하네스 설정을 `src/`에 두지 않는다.

### Rule 2. 메타 하네스가 제품 하네스를 로드하지 못하게 한다

개발용 에이전트는 정해진 이름의 경로를 자동으로 탐색한다. `src/` 안에 그 이름이 생기면 제품 하네스가 개발용 에이전트의 context에 섞인다.

- Claude Code는 시작 디렉터리 아래의 `.claude/skills/`를 그 디렉터리의 파일을 처음 읽거나 편집할 때 로드하고, 하위 디렉터리의 `CLAUDE.md`·`AGENTS.md`도 같은 방식으로 읽는다.
- OpenCode는 작업 디렉터리에서 위로 올라가며 `.opencode/`, `.claude/skills/`, `.agents/skills/`, `opencode.json(c)`, `AGENTS.md`를 읽는다. Codex는 `.agents/skills/`를 읽는다.
- 에이전트별 세부 경로는 `references/discovery-paths.md`에 있다.

따라서 `src/` 아래 **어느 깊이에도** 다음 이름을 만들지 않는다.

```text
.claude/  .agents/  .opencode/  .codex/  AGENTS.md  CLAUDE.md  opencode.json  opencode.jsonc  .mcp.json
```

OpenCode에 설치될 때 이런 이름이 필요하더라도 `src/`에는 중립적인 이름(아래 기본 레이아웃)으로 두고, 설치 단계에서 대상 위치에 배치한다. 설치 방식은 아직 정해지지 않았으므로 필요해지면 사용자에게 확인한다.

추가로 금지:

- 테스트 편의를 위해 `src/`의 산출물을 `.agent/skills/` 등에 복사하거나 링크하는 것
- 개발 중인 MCP 서버를 `.agent/mcp.json`, `.mcp.json`, `claude mcp add`, 사용자 전역 설정(`~/.claude*`, `~/.config/opencode/`)에 등록하는 것 — 사용자가 명시적으로 요청한 경우만 예외

작업을 마칠 때 다음 명령의 출력이 비어 있어야 한다(`src/`가 없으면 아무것도 출력하지 않는다).

```bash
[ -d src ] && find src \( -name .claude -o -name .agents -o -name .opencode -o -name .codex \
  -o -name AGENTS.md -o -name CLAUDE.md -o -name 'opencode.json*' -o -name .mcp.json \) -print
```

### Rule 3. 대상 OpenCode 버전의 규격을 먼저 확인한다

OpenCode 설정 형식은 버전에 따라 크게 바뀌었다(예: `mcp.<name>` → `mcp.servers.<name>`, `enabled` → `disabled`, `permission` 객체 → `permissions` 배열, `plugin` → `plugins`). 기억이나 다른 프로젝트의 예시로 작성하지 않는다.

- 설정·Plugin 코드를 작성하기 전에 대상 버전(`opencode --version`, 또는 사용자가 지정한 버전)과 공식 문서(`https://opencode.ai/docs/`)를 확인한다.
- `references/`의 규격 파일은 작성 시점(2026-11-20)의 공식 문서를 요약한 것이다. 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.
- `.agent/guardrails/opencode.json`은 메타 하네스용 생성 파일이다. 제품 설정의 참고 예시로 쓰지 않는다.

### Rule 4. 결정적인 로직은 코드로, 판단과 절차는 Skill로 나눈다

- 파싱, 변환, 검증, 그래프 구축처럼 같은 입력에 같은 결과가 나와야 하는 로직은 MCP tool 또는 Skill의 `scripts/`에 코드로 구현하고 테스트한다. 모델이 프롬프트만으로 수행하게 하지 않는다.
- Skill 본문에는 언제 어떤 tool·script를 어떤 순서로 쓰는지, 입력이 모호할 때 무엇을 사용자에게 확인하는지를 쓴다.
- 산출물 하나가 여러 책임을 지면 나눈다. Skill 하나에 무관한 작업을 묶지 않고, MCP tool 하나가 여러 동작을 flag로 분기하지 않게 한다.

### Rule 5. 산출물별 작성 기준을 지킨다

**Skill** (`src/skills/<skill-id>/`)

- `<skill-id>`는 1–64자 kebab-case(`^[a-z0-9]+(-[a-z0-9]+)*$`)이고 디렉터리 이름과 frontmatter `name`이 같다.
- `description`은 필수다. 없으면 OpenCode가 모델에게 skill을 알리지 않는다. 핵심 용도를 맨 앞에 두고 언제 쓰는지와 쓰지 않는지를 쓴다. 이식성을 위해 1024자 이하로 한다.
- frontmatter는 `name`, `description`, `license`, `compatibility`, `metadata`만 쓴다. Claude Code 전용 필드(`paths`, `allowed-tools`, `context` 등)는 OpenCode가 해석하지 않는다.
- 본문은 500줄 이하로 유지하고 세부 내용은 `references/`, 실행 코드는 `scripts/`로 분리해 상대 경로로 참조한다. OpenCode는 supporting file을 자동으로 읽지 않으므로 본문에서 언제 읽을지 지시한다.
- 세부 규격: `references/skill.md`

**MCP 서버** (`src/mcp/<server-name>/`)

- 서버마다 독립된 패키지(매니페스트, 소스, 테스트)로 만든다.
- OpenCode는 tool을 `<server>_<tool>`로 노출하고 영문·숫자·`_`·`-` 외의 문자를 `_`로 바꾼다. 서버·tool 이름은 짧은 영문 snake_case 또는 kebab-case로 정한다.
- tool 입력은 JSON Schema로 엄격하게 정의한다(`required`, `additionalProperties: false`). description에는 무엇을 하고 언제 쓰는지와 출력 형태를 쓴다.
- 오류는 모델이 고칠 수 있는 메시지로 반환한다(어느 입력이 왜 잘못됐는지).
- 비밀값을 코드나 설정 조각에 넣지 않는다. OpenCode 설정에서는 `{env:VAR}` 치환을 쓴다.
- local(stdio)과 remote(Streamable HTTP) 중 무엇으로 제공할지는 설계 결정이다. 정해지지 않았으면 사용자에게 확인한다.
- 세부 규격: `references/mcp-server.md`

**Plugin / Agent / Command / 설정 조각**

- 기본 레이아웃의 디렉터리에 두고, 형식은 각 규격 파일(`references/plugin.md`, `agent.md`, `command.md`, `config.md`)과 대상 버전의 공식 문서를 따른다.
- 설정 조각의 파일 이름은 `opencode.json(c)`로 하지 않는다(Rule 2). 예: `src/config/opencode.example.jsonc`.

### Rule 6. 메타 하네스와 격리된 환경에서 검증한다

- MCP 서버와 script는 단위 테스트로 검증한다. 가능하면 실제 MCP client(예: MCP Inspector)로 tool 목록과 호출 결과도 확인한다.
- OpenCode 통합 검증은 **이 저장소 밖의 임시 디렉터리**에서 한다. 그 디렉터리의 `opencode.json(c)`에서 `src/` 산출물을 절대 경로로 참조한다(예: `skills` 배열, `mcp.servers`). 이 저장소 안에서 OpenCode를 실행하면 메타 하네스의 `AGENTS.md`와 `.agent/skills`가 함께 로드되어 결과를 신뢰할 수 없다. 설정 예시는 `references/isolated-verification.md`에 있다.
- 사용자의 전역 OpenCode 설정을 수정하지 않는다.
- 실행하지 못한 검증은 통과로 보고하지 않는다. 무엇을 실행했고 무엇을 실행하지 못했는지 구분해 보고한다.

### Rule 7. 확정된 설계 결정은 문서화로 넘긴다

기술 스택, 배포·설치 방식, MCP 전송 방식, `src/` 레이아웃 변경처럼 되돌리기 어려운 결정이 확정되면 `project-documentation` 스킬로 문서 영향을 판정한다.

## 기본 `src/` 레이아웃

`src/`에 이미 관례가 있으면 그것을 따른다. 비어 있으면 아래를 따르고, **필요한 디렉터리만** 만든다.

```text
src/
  skills/<skill-id>/            # SKILL.md, references/, scripts/
  mcp/<server-name>/            # MCP 서버 패키지 (매니페스트, 소스, 테스트)
  plugins/<plugin-id>/          # OpenCode plugin
  agents/<agent-id>.md          # OpenCode agent
  commands/<command-name>.md    # OpenCode command
  config/                       # 배포용 설정 조각 (opencode.json(c) 이름 금지)
```

## 작업 절차

1. **분류** — 요청이 제품 하네스 작업인지 확인한다. 메타 하네스 작업이면 이 스킬을 적용하지 않는다. 둘 다 포함되면 나눠서 진행한다.
2. **현황 파악** — `src/`의 기존 산출물, 언어·런타임, 레이아웃 관례를 확인한다.
3. **규격 확인** — [참고 문서](#참고-문서) 표에서 해당 산출물의 규격 파일과 대상 버전의 공식 문서를 확인한다(Rule 3).
4. **불확실성 해소** — 요구사항, 기술 스택, 전송 방식, 배포 방식 중 정해지지 않은 것이 구현에 필요하면 추측하지 않고 사용자에게 확인한다.
5. **구현** — `src/` 아래에 작성한다(Rule 1, 4, 5).
6. **격리 점검** — Rule 2의 `find` 명령 출력이 비어 있는지, 메타 하네스 경로에 변경이 없는지(`git status`) 확인한다.
7. **검증** — Rule 6에 따라 테스트한다.
8. **보고** — 만든·바꾼 산출물, 검증 결과(실행한 것 / 못 한 것), 남은 결정 사항을 보고한다.
