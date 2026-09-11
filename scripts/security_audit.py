from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

PRIVATE_KEY_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
)
SECRET_NAMES = (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "IG_API_KEY",
    "IG_PASSWORD",
    "MCP_AGENT_TOKEN",
    "MCP_REVIEWER_TOKEN",
    "OIDC_REVIEWER_ACCESS_TOKEN",
    "POSTGRES_PASSWORD",
    "GF_SECURITY_ADMIN_PASSWORD",
)
_ASSIGNMENT = re.compile(
    rf"^\s*({'|'.join(SECRET_NAMES)})\s*(?:=|:)\s*[\"']?([^\"'\s#]+)",
    re.MULTILINE,
)
_ALLOWED_VALUES = {
    "",
    "change-me",
    "change-me-locally",
    "changeme",
    "placeholder",
    "example",
}


def scan_text(relpath: str, text: str) -> list[str]:
    findings: list[str] = []
    if relpath == ".env":
        findings.append("tracked .env is forbidden")
    if relpath == ".env.example" or relpath.startswith("tests/"):
        return findings
    for marker in PRIVATE_KEY_MARKERS:
        if marker in text:
            findings.append(f"private key material detected in {relpath}")
            break
    for match in _ASSIGNMENT.finditer(text):
        key, value = match.group(1), match.group(2).strip()
        normalized = value.lower()
        if normalized in _ALLOWED_VALUES or value.startswith("${") or value.startswith("os.getenv"):
            continue
        findings.append(f"literal secret-like value for {key} in {relpath}")
    return findings


def tracked_files(root: Path) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root, stderr=subprocess.STDOUT
    )
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def audit_repository(root: Path) -> list[str]:
    findings: list[str] = []
    for relpath in tracked_files(root):
        path = root / relpath
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(relpath, text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    findings = audit_repository(Path(args.root).resolve())
    if findings:
        for finding in findings:
            print(f"SECURITY_AUDIT_FAIL: {finding}")
        return 1
    print("SECURITY_AUDIT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
