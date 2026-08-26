#!/usr/bin/env python3
"""Fail closed on common private-path, identity, secret, and skill-layout leaks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEXT_SUFFIXES = {".md", ".txt", ".py", ".ps1", ".json", ".yaml", ".yml", ".toml"}
BLOCKED = {
    "windows user profile": re.compile(r"(?i)C:\\Users\\(?!<|Public\\|Default\\)[^\\\s`]+"),
    "fixed private drive path": re.compile(r"(?i)(?:^|[\s`\"'])(?:D|E|F):\\"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential assignment": re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]{8,}"),
    "email address": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
}


def inspect(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"{path.relative_to(root)}: not UTF-8")
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for label, pattern in BLOCKED.items():
                if pattern.search(line):
                    findings.append(f"{path.relative_to(root)}:{line_number}: {label}")
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        findings.append("skills/: missing")
    else:
        for skill in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            manifest = skill / "SKILL.md"
            if not manifest.is_file():
                findings.append(f"{skill.relative_to(root)}: SKILL.md missing")
                continue
            text = manifest.read_text(encoding="utf-8")
            if not re.match(r"^---\s*\n.*?^name:\s*[^\n]+\n.*?^description:\s*[^\n]+\n.*?^---", text, re.M | re.S):
                findings.append(f"{manifest.relative_to(root)}: invalid YAML frontmatter")
    for required in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "SECURITY.md"):
        if not (root / required).is_file():
            findings.append(f"{required}: missing")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    findings = inspect(root)
    if findings:
        print("PUBLIC_RELEASE_CHECK=FAILED")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("PUBLIC_RELEASE_CHECK=PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
