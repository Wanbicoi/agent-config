# Claude Code user configuration (portable subset)

This directory is the source of truth for **user-authored** Claude Code
configuration. It is symlinked into `~/.claude/` by `home/nixos/default.nix`.

## Tracked here

| Path           | Purpose                                         |
|----------------|-------------------------------------------------|
| `CLAUDE.md`    | Symlink to `../AGENTS.md` (global instructions) |
| `agents/`      | User subagents (`*.md`)                         |
| `commands/`    | User slash commands (`*.md`)                    |
| `hooks/`       | Lifecycle hooks (`redact.py`)                   |
| `settings.json`| Durable user settings (model, theme, hooks)     |

Global instructions live in the repo-root `AGENTS.md`, shared with Pi and
OpenCode. `CLAUDE.md` is only a symlink to it; edit `AGENTS.md` instead.

Agent Skills are shared too: they live in the repo-root `skills/` directory and
are linked into Claude Code via `~/.claude/skills` (see
`home/nixos/submodules.nix`).

## Deliberately NOT tracked

- `settings.local.json` — per-machine overrides.
- `projects/`, `todos/`, `shell-snapshots/`, `statsig/`, `plugins/` — runtime.
- `.credentials.json` — secrets.

Hooks that external tools install themselves (currently
`hooks/herdr-agent-state.sh`, owned by Herdr) are also not tracked; the tracked
`settings.json` only references them via `$HOME`. Orca used to rewrite
`settings.json` with per-machine hook commands; that file is now ours, so keep
machine-specific paths out of it (use `$HOME` in hook commands).

## Note on symlinks

`~/.claude/settings.json` is linked to this checkout (out-of-store, writable),
like the other config entries. Edits Claude Code or Herdr make to it land here,
so review `git diff` after changing settings in the UI. Everything is linked to
an *out-of-store, writable* location (this repo) rather than to `/nix/store`
because Claude Code's settings watcher and writers need a writable path.
