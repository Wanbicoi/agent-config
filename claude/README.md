# Claude Code user configuration (portable subset)

This directory is the source of truth for **user-authored** Claude Code
configuration. It is symlinked into `~/.claude/` by `home/nixos/default.nix`.

## Tracked here

| Path        | Purpose                                   |
|-------------|-------------------------------------------|
| `CLAUDE.md` | Global user instructions                  |
| `agents/`   | User subagents (`*.md`)                   |
| `commands/` | User slash commands (`*.md`)              |
| `skills/`   | User skills (`<name>/SKILL.md`)           |

## Deliberately NOT tracked

- `settings.json` — currently rewritten by Orca with per-machine hook commands
  (encoded PowerShell paths, `${HOME}/.orca/...`). Versioning it would leak
  machine paths and fight the platform. If you later add durable user settings
  (permissions, model, statusLine) rework this: keep the Orca `hooks` key out
  of git, e.g. track a `settings.user.json` and merge, or relocate the whole
  config dir with `CLAUDE_CONFIG_DIR`.
- `projects/`, `todos/`, `shell-snapshots/`, `statsig/`, `plugins/` — runtime.
- `.credentials.json` — secrets.

## Note on symlinks

Claude Code has had bugs with symlinked config files (it may not see symlinked
commands/memory, and its settings watcher can enumerate a symlink's parent
dir). That is why **only `settings.json` is left untouched** and the rest are
linked to an *out-of-store, writable* location (this repo) rather than to
`/nix/store`.
