# 격리된 OpenCode 통합 검증

SKILL.md Rule 6의 절차 예시다. 설정 키 형식은 `config.md`, `skill.md`, `mcp-server.md`를 따른다.

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

- 사용자 전역의 `~/.claude/skills`, `~/.agents/skills`, `~/.config/opencode/skills`도 OpenCode가 읽는다. 결과가 섞이면 `OPENCODE_DISABLE_CLAUDE_CODE=1`(`instructions.md` 참고)을 쓰고, 나머지 전역 skill이 남아 있다는 사실을 보고에 적는다.
- 사용자의 전역 설정 파일은 수정하지 않는다.
