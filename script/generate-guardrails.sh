#!/usr/bin/env bash
#
# Render the agent guardrails from .agent/guardrails/protected-branches into
# the permission files each coding agent reads.
#
#   .agent/guardrails/claude-settings.json  -> .claude/settings.json      (Claude Code)
#   .agent/guardrails/opencode.json         -> opencode.json              (opencode)
#   .agent/guardrails/codex.rules           -> .codex/rules/guardrails.rules (Codex)
#
# The links are created by script/setup-agent-links.sh / .ps1. This script only
# writes the three files under .agent/guardrails/, which are committed.
#
# Guardrails:
#   1. No direct push to a protected branch, and no push whose target branch
#      cannot be read from the command itself (bare `git push`, `HEAD`,
#      `--all`, ...), since such a push may land on a protected branch.
#   2. No pull request merge.
#   3. No history rewrite: no `git commit --amend` and no force push
#      (`-f`, `--force*`, `+<refspec>`).
#   4. No change to agent settings files: the guardrail files, this script,
#      Claude Code / opencode / Codex settings. Claude Code denies file tools
#      on those paths; Claude Code and opencode deny any shell command that
#      names them.
#
# Rules 1-4 are deny rules, so they apply in every permission mode, including
# Claude Code's bypassPermissions and auto modes. Claude Code also gets allow
# rules for `git add`, `git commit` and `git push`, so other commits and pushes
# run without a prompt; a deny rule still wins over them.
#
# Usage: script/generate-guardrails.sh   (runnable from any working directory)
# On Windows, run it from Git Bash.

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(cd -- "$script_dir/.." && pwd -P)"
guardrails_dir="$project_root/.agent/guardrails"
branches_file="$guardrails_dir/protected-branches"

if [ ! -f "$branches_file" ]; then
  printf '[ERROR] %s does not exist\n' "${branches_file#"$project_root"/}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Protected branches
# ---------------------------------------------------------------------------

