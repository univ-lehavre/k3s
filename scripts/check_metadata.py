from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORBIDDEN_PATTERNS = {
    "codex": re.compile(r"\bcodex\b|\[codex\]", re.IGNORECASE),
    "chatgpt": re.compile(r"\bchatgpt\b", re.IGNORECASE),
    "openai": re.compile(r"\bopenai\b", re.IGNORECASE),
    "claude": re.compile(r"\bclaude\b", re.IGNORECASE),
    "copilot": re.compile(r"\bcopilot\b", re.IGNORECASE),
}


def find_violations(label: str, text: str) -> list[str]:
    violations: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(line):
                violations.append(f"{label}:{line_number}: forbidden metadata term: {name}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject AI/vendor branding in commit and pull request metadata."
    )
    parser.add_argument("paths", nargs="*", type=Path, help="Files containing metadata to check.")
    parser.add_argument("--label", default="metadata", help="Label used in violation output.")
    parser.add_argument("--text", action="append", default=[], help="Inline text to check.")
    args = parser.parse_args()

    violations: list[str] = []

    for index, text in enumerate(args.text, start=1):
        violations.extend(find_violations(f"{args.label}-text-{index}", text))

    for path in args.paths:
        violations.extend(find_violations(str(path), path.read_text(encoding="utf-8")))

    if violations:
        print("Metadata rejected: do not use AI/vendor trademarks in commits or PRs.")
        for violation in violations:
            print(violation)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
