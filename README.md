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
AGENTS.md  canonical global instructions (single source of truth)
skills/    canonical Agent Skills, shared by every agent
pi/        Pi agent dir        -> ~/.pi/agent          (AGENTS.md -> ../AGENTS.md)
claude/    user config subset  -> ~/.claude/{CLAUDE.md,agents,commands}
opencode/  OpenCode config dir -> ~/.config/opencode     (AGENTS.md -> ../AGENTS.md)
```

`AGENTS.md` at the repo root is the only place global instructions are edited.
The per-tool files are symlinks to it, so Pi, Claude Code, and OpenCode all load
the same text:

| Tool | File read |
|------|-----------|
| Pi | `pi/AGENTS.md` -> `../AGENTS.md` |
| OpenCode | `opencode/AGENTS.md` -> `../AGENTS.md` |
| Claude Code | `claude/CLAUDE.md` -> `../AGENTS.md` (wired directly to the canonical file) |

`skills/` is likewise the single canonical copy of installed Agent Skills. Pi
and OpenCode read it through `~/.agents/skills`, Claude Code through
`~/.claude/skills`; the wiring lives in `home/nixos/submodules.nix`.

## Tracked vs ignored

**Tracked:** agent settings/preferences, instructions (`AGENTS.md`/`CLAUDE.md`),
extensions/skills/commands/subagents, themes, MCP server definitions.

**Never tracked:** `auth.json`, `.credentials.json`, API keys, `sessions/`,
`projects/`, `storage/`, installed npm packages, and platform-managed files
(e.g. Orca's `pi/extensions/orca-agent-status.ts` and Claude's
`~/.claude/settings.json`).

## Wiring

This repo is a git submodule of `nixconfig` and is linked into place by
`home/nixos/default.nix` using `mkOutOfStoreSymlink` (so the link target is a
writable checkout, **not** `/nix/store` — important for Claude Code's settings
watcher). The same pattern as the `nvim` submodule.

```
home.file.".pi/agent"        -> <repo>/pi
xdg.configFile."opencode"    -> <repo>/opencode
home.file.".agents/skills"   -> <repo>/skills
home.file.".claude/skills"   -> <repo>/skills
home.file.".claude/CLAUDE.md"-> <repo>/AGENTS.md
home.file.".claude/agents"   -> <repo>/claude/agents
...
```

> The absolute path `${HOME}/nixconfig` is assumed, matching the existing `nvim`
> wiring. Clone `nixconfig` at `~/nixconfig`.

## Remote

The submodule URL is currently a placeholder. Point it at your real remote
(private repo recommended, it contains personal agent config):

```sh
cd ~/nixconfig
make agent-remote AGENT_REMOTE=git@github.com:<you>/agent-config.git
git add .gitmodules agent-config && git commit -m "agent-config: set remote"
cd agent-config && git push -u origin main
```

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
