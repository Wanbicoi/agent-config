#!/usr/bin/env python3
"""Claude Code Redaction Hook.

Intercepts Claude Code lifecycle events (primarily PostToolUse and UserPromptSubmit)
to detect and scrub sensitive secrets, API keys, credentials, and private keys
before they enter the LLM's context window or get sent upstream.

Supported events:
  - PostToolUse: Sanitizes tool_response (Bash stdout/stderr, Read/ReadFile content, etc.)
                 using hookSpecificOutput.updatedToolOutput.
  - UserPromptSubmit: Blocks accidental submission of raw credentials in user chat prompt.
  - PreToolUse: Sanitizes tool_input before execution (optional).
  - CLI / Filter: Pipe or check text directly for testing and validation.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple, Union


# -----------------------------------------------------------------------------
# Pattern Definitions
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class SecretRule:
    name: str
    pattern: Pattern[str]
    replacer: Callable[[re.Match[str]], str]
    category: str


# Common false-positive guards:
# - Nix store paths: /nix/store/<32-char-hash>-<name>
# - UUIDs: 8-4-4-4-12 hex
# - Git commit hashes: 40 or 64 hex chars
NIX_STORE_REGEX = re.compile(r"/nix/store/[a-z0-9]{32}-[^\s/]+")
UUID_REGEX = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
GIT_HASH_REGEX = re.compile(r"\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{64}\b")

# Placeholders that should NOT be redacted
DUMMY_PLACEHOLDERS = re.compile(
    r"^(?:example|placeholder|changeme|your[-_]?api[-_]?key|your[-_]?secret|todo|xxx+|\*{3,}|<[^>]+>)$",
    re.IGNORECASE,
)


def build_default_rules() -> List[SecretRule]:
    rules: List[SecretRule] = []

    # 1. Private Keys
    rules.append(
        SecretRule(
            name="private_key",
            category="crypto",
            pattern=re.compile(
                r"-----BEGIN\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY-----\s*[\s\S]+?\s*-----END\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY-----",
                re.MULTILINE,
            ),
            replacer=lambda m: "[REDACTED:PRIVATE_KEY]",
        )
    )

    # 2. Anthropic API Keys (sk-ant-api03-..., sk-ant-admin01-...)
    rules.append(
        SecretRule(
            name="anthropic_api_key",
            category="api_key",
            pattern=re.compile(r"\bsk-ant-(?:api|admin)[0-9]{2}-[a-zA-Z0-9_-]{80,}\b"),
            replacer=lambda m: f"[REDACTED:ANTHROPIC_KEY:{m.group(0)[:12]}...]",
        )
    )

    # 3. OpenAI API Keys (sk-..., sk-proj-...)
    rules.append(
        SecretRule(
            name="openai_api_key",
            category="api_key",
            pattern=re.compile(r"\bsk-(?:proj-)?[a-zA-Z0-9_-]{40,}\b"),
            replacer=lambda m: f"[REDACTED:OPENAI_KEY:{m.group(0)[:11]}...]",
        )
    )

    # 4. AWS Credentials
    # Access Key ID: AKIA, ASIA, ABIA, ACCA followed by 16 alphanumeric characters
    rules.append(
        SecretRule(
            name="aws_access_key_id",
            category="cloud",
            pattern=re.compile(r"\b(AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
            replacer=lambda m: f"[REDACTED:AWS_KEY_ID:{m.group(0)[:4]}***]",
        )
    )
    # AWS Secret Key assignment in scripts/configs
    rules.append(
        SecretRule(
            name="aws_secret_access_key",
            category="cloud",
            pattern=re.compile(
                r"(?i)\b(aws[_-]?secret[_-]?access[_-]?key)\s*([:=])\s*(['\"]?)([A-Za-z0-9/+=]{40})\3"
            ),
            replacer=lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}[REDACTED:AWS_SECRET_KEY]{m.group(3)}",
        )
    )

    # 5. GitHub Tokens
    # Classic (ghp_), Fine-grained (github_pat_), OAuth (gho_), User/Server (ghu_, ghs_, ghr_)
    rules.append(
        SecretRule(
            name="github_token",
            category="api_key",
            pattern=re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{82})\b"),
            replacer=lambda m: f"[REDACTED:GITHUB_TOKEN:{m.group(1)[:7]}...]",
        )
    )

    # 6. Google / Gemini / GCP API Key
    rules.append(
        SecretRule(
            name="google_api_key",
            category="api_key",
            pattern=re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
            replacer=lambda m: "[REDACTED:GOOGLE_API_KEY]",
        )
    )

    # 7. Slack Tokens (xoxb-, xoxp-, xoxa-, xoxr-)
    rules.append(
        SecretRule(
            name="slack_token",
            category="api_key",
            pattern=re.compile(r"\bxox[bpar]-[0-9]{9,13}-[0-9]{9,13}-[a-zA-Z0-9]{24,32}\b"),
            replacer=lambda m: f"[REDACTED:SLACK_TOKEN:{m.group(0)[:8]}...]",
        )
    )

    # 8. Hugging Face Tokens (hf_...)
    rules.append(
        SecretRule(
            name="huggingface_token",
            category="api_key",
            pattern=re.compile(r"\bhf_[a-zA-Z0-9]{34,}\b"),
            replacer=lambda m: "[REDACTED:HF_TOKEN]",
        )
    )

    # 9. Stripe API Keys (sk_live_, rk_live_)
    rules.append(
        SecretRule(
            name="stripe_key",
            category="api_key",
            pattern=re.compile(r"\b[sr]k_live_[0-9a-zA-Z]{24,}\b"),
            replacer=lambda m: f"[REDACTED:STRIPE_KEY:{m.group(0)[:10]}...]",
        )
    )

    # 10. JSON Web Tokens (JWT)
    rules.append(
        SecretRule(
            name="jwt_token",
            category="auth",
            pattern=re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"),
            replacer=lambda m: "[REDACTED:JWT_TOKEN]",
        )
    )

    # 11. Database Connection URIs with embedded passwords
    # postgres://user:password@host, mongodb://..., redis://...
    rules.append(
        SecretRule(
            name="db_uri_credentials",
            category="database",
            pattern=re.compile(
                r"((?:postgres|postgresql|mysql|mongodb|mongodb\+srv|redis|rediss|amqp|amqps)://[^\s/@:]+:)(.+)(@[a-zA-Z0-9.-]+(?::\d+)?(?:/[^\s]*)?)",
                re.IGNORECASE,
            ),
            replacer=lambda m: f"{m.group(1)}[REDACTED:DB_PASSWORD]{m.group(3)}",
        )
    )

    # 12. HTTP Authorization Headers
    # Authorization: Bearer <token>
    rules.append(
        SecretRule(
            name="auth_bearer_header",
            category="auth",
            pattern=re.compile(r"(?i)\b(authorization\s*:\s*Bearer\s+)([a-zA-Z0-9_\-\.]{20,})\b"),
            replacer=lambda m: f"{m.group(1)}[REDACTED:BEARER_TOKEN]",
        )
    )
    # Authorization: Basic <base64>
    rules.append(
        SecretRule(
            name="auth_basic_header",
            category="auth",
            pattern=re.compile(r"(?i)\b(authorization\s*:\s*Basic\s+)([A-Za-z0-9+/=]{16,})\b"),
            replacer=lambda m: f"{m.group(1)}[REDACTED:BASIC_AUTH]",
        )
    )

    # 13. Generic Credential Key=Value Assignments
    # db_password: "...", secret_key = "..."
    rules.append(
        SecretRule(
            name="generic_secret_assignment",
            category="credentials",
            pattern=re.compile(
                r"""(?xi)
                (?:^|(?<=[\s,;{(]))
                ([a-zA-Z0-9_]*?(?:api_?key|apikey|secret_?key|auth_?token|access_?token|private_?token|passwd|password))
                \s*([:=])\s*
                (['"]?)([^'"\s\n\r#]{8,})\3
                """
            ),
            replacer=lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}[REDACTED:{m.group(1).upper()}]{m.group(3)}",
        )
    )

    return rules


# -----------------------------------------------------------------------------
# Configuration & Redactor Engine
# -----------------------------------------------------------------------------

class Redactor:
    """Core redaction engine."""

    def __init__(self, rules: Optional[List[SecretRule]] = None, allowlist: Optional[List[str]] = None):
        self.rules = rules or build_default_rules()
        self.allowlist: List[Pattern[str]] = [
            NIX_STORE_REGEX,
            UUID_REGEX,
        ]
        if allowlist:
            for item in allowlist:
                try:
                    self.allowlist.append(re.compile(item))
                except re.error:
                    pass

    def redact_text(self, text: str) -> Tuple[str, List[str]]:
        """Redacts all matching secrets in `text`.
        
        Returns:
            Tuple of (sanitized_text, list_of_detected_rule_names)
        """
        if not text or not isinstance(text, str):
            return text, []

        modified_text = text
        detected: List[str] = []

        for rule in self.rules:
            # Check if pattern matches
            if not rule.pattern.search(modified_text):
                continue

            # We perform replacement with allowlist verification
            def replace_handler(m: re.Match[str]) -> str:
                matched_str = m.group(0)

                # Skip if matched string is in allowlist (e.g. nix store path or uuid)
                for allow_pat in self.allowlist:
                    if allow_pat.search(matched_str):
                        return matched_str

                # Skip already redacted placeholders
                if "[REDACTED" in matched_str:
                    return matched_str

                # Check dummy placeholders for the extracted value
                # (usually the last group or whole match)
                val_to_check = m.group(m.lastindex) if m.lastindex else matched_str
                if DUMMY_PLACEHOLDERS.match(val_to_check.strip("'\"")):
                    return matched_str

                if rule.name not in detected:
                    detected.append(rule.name)
                return rule.replacer(m)

            new_text = rule.pattern.sub(replace_handler, modified_text)
            modified_text = new_text

        return modified_text, detected

    def redact_structure(self, obj: Any) -> Tuple[Any, List[str]]:
        """Recursively redact secrets across dictionaries, lists, and strings."""
        all_detected: List[str] = []

        def _traverse(item: Any) -> Any:
            if isinstance(item, str):
                redacted, detected = self.redact_text(item)
                all_detected.extend(detected)
                return redacted
            elif isinstance(item, dict):
                return {k: _traverse(v) for k, v in item.items()}
            elif isinstance(item, list):
                return [_traverse(elem) for elem in item]
            return item

        sanitized_obj = _traverse(obj)
        # Deduplicate detected while preserving order
        unique_detected = list(dict.fromkeys(all_detected))
        return sanitized_obj, unique_detected


def load_config() -> Redactor:
    """Optionally loads user custom rules/allowlists from ~/.claude/redact.json."""
    config_paths = [
        Path.home() / ".claude" / "redact.json",
        Path.cwd() / ".claude" / "redact.json",
    ]
    allowlist: List[str] = []

    for path in config_paths:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    allowlist.extend(data.get("allowlist", []))
            except Exception:
                pass

    return Redactor(allowlist=allowlist)


# -----------------------------------------------------------------------------
# Hook Handlers
# -----------------------------------------------------------------------------

def handle_post_tool_use(payload: Dict[str, Any], redactor: Redactor) -> Dict[str, Any]:
    """Handles PostToolUse hook event.
    
    Inspects `tool_response` and returns hookSpecificOutput with updatedToolOutput
    if any secret was found, preserving the exact data type/shape of tool_response.
    """
    tool_response = payload.get("tool_response")
    if tool_response is None:
        return {}

    sanitized_response, detected = redactor.redact_structure(tool_response)

    if not detected:
        # Fast path: nothing was redacted, output empty JSON
        return {}

    # Claude Code schema requires hookSpecificOutput.updatedToolOutput
    tool_name = payload.get("tool_name", "tool")
    note = f"Scrubbed {len(detected)} sensitive credential pattern(s) from {tool_name} output ({', '.join(detected)})."

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": sanitized_response,
            "additionalContext": note,
        }
    }


def handle_user_prompt_submit(payload: Dict[str, Any], redactor: Redactor) -> Dict[str, Any]:
    """Handles UserPromptSubmit hook event.
    
    Inspects user prompt before submission. If high-severity secrets (private keys,
    API keys) are found, blocks submission so they never leave the machine.
    """
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return {}

    _, detected = redactor.redact_text(prompt)
    if not detected:
        return {}

    # Block prompt from reaching the model
    reason = (
        f"Redaction guard blocked prompt submission: detected sensitive credential(s) "
        f"({', '.join(detected)}). Please remove secrets before sending."
    )
    return {
        "decision": "block",
        "reason": reason,
        "systemMessage": f"⚠️ [Redact] Blocked prompt submission containing credentials: {', '.join(detected)}",
    }


def process_hook(raw_input: str, redactor: Redactor) -> Dict[str, Any]:
    """Dispatches raw JSON stdin to appropriate hook handler."""
    if not raw_input.strip():
        return {}

    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError:
        # Not JSON, fallback to line/text filter
        sanitized, _ = redactor.redact_text(raw_input)
        sys.stdout.write(sanitized)
        return {}

    if not isinstance(data, dict):
        return {}

    # Infer hook event
    event_name = data.get("hook_event_name")

    if event_name == "UserPromptSubmit" or ("prompt" in data and "tool_response" not in data):
        return handle_user_prompt_submit(data, redactor)

    # Default to PostToolUse if tool_response exists or event is PostToolUse
    if event_name == "PostToolUse" or "tool_response" in data:
        return handle_post_tool_use(data, redactor)

    # If it's PreToolUse, check tool_input
    if event_name == "PreToolUse" and "tool_input" in data:
        sanitized_input, detected = redactor.redact_structure(data["tool_input"])
        if detected:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": sanitized_input,
                }
            }
        return {}

    return {}


# -----------------------------------------------------------------------------
# Main CLI & Entrypoint
# -----------------------------------------------------------------------------

def main() -> int:
    redactor = load_config()

    # CLI test modes
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--help", "-h"):
            print(__doc__)
            return 0
        if arg == "--filter":
            # Direct stdin/stdout streaming text filter
            content = sys.stdin.read()
            sanitized, _ = redactor.redact_text(content)
            sys.stdout.write(sanitized)
            return 0
        if arg == "--test-string" and len(sys.argv) > 2:
            sanitized, detected = redactor.redact_text(sys.argv[2])
            print(f"Detected: {detected}")
            print(f"Result: {sanitized}")
            return 0

    # Normal hook execution reading from stdin
    try:
        raw_input = sys.stdin.read()
    except Exception:
        print("{}", file=sys.stdout)
        return 0

    result = process_hook(raw_input, redactor)
    # Always print valid JSON
    output_json = json.dumps(result) if result else "{}"
    print(output_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