branches=()
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"
  line="${line//[[:space:]]/}"
  [ -n "$line" ] || continue
  # Names end up inside JSON strings and glob patterns unescaped, so only
  # characters that need no escaping in either are accepted.
  if ! [[ "$line" =~ ^[A-Za-z0-9._/*-]+$ ]]; then
    printf '[ERROR] invalid branch name: %s\n' "$line" >&2
    exit 1
  fi
  branches+=("$line")
done <"$branches_file"

if [ "${#branches[@]}" -eq 0 ]; then
  printf '[ERROR] %s lists no branches\n' "${branches_file#"$project_root"/}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Shell command patterns, shared by Claude Code and opencode
#
# Both match the whole command text, `*` matches any text including spaces,
# and both split compound commands (&&, ;, |, ...) before matching.
# ---------------------------------------------------------------------------

# `git -C <dir> push` and `git -c <k>=<v> push` are the same push.
push_prefixes=('git push' 'git -C * push' 'git -c * push')
commit_prefixes=('git commit' 'git -C * commit' 'git -c * commit')

# Short-flag spellings of a force push: `-f` alone or bundled with one of the
# other flag-only short options (-u, -v, -q, -n).
force_short_flags=(-f -fu -uf -fv -vf -fq -qf -fn -nf)

shell_patterns() {
  local p b f

  for p in "${push_prefixes[@]}"; do
    # Target branch is spelled out: <b>, +<b>, <src>:<b>, :<b>, refs/heads/<b>.
    for b in "${branches[@]}"; do
      printf '%s\n' \
        "$p * $b" "$p * $b *" \
        "$p * +$b" "$p * +$b *" \
        "$p *:$b" "$p *:$b *" \
        "$p *refs/heads/$b" "$p *refs/heads/$b *"
    done

    # Target branch is implied by the current branch or covers every branch.
    printf '%s\n' \
      "$p" \
      "$p origin" "$p * origin" \
      "$p * HEAD" "$p * HEAD *" \
      "$p * +HEAD" "$p * +HEAD *" \
      "$p * @" "$p * @ *" \
      "$p *--all*" "$p *--branches*" "$p *--mirror*"

    # Force push to any branch: --force, --force-with-lease, --force-if-includes,
    # -f (alone or bundled), and a `+<refspec>`.
    printf '%s\n' "$p *--force*" "$p +*" "$p * +*"
    for f in "${force_short_flags[@]}"; do
      printf '%s\n' "$p $f" "$p $f *" "$p * $f" "$p * $f *"
    done
  done

  # Amending a commit. git accepts any unambiguous prefix of a long option,
  # and `--am` is the shortest prefix of `--amend`.
  for p in "${commit_prefixes[@]}"; do
    printf '%s\n' "$p *--am*"
  done

  # Pushing through the GitHub API instead of git.
  for b in "${branches[@]}"; do
    printf '%s\n' "gh api *refs/heads/$b*" "gh api *branch=$b*"
  done
  printf '%s\n' "gh api *merges*" "gh api *force=true*"

  # Pull request merge.
  printf '%s\n' \
    'gh pr merge *' \
    'gh * pr merge *' \
    'gh api *pulls/*/merge*' \
    'gh api *mergePullRequest*' \
    'gh api *enablePullRequestAutoMerge*' \
    'glab mr merge *'
}

# Shell commands that name an agent settings file, shared by Claude Code and
# opencode. Any such command is denied, reads included, because a pattern
# cannot tell a read from a write. Use the Read tool to look at these files.
settings_shell_patterns() {
  printf '%s\n' \
    '*.agent/guardrails*' \
    '*protected-branches*' \
    '*claude-settings.json*' \
    '*codex.rules*' \
    '*generate-guardrails*' \
    '*.claude/settings*' \
    '*.claude.json*' \
    '*managed-settings*' \
    '*opencode.json*' \
    '*.config/opencode*' \
    '*.codex*'
}

# Agent settings files, as Claude Code file permission paths. `Edit(path)`
# covers every file-writing tool (Edit, Write, NotebookEdit).
#   /path    relative to the project root
#   **/path  relative to the working directory, at any depth
#   ~/path   relative to the home directory
#   //path   absolute
settings_edit_paths() {
  local rel
  for rel in \
    '.agent/guardrails/**' \
    'script/generate-guardrails.sh' \
    '.claude/settings.json' \
    '.claude/settings.local.json' \
    'opencode.json' \
    'opencode.jsonc' \
    '.opencode/opencode.json' \
    '.opencode/opencode.jsonc' \
    '.codex/**'; do
    printf '%s\n' "/$rel" "**/$rel"
  done
  printf '%s\n' \
    '~/.claude/settings.json' \
    '~/.claude/settings.local.json' \
    '~/.claude.json' \
    '~/.config/opencode/**' \
    '~/.codex/**' \
    '//etc/claude-code/**'
}

# MCP tools that merge a pull request, on any server (Claude Code only).
mcp_patterns() {
  printf '%s\n' 'mcp__*__*merge_pull_request*' 'mcp__*__*auto_merge*'
}

# Commands Claude Code may run without a prompt. Deny rules above still win.
allow_patterns() {
  printf '%s\n' 'git add *' 'git commit *' 'git push *'
}

# Print lines as JSON array items: `<indent>"<prefix><line><suffix>",`
# with the trailing comma dropped on the last item.
json_items() {
  local indent="$1" prefix="$2" suffix="$3"
  sed -e "s|.*|$indent\"$prefix&$suffix\",|" -e '$ s|,$||'
}

header_note='GENERATED by script/generate-guardrails.sh from .agent/guardrails/protected-branches. Do not edit by hand.'

# ---------------------------------------------------------------------------
# Claude Code: .claude/settings.json
#
# Bash and PowerShell are separate tools with separate rules. Deny rules match
# past leading env assignments and wrappers such as `timeout`.
# ---------------------------------------------------------------------------

render_claude() {
  printf '{\n'
  printf '  "$schema": "https://json.schemastore.org/claude-code-settings.json",\n'
  printf '  "permissions": {\n'
  printf '    "allow": [\n'
  {
    allow_patterns | sed -e 's|.*|Bash(&)|'
    allow_patterns | sed -e 's|.*|PowerShell(&)|'
  } | json_items '      ' '' ''
  printf '    ],\n'
  printf '    "deny": [\n'
  {
    { shell_patterns; settings_shell_patterns; } | sed -e 's|.*|Bash(&)|'
    { shell_patterns; settings_shell_patterns; } | sed -e 's|.*|PowerShell(&)|'
    settings_edit_paths | sed -e 's|.*|Edit(&)|'
    mcp_patterns
  } | json_items '      ' '' ''
  printf '    ]\n'
  printf '  }\n'
  printf '}\n'
}

# ---------------------------------------------------------------------------
# opencode: opencode.json
#
# The last matching rule wins, so these deny rules must stay after any broader
# allow rule. Commands that match none of them keep opencode's default.
# ---------------------------------------------------------------------------

render_opencode() {
  printf '{\n'
  printf '  "$schema": "https://opencode.ai/config.json",\n'
  printf '  "permission": {\n'
  printf '    "bash": {\n'
  { shell_patterns; settings_shell_patterns; } | json_items '      ' '' '": "deny'
  printf '    }\n'
  printf '  }\n'
  printf '}\n'
}

# ---------------------------------------------------------------------------
# Codex: .codex/rules/guardrails.rules
#
# prefix_rule() matches the leading argv tokens literally: no globs, and a
# rule cannot require the command to end. So Codex blocks a push only when the
# remote and the target refspec are written out, e.g. `git push origin main`,
# with up to three flag or remote tokens in front of the refspec. Bare
# `git push` and `git push origin` stay allowed under Codex.
# ---------------------------------------------------------------------------

starlark_list() {
  local first=1 item
  printf '['
  for item in "$@"; do
    [ "$first" -eq 1 ] || printf ', '
    printf '"%s"' "$item"
    first=0
  done
  printf ']'
}

render_codex() {
  local -a literal=() danger=() lead=() push_lead=() commit_lead=()
  local b i k pattern

  for b in "${branches[@]}"; do
    case "$b" in *'*'*) continue ;; esac
    literal+=("$b")
  done

  for b in "${literal[@]}"; do
    danger+=("$b" "+$b" ":$b" "HEAD:$b" "+HEAD:$b" "$b:$b" "+$b:$b"
      "refs/heads/$b" "+refs/heads/$b" ":refs/heads/$b" "HEAD:refs/heads/$b"
      "+HEAD:refs/heads/$b" "$b:refs/heads/$b")
  done
  danger+=(HEAD +HEAD @ --all --branches --mirror)

  # Tokens that may stand between `git push` and the refspec.
  lead=(origin upstream -u --set-upstream -f --force --force-with-lease
    --force-if-includes --no-verify --atomic --follow-tags --tags -d --delete
    -n --dry-run -q --quiet -v --verbose --porcelain --progress --no-progress)

  # Tokens that may stand in front of a force flag or `--amend`.
  push_lead=(origin upstream -u --set-upstream --no-verify --atomic
    --follow-tags --tags -n --dry-run -q --quiet -v --verbose --porcelain
    --progress --no-progress)
  commit_lead=(-a --all --no-edit -q --quiet -v --verbose -n --no-verify
    -s --signoff -S --reset-author --allow-empty)

  printf '# %s\n' "$header_note"
  printf '#\n'
  printf '# Protected branches: %s\n' "${branches[*]}"
  if [ "${#literal[@]}" -ne "${#branches[@]}" ]; then
    printf '# Glob entries are skipped: Codex prefix rules match literal tokens only.\n'
  fi

  for k in 0 1 2 3; do
    pattern="\"git\", \"push\""
    for ((i = 0; i < k; i++)); do
      pattern+=", $(starlark_list "${lead[@]}")"
    done
    pattern+=", $(starlark_list "${danger[@]}")"
    printf '\nprefix_rule(\n'
    printf '    pattern = [%s],\n' "$pattern"
    printf '    decision = "forbidden",\n'
    printf '    justification = "Direct push to a protected branch, or a push whose target branch is implicit, is forbidden. Push a feature branch by name and open a pull request.",\n'
    printf ')\n'
  done

  # Force push: the force flag must come within the first three tokens after
  # `git push`. A `+<refspec>` or `--force-with-lease=<ref>` is not caught.
  for k in 0 1 2 3; do
    pattern="\"git\", \"push\""
    for ((i = 0; i < k; i++)); do
      pattern+=", $(starlark_list "${push_lead[@]}")"
    done
    pattern+=", $(starlark_list "${force_short_flags[@]}" --force --force-with-lease --force-if-includes)"
    printf '\nprefix_rule(\n'
    printf '    pattern = [%s],\n' "$pattern"
    printf '    decision = "forbidden",\n'
    printf '    justification = "Force push rewrites remote history and is forbidden for agents. Push new commits instead.",\n'
    printf ')\n'
  done

  # Amend: `--amend` must come within the first three tokens after
  # `git commit`, and `-m <message>` in front of it is not caught.
  for k in 0 1 2 3; do
    pattern="\"git\", \"commit\""
    for ((i = 0; i < k; i++)); do
      pattern+=", $(starlark_list "${commit_lead[@]}")"
    done
    pattern+=", [\"--amend\"]"
    printf '\nprefix_rule(\n'
    printf '    pattern = [%s],\n' "$pattern"
    printf '    decision = "forbidden",\n'
    printf '    justification = "Amending a commit rewrites history and is forbidden for agents. Make a new commit instead.",\n'
    printf ')\n'
  done

  printf '\nprefix_rule(\n'
  printf '    pattern = ["gh", "pr", "merge"],\n'
  printf '    decision = "forbidden",\n'
  printf '    justification = "Merging a pull request is forbidden for agents. A human merges it.",\n'
  printf '    match = ["gh pr merge 1 --squash"],\n'
  printf ')\n'

  printf '\nprefix_rule(\n'
  printf '    pattern = ["glab", "mr", "merge"],\n'
  printf '    decision = "forbidden",\n'
  printf '    justification = "Merging a merge request is forbidden for agents. A human merges it.",\n'
  printf ')\n'
}

# ---------------------------------------------------------------------------
# Write
#
# Files are truncated and rewritten in place rather than replaced, so a
# Windows hard link created by setup-agent-links.ps1 keeps pointing at them.
# ---------------------------------------------------------------------------

write_file() {
  local rel="$1" render="$2"
  "$render" >"$project_root/$rel"
  printf '[OK]    %s\n' "$rel"
}

printf 'Protected branches: %s\n\n' "${branches[*]}"
write_file .agent/guardrails/claude-settings.json render_claude
write_file .agent/guardrails/opencode.json render_opencode
write_file .agent/guardrails/codex.rules render_codex
printf '\nDone. Run script/setup-agent-links.sh if the links do not exist yet.\n'
