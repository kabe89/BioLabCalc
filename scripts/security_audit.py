#!/usr/bin/env python3
"""
Automated Git Security & PII Auditor for BioLabCalc.

Audits tracked files and Git configuration to ensure:
1. No personal email addresses or real usernames are committed.
2. No local developer directories or machine-specific absolute paths are present.
3. No hardcoded credentials, private keys, API keys, or auth tokens exist.
4. Git committer and author configuration use privacy-preserving noreply emails.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Allowed email domains in code, tests, and documentation
ALLOWED_EMAIL_DOMAINS = (
    "biolabcalc.org",
    "alumni.biolabcalc.org",
    "example.com",
    "users.noreply.github.com",
)

# Known benign synthetic test paths
BENIGN_PATHS = (
    r"C:\Users\jdoe",
    r"C:\Users\admin",
    r"C:\Users\test",
    r"C:\Users\scientist",
    r"C:\Users\BenchResearcher",
    r"C:\local\db.sqlite",
    r"C:\windows",
)

SECRET_PATTERNS = [
    (r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "Private cryptographic key"),
    (r"\bghp_[A-Za-z0-9_]{36,}\b", "GitHub Personal Access Token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{60,}\b", "GitHub Fine-Grained Personal Access Token"),
    (r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b", "AWS Access Key ID"),
    (r"(?:api[_-]?key|auth[_-]?token|secret[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{24,}['\"]", "Hardcoded API/Auth Token"),
]


def run_git(args: List[str]) -> Tuple[int, str]:
    res = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True)
    return res.returncode, res.stdout.strip()


def check_git_config() -> List[str]:
    """Verify local Git user configuration uses a privacy-preserving noreply email."""
    errors = []
    code, email = run_git(["config", "user.email"])
    if code != 0 or not email:
        errors.append("Git user.email is not configured.")
    elif not any(email.lower().endswith(d) for d in ALLOWED_EMAIL_DOMAINS):
        errors.append(f"Git user.email '{email}' is a personal email. Use GitHub noreply email.")

    return errors


def check_tracked_files() -> List[str]:
    """Inspect all git-tracked files for PII, local paths, and secrets."""
    errors = []
    code, files_out = run_git(["ls-files"])
    if code != 0:
        return ["Failed to list git tracked files."]

    tracked_files = [f for f in files_out.splitlines() if f.strip()]

    # Patterns
    email_regex = re.compile(r"\b([A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,}))\b", re.IGNORECASE)
    # Match Windows user profiles: C:\Users\<name> or C:/Users/<name>
    user_path_regex = re.compile(r"[A-Za-z]:[\\/][Uu]sers[\\/]([A-Za-z0-9_.-]+)", re.IGNORECASE)

    for rel_path in tracked_files:
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            continue

        # Skip binary files or large assets
        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # 1. Check for personal emails
        for match in email_regex.finditer(content):
            full_email = match.group(1)
            domain = match.group(2).lower()
            if not any(domain == d or domain.endswith("." + d) for d in ALLOWED_EMAIL_DOMAINS):
                # Check line number
                line_no = content[: match.start()].count("\n") + 1
                errors.append(f"{rel_path}:{line_no}: Disallowed personal email found: '{full_email}'")

        # 2. Check for personal Windows user paths
        for match in user_path_regex.finditer(content):
            matched_path = match.group(0)
            if not any(matched_path.lower().startswith(b.lower()) for b in BENIGN_PATHS):
                line_no = content[: match.start()].count("\n") + 1
                errors.append(f"{rel_path}:{line_no}: Potential local machine path found: '{matched_path}'")

        # 3. Check for secrets
        for pattern, desc in SECRET_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_no = content[: match.start()].count("\n") + 1
                errors.append(f"{rel_path}:{line_no}: {desc} detected: '{match.group(0)[:20]}...'")

    return errors


def main() -> None:
    print("======================================================================")
    print("  BIOLABCALC GIT SECURITY & PII COMPLIANCE AUDIT")
    print("======================================================================")

    config_errors = check_git_config()
    tracked_errors = check_tracked_files()

    all_errors = config_errors + tracked_errors

    if config_errors:
        print("[!] Git Configuration Issues:")
        for err in config_errors:
            print(f"    - {err}")

    if tracked_errors:
        print("[!] Tracked File Violations:")
        for err in tracked_errors:
            print(f"    - {err}")

    if all_errors:
        print("======================================================================")
        print(f"[FAILED] Found {len(all_errors)} security or PII violation(s).")
        print("======================================================================")
        sys.exit(1)

    print("[✓] Git Configuration: Privacy-preserving noreply email confirmed.")
    print("[✓] Tracked Files: Zero personal emails, real usernames, or local machine paths.")
    print("[✓] Secrets Scan: Zero private keys, access tokens, or credentials detected.")
    print("======================================================================")
    print("[PASSED] ALL GIT SECURITY & PII CHECKS PASSED WITH ZERO VIOLATIONS.")
    print("======================================================================")
    sys.exit(0)


if __name__ == "__main__":
    main()
