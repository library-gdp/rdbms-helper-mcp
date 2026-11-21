# OpenCode MCP 서버 규격

> 출처: https://opencode.ai/docs/mcp-servers/ (2026-11-20 확인, V2 설정 모델).
> 대상 OpenCode 버전의 공식 문서와 다르면 공식 문서를 따르고, 차이를 사용자에게 알린다.

설정 파일 자체의 이름·위치·치환 규칙은 `config.md`에 있다.

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
