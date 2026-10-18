# agent-config

Shared, version-controlled configuration for the AI coding agents used on every
machine:

| Tool                       | Repo dir   | Linked to                  |
|----------------------------|------------|----------------------------|
| [Pi](https://pi.dev)       | `pi/`      | `~/.pi/agent`              |
| [Claude Code](https://code.claude.com) | `claude/` | `~/.claude/` (subset) |
| [OpenCode](https://opencode.ai) | `opencode/` | `~/.config/opencode`  |

Only **portable, user-authored** config lives here. Credentials, session
history, caches, installed packages, and platform-injected files are ignored —
see each subdirectory's `.gitignore`.

## Layout

```
pi/        Pi agent dir        -> ~/.pi/agent
claude/    user config subset  -> ~/.claude/{CLAUDE.md,agents,commands,skills}
opencode/  OpenCode config dir -> ~/.config/opencode
```

## Tracked vs ignored

**Tracked:** agent settings/preferences, instructions (`AGENTS.md`/`CLAUDE.md`),
extensions/skills/commands/subagents, themes, MCP server definitions.

**Never tracked:** `auth.json`, `.credentials.json`, API keys, `sessions/`,
`projects/`, `storage/`, installed npm packages, and platform-managed files
(e.g. Orca's `pi/extensions/orca-agent-status.ts` and Claude's
`~/.claude/settings.json`).

## Wiring

This repo is a git submodule of
[`nixconfig`](https://github.com/CHANGE_ME/nixconfig) and is linked into place by
`home/nixos/default.nix` using `mkOutOfStoreSymlink` (so the link target is a
writable checkout, **not** `/nix/store` — important for Claude Code's settings
watcher). The same pattern as the `nvim` submodule.

```
home.file.".pi/agent"        -> <repo>/pi
xdg.configFile."opencode"    -> <repo>/opencode
home.file.".claude/CLAUDE.md"-> <repo>/claude/CLAUDE.md
home.file.".claude/agents"   -> <repo>/claude/agents
...
```

> The absolute path `${HOME}/nixconfig` is assumed, matching the existing `nvim`
> wiring. Clone `nixconfig` at `~/nixconfig`.

## New machine

```sh
git clone --recurse-submodules <nixconfig-url> ~/nixconfig
# then, from ~/nixconfig:
make switch          # Home Manager links everything into place
```

Credentials are **not** synced: run `pi /login`, `claude` auth, and
`opencode auth login` (or set the provider API-key env vars) once per machine.

## Editing

Edit files here and commit. A running agent reads the file through the symlink;
most tools need a reload/restart to pick up changes.
