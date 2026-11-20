# OpenCode 하네스 규격 요약

2026-11-20에 `https://opencode.ai/docs/`의 skills, mcp-servers, config, plugins, agents, commands, rules 페이지를 읽고
정리했다. 문서는 **V2 설정 모델**을 설명하며 일부 V1 형식은 deprecated 또는 미지원으로 표시한다.
작성 전에 대상 OpenCode 버전과 공식 문서를 다시 확인하고, 이 파일과 다르면 공식 문서를 따른다.

## 1. 개발용 에이전트의 자동 탐색 경로 (격리 기준)

`src/` 안에 아래 이름이 생기면 개발용 에이전트가 제품 하네스를 로드할 수 있다. SKILL.md Rule 2의 근거다.

| 에이전트 | 자동으로 읽는 경로 | 비고 |
|---|---|---|
| Claude Code | 시작 디렉터리~저장소 루트의 `.claude/skills/`, 하위 디렉터리의 `.claude/skills/` | 하위 디렉터리 skill은 그 디렉터리 파일을 처음 읽거나 편집할 때 로드 |
| Claude Code | `CLAUDE.md`, `AGENTS.md`(하위 디렉터리 포함), 루트 `.mcp.json`, `.claude/settings*.json` | 하위 디렉터리 지침은 그 디렉터리 파일을 읽을 때 로드 |
| OpenCode | 작업 디렉터리에서 위로 올라가며 `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` | 전역: `~/.config/opencode/skills/`, `~/.claude/skills/`, `~/.agents/skills/` |
| OpenCode | 작업 디렉터리에서 위로 올라가며 `opencode.json(c)`, `.opencode/opencode.json(c)` | `.opencode/` 아래의 `agents/`, `commands/`, `plugins/`도 로드 |
| OpenCode | `AGENTS.md`(없으면 `CLAUDE.md`), 작업 디렉터리 아래의 것은 해당 파일을 읽을 때 로드 | 전역: `~/.config/opencode/AGENTS.md`, 없으면 `~/.claude/CLAUDE.md` |
| Codex | `.agents/skills/`, `AGENTS.md`, `.codex/` | |

## 2. Skill

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

## 3. MCP 서버

```jsonc
{
  "mcp": {
    "servers": {
      "<server-name>": {
        "type": "local",                       // 필수
        "command": ["<bin>", "<arg>"],         // 필수, 배열
        "cwd": "<dir>",
        "environment": { "API_KEY": "{env:API_KEY}" },
        "disabled": false
      },
      "<remote-name>": {
        "type": "remote",
        "url": "https://example.com/mcp",      // Streamable HTTP
        "headers": { "Authorization": "Bearer {env:TOKEN}" },
        "oauth": false                         // 기본은 사용, 객체로 client_id 등 지정 가능
      }
    }
  }
}
```

- 서버별 `timeout`은 숫자가 아니라 `{ "startup", "catalog", "execution" }` 객체(ms)다. 기본 30s / 30s / 12h.
- 그 밖의 서버 옵션: `codemode`(기본 `true`), `protocol`, `pool`. Code Mode에서는 tool이 `tools.<server>.<tool>(...)`로 보이고, `codemode: false`면 tool을 직접 노출한다.
- tool 이름은 `<server>_<tool>`이며 영문·숫자·`_`·`-` 외의 문자는 `_`로 바뀐다. 권한 규칙도 이 이름으로 매칭한다(예: `{ "action": "<server>_*", "resource": "*", "effect": "deny" }`).
- MCP prompt는 `<server>:<prompt>` command가 된다.
- Claude Code `.mcp.json`과의 차이: `mcpServers` 대신 `mcp.servers`, `env` 대신 `environment`, `type` 필수, 치환은 `$VAR`가 아니라 `{env:VAR}`, 활성화는 `disabled`.

## 4. 설정 파일

- 이름: `opencode.json` 또는 `opencode.jsonc`(주석·trailing comma 허용). `$schema`: `https://opencode.ai/config.json`.
- 위치: 전역 `~/.config/opencode/opencode.json(c)`, 프로젝트 `<dir>/opencode.json(c)` 또는 `<dir>/.opencode/opencode.json(c)`, 시스템(Linux `/etc/opencode`).
- 병합: 작업 디렉터리에서 루트 방향으로 찾고, 먼 것 → 가까운 것 순으로 직접 파일을 병합한 뒤 `.opencode/` 설정을 같은 순서로 병합한다. 충돌하지 않는 값은 유지된다. 시스템·관리 설정이 가장 우선한다.
- 치환(JSON 문자열 안): `{env:NAME}`(미설정이면 빈 문자열), `{file:path}`(설정 파일 기준 상대 경로, `~/`, 절대 경로).
- 주요 최상위 키: `skills`, `mcp`, `plugins`, `agents`, `commands`, `permissions`, `instructions`, `default_agent`.
- V1 형식 주의: `mcp.<name>`, `enabled`, `plugin`, `agent`, `command`, `permission` 객체, `tools`는 구버전 형식이다.

