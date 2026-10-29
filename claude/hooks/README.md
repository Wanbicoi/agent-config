# Claude Code Redaction Hook (`redact.py`)

A fast, dependency-free Python hook for Claude Code that prevents sensitive API keys, private keys, database credentials, and secrets from leaking into the model context or outgoing prompts.

---

## Capabilities

1. **`PostToolUse` Redaction**: Intercepts tool execution outputs (from `Bash`, `Read`, `Grep`, `Glob`, `WebFetch`, etc.) and scrubs matching secrets before they are fed to the model context.
2. **`UserPromptSubmit` Guard**: Prevents users from accidentally submitting credentials directly in chat prompts (blocks submission and alerts the user).
3. **Shape & Type Preservation**: Maintains exact dictionary and string output schemas so Claude Code's tool validation passes cleanly.
4. **Fast & Non-intrusive**: Returns `{}` immediately when no secrets are detected, incurring negligible overhead.
5. **False Positive Guard**: Protects Nix store paths (`/nix/store/...`), UUIDs, and Git commit hashes from accidental mangling.

---

## Pattern Coverage

- **Anthropic API Keys**: `sk-ant-api03-...`, `sk-ant-admin01-...`
- **OpenAI API Keys**: `sk-...`, `sk-proj-...`
- **AWS Credentials**: `AKIA...`, `ASIA...`, `aws_secret_access_key`
- **GitHub Tokens**: Classic PAT (`ghp_`), fine-grained (`github_pat_`), OAuth (`gho_`), user/server (`ghu_`, `ghs_`, `ghr_`)
- **Google / Gemini / GCP**: `AIza...`
- **Slack Tokens**: `xoxb-`, `xoxp-`, `xoxa-`, `xoxr-`
- **Hugging Face**: `hf_...`
- **Stripe**: `sk_live_...`, `rk_live_...`
- **JSON Web Tokens (JWT)**: `eyJ...`
- **Private Keys**: RSA, OpenSSH, PGP, EC (`BEGIN PRIVATE KEY`)
- **Database Connection URIs**: `postgres://...`, `mysql://...`, `mongodb://...`, `redis://...`
- **HTTP Authorization Headers**: `Authorization: Bearer <token>`, `Authorization: Basic <token>`
- **Generic Key-Value Assignments**: `password=...`, `secret_key=...`, `auth_token=...`

---

## Configuring in `~/.claude/settings.json`

Add the hook to the `PostToolUse` and `UserPromptSubmit` arrays in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash|Read|ReadFile|View|Grep|Glob|WebFetch",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/nixos/.claude/hooks/redact.py",
            "timeout": 10
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 /home/nixos/.claude/hooks/redact.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

---

## Standalone / CLI Usage

```bash
# Test a single string
python3 ~/.claude/hooks/redact.py --test-string "export AWS_KEY=AKIA1234567890ABCDEF"

# Stream filter via stdin/stdout
cat sensitive.log | python3 ~/.claude/hooks/redact.py --filter

# Run test suite
python3 -m unittest /srv/nixconfig/submodules/agent-config/claude/hooks/test_redact.py
```
