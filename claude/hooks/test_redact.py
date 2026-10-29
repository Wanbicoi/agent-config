#!/usr/bin/env python3
"""Unit tests for Claude Code Redaction Hook."""

import json
import unittest
from pathlib import Path

import redact
from redact import Redactor, build_default_rules, process_hook


class TestRedactorPatterns(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor()

    def test_anthropic_key_redaction(self):
        # 80+ char suffix
        sample_key = "sk-ant-api03-" + "a" * 85
        text = f"curl -H 'x-api-key: {sample_key}' https://api.anthropic.com/v1/messages"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("anthropic_api_key", detected)
        self.assertNotIn(sample_key, sanitized)
        self.assertIn("[REDACTED:ANTHROPIC_KEY:sk-ant-api03...]", sanitized)

    def test_openai_key_redaction(self):
        sample_key = "sk-proj-" + "b" * 50
        text = f"export OPENAI_API_KEY={sample_key}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("openai_api_key", detected)
        self.assertNotIn(sample_key, sanitized)
        self.assertIn("[REDACTED:OPENAI_KEY:sk-proj-bbb...]", sanitized)

    def test_aws_access_key_redaction(self):
        aws_key = "AKIA1234567890ABCDEF"
        text = f"AWS_ACCESS_KEY_ID={aws_key}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("aws_access_key_id", detected)
        self.assertNotIn(aws_key, sanitized)
        self.assertIn("[REDACTED:AWS_KEY_ID:AKIA***]", sanitized)

    def test_aws_secret_key_assignment(self):
        secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        text = f"aws_secret_access_key = {secret}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("aws_secret_access_key", detected)
        self.assertNotIn(secret, sanitized)
        self.assertIn("[REDACTED:AWS_SECRET_KEY]", sanitized)

    def test_github_token_classic_and_pat(self):
        gh_classic = "ghp_" + "1" * 36
        gh_pat = "github_pat_" + "2" * 82
        text = f"Tokens: {gh_classic} and {gh_pat}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("github_token", detected)
        self.assertNotIn(gh_classic, sanitized)
        self.assertNotIn(gh_pat, sanitized)
        self.assertIn("[REDACTED:GITHUB_TOKEN:ghp_111...]", sanitized)
        self.assertIn("[REDACTED:GITHUB_TOKEN:github_...]", sanitized)

    def test_google_api_key(self):
        google_key = "AIzaSy" + "A" * 33
        text = f"Google key: {google_key}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("google_api_key", detected)
        self.assertNotIn(google_key, sanitized)
        self.assertIn("[REDACTED:GOOGLE_API_KEY]", sanitized)

    def test_slack_token(self):
        # Built by concatenation, like the other fixtures above: a contiguous
        # realistic token triggers GitHub push protection as a leaked secret.
        slack_token = (
            "xoxb-" + "123456789012-" + "123456789012-" + "abcdefghijklmnopqrstuvwx"
        )
        text = f"SLACK_BOT_TOKEN={slack_token}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("slack_token", detected)
        self.assertNotIn(slack_token, sanitized)
        self.assertIn("[REDACTED:SLACK_TOKEN:xoxb-123...]", sanitized)

    def test_stripe_key(self):
        stripe_live = "sk_live_" + "9" * 28
        text = f"stripe.api_key = '{stripe_live}'"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("stripe_key", detected)
        self.assertNotIn(stripe_live, sanitized)
        self.assertIn("[REDACTED:STRIPE_KEY:sk_live_99...]", sanitized)

    def test_huggingface_token(self):
        hf_token = "hf_" + "x" * 35
        text = f"HF_TOKEN={hf_token}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("huggingface_token", detected)
        self.assertNotIn(hf_token, sanitized)
        self.assertIn("[REDACTED:HF_TOKEN]", sanitized)

    def test_jwt_token(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        text = f"Authorization: Bearer {jwt}"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("jwt_token", detected)
        self.assertNotIn(jwt, sanitized)
        self.assertIn("[REDACTED:JWT_TOKEN]", sanitized)

    def test_database_uri_passwords(self):
        db_uri = "postgres://admin_user:SuperSecretP@ssw0rd!@db.internal.net:5432/production"
        sanitized, detected = self.redactor.redact_text(db_uri)
        self.assertIn("db_uri_credentials", detected)
        self.assertNotIn("SuperSecretP@ssw0rd!", sanitized)
        self.assertIn("postgres://admin_user:[REDACTED:DB_PASSWORD]@db.internal.net:5432/production", sanitized)

    def test_private_key_block(self):
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Y8v...test...data...\n"
            "-----END RSA PRIVATE KEY-----"
        )
        text = f"Here is my key:\n{pem}\nCheck it out."
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("private_key", detected)
        self.assertNotIn("BEGIN RSA PRIVATE KEY", sanitized)
        self.assertIn("[REDACTED:PRIVATE_KEY]", sanitized)

    def test_generic_secret_assignment(self):
        text = 'db_password: "MyHiddenSecret123!"'
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn("generic_secret_assignment", detected)
        self.assertNotIn("MyHiddenSecret123!", sanitized)
        self.assertIn('[REDACTED:DB_PASSWORD]', sanitized)


class TestFalsePositives(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor()

    def test_nix_store_path_preserved(self):
        nix_path = "/nix/store/i4k678j7vrrrhn7ikc6rphshfrpnxwcn-home-manager-files/.claude"
        sanitized, detected = self.redactor.redact_text(nix_path)
        self.assertEqual(sanitized, nix_path)
        self.assertEqual(detected, [])

    def test_uuid_preserved(self):
        uuid_str = "75efa71b-f761-413e-8aab-ffdf7b8037fb"
        sanitized, detected = self.redactor.redact_text(uuid_str)
        self.assertEqual(sanitized, uuid_str)
        self.assertEqual(detected, [])

    def test_git_commit_hash_preserved(self):
        commit_hash = "f4c20b8e7456d98a0026e6efbc134d193d2bca81"
        text = f"commit {commit_hash} (HEAD -> main)"
        sanitized, detected = self.redactor.redact_text(text)
        self.assertIn(commit_hash, sanitized)
        self.assertEqual(detected, [])

    def test_code_syntax_and_keywords(self):
        code = """
        def authenticate(user_token=None):
            if not user_token:
                raise ValueError("missing token")
            return True
        """
        sanitized, detected = self.redactor.redact_text(code)
        self.assertEqual(sanitized, code)
        self.assertEqual(detected, [])


class TestHookContract(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor()

    def test_post_tool_use_clean_noop(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": "file1.txt\nfile2.txt\n",
        }
        res = process_hook(json.dumps(payload), self.redactor)
        self.assertEqual(res, {})

    def test_post_tool_use_string_response_redacted(self):
        secret = "AKIA1111222233334444"
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "env"},
            "tool_response": f"USER=nixos\nAWS_KEY={secret}\n",
        }
        res = process_hook(json.dumps(payload), self.redactor)
        self.assertIn("hookSpecificOutput", res)
        hso = res["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PostToolUse")
        self.assertIsInstance(hso["updatedToolOutput"], str)
        self.assertNotIn(secret, hso["updatedToolOutput"])
        self.assertIn("[REDACTED:AWS_KEY_ID:AKIA***]", hso["updatedToolOutput"])

    def test_post_tool_use_dict_response_shape_preserved(self):
        # Tools returning structured dict (stdout, stderr, exit_code)
        secret = "ghp_" + "a" * 36
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_response": {
                "stdout": f"GitHub token is {secret}",
                "stderr": "",
                "exit_code": 0,
            },
        }
        res = process_hook(json.dumps(payload), self.redactor)
        self.assertIn("hookSpecificOutput", res)
        output = res["hookSpecificOutput"]["updatedToolOutput"]
        # Dict shape must be preserved!
        self.assertIsInstance(output, dict)
        self.assertEqual(output["exit_code"], 0)
        self.assertNotIn(secret, output["stdout"])
        self.assertIn("[REDACTED:GITHUB_TOKEN:ghp_aaa...]", output["stdout"])

    def test_user_prompt_submit_clean(self):
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Hello Claude, please help me optimize this SQL query",
        }
        res = process_hook(json.dumps(payload), self.redactor)
        self.assertEqual(res, {})

    def test_user_prompt_submit_blocked_on_secret(self):
        openai_key = "sk-proj-" + "z" * 45
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": f"Here is my key: {openai_key}, why does it fail?",
        }
        res = process_hook(json.dumps(payload), self.redactor)
        self.assertEqual(res.get("decision"), "block")
        self.assertIn("openai_api_key", res.get("reason", ""))
        self.assertIn("systemMessage", res)


if __name__ == "__main__":
    unittest.main()