## 5. Plugin

- 탐색: `.opencode/plugins/`(`.ts`/`.js` 파일과 바로 아래 패키지 디렉터리), `~/.config/opencode/plugins/`. 프로젝트 루트 `opencode.json` 옆의 `plugins/`는 자동 탐색하지 않는다.
- 설정 `plugins` 배열: npm 이름(`"name"`, `"name@1.2.0"`, `"@scope/name"`), 로컬 디렉터리 경로, 또는 `{ "package": "...", "options": { ... } }`. `-<id>`로 비활성화.
- 형식(문서 예시):

  ```ts
  import { Plugin } from "@opencode/plugin"

  export default Plugin.define({
    id: "example",
    async setup(ctx) {
      // ctx.options, ctx.storage, ctx.tool, ctx.session, ctx.permission, ctx.event ...
    },
  })
  ```

- tool 등록: `ctx.tool.transform((editor) => editor.add({ name, description, input: <JSON Schema>, options: { namespace }, execute }))`. namespace가 있으면 `<namespace>_<name>`.
- hook: `ctx.session.hook(...)`, `ctx.tool.hook("execute.before" | "execute.after", ...)`, `ctx.permission.hook("evaluate", ...)`, `ctx.shell.hook("create.before", ...)`, 이벤트는 `ctx.event.subscribe()`.

## 6. Agent

- 위치: `.opencode/agents/<id>.md`, `~/.config/opencode/agents/<id>.md`. 하위 경로는 ID에 포함된다(`team/reviewer`).
- frontmatter: `description`, `mode`(`primary` | `subagent` | `all`), `model`(`provider/model`, 선택적으로 `#variant`), `permissions`(배열), `steps`, `hidden`, `color`, `disabled`. 본문이 system prompt다.
- JSON은 `agents.<id>`에 같은 필드와 `system` 문자열. `temperature`, `prompt`, `permission`, `tools`, `maxSteps` 같은 V1 필드는 쓰지 않는다.

## 7. Command

- 위치: `.opencode/commands/*.md`, `~/.config/opencode/commands/*.md`(단수 `command/`는 구버전 호환).
- frontmatter: `description`, `agent`, `model`, `subagent`(`subtask`는 deprecated 별칭). 본문이 template이다.
- 치환: `$ARGUMENTS`, `$1`, `$2`, …(마지막 번호가 나머지 인자를 모두 받음). `` !`cmd` ``는 셸 출력으로 치환되며 agent 권한 흐름 밖에서 실행된다. 저장된 template의 `@path`는 확장되지 않는다.

## 8. 지침 파일

- `AGENTS.md`: 전역 `~/.config/opencode/AGENTS.md`와 작업 디렉터리에서 프로젝트 루트까지의 `AGENTS.md`. 같은 디렉터리에 `AGENTS.md`가 없으면 `CLAUDE.md`를 읽는다.
- 설정 `instructions`: 상대 경로·glob·`~/`·절대 경로·URL 배열. `AGENTS.md` 다음에 순서대로 로드된다.
- 환경 변수: `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1`(CLAUDE.md 무시), `OPENCODE_DISABLE_CLAUDE_CODE=1`(`.claude` skill까지 무시), `OPENCODE_DISABLE_PROJECT_CONFIG=1`(프로젝트 AGENTS.md 탐색 생략).

## 9. 격리된 통합 검증 예시

이 저장소 밖의 임시 디렉터리를 만들고 그 안에 아래 설정을 둔 뒤 OpenCode를 실행한다. 경로는 절대 경로로 쓴다.

```jsonc
// <임시 디렉터리>/opencode.jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "skills": ["<repo 절대 경로>/src/skills"],
  "mcp": {
    "servers": {
      "<server-name>": {
        "type": "local",
        "command": ["<bin>", "<repo 절대 경로>/src/mcp/<server-name>/<entry>"]
      }
    }
  }
}
```

- 사용자 전역의 `~/.claude/skills`, `~/.agents/skills`, `~/.config/opencode/skills`도 OpenCode가 읽는다. 결과가 섞이면 `OPENCODE_DISABLE_CLAUDE_CODE=1`을 쓰고, 나머지 전역 skill이 남아 있다는 사실을 보고에 적는다.
- 사용자의 전역 설정 파일은 수정하지 않는다.
