# OpenCode Plugin 규격

> 출처: https://opencode.ai/docs/plugins/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

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
