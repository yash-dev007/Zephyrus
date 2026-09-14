"""Report-only changed-test guidance helper for CI.

Given the tests/ paths changed in a PR, prints the exact pytest commands to
run. It never infers tests from source changes: only directly changed files
under tests/ are reported. Existing blocking CI remains the source of truth.
"""

from __future__ import annotations

import posixpath
import shlex
import subprocess
from collections.abc import Iterable


def parse_paths(raw: bytes) -> list[str]:
    """Split NUL-delimited (falling back to newline-delimited) git output."""
    text = raw.decode("utf-8", errors="surrogateescape")
    return [p for p in text.replace("\0", "\n").splitlines() if p.strip()]


def _normalize(path: str) -> str:
    path = path.strip()
    if path.startswith("./"):
        path = path[2:]
    return posixpath.normpath(path)


def select_test_paths(paths: Iterable[str]) -> list[str]:
    """Keep only files under tests/, normalized and deduplicated."""
    selected: list[str] = []
    for path in paths:
        normalized = _normalize(path)
        if not normalized.startswith("tests/"):
            continue
        if normalized not in selected:
            selected.append(normalized)
    return selected


def _pytest_command(path: str) -> str:
    return f"python3 -m pytest -q {shlex.quote(path)}"


def format_report(paths: Iterable[str]) -> str:
    """Build a markdown report for changed tests/ paths."""
    selected = select_test_paths(paths)
    lines = ["### Changed tests", ""]
    if not selected:
        lines.append("No changed paths under `tests/`.")
    else:
        for path in selected:
            lines.append(f"- `{path}`")
            if path.endswith(".py"):
                lines.append(f"  `{_pytest_command(path)}`")
    lines.append("")
    runnable = [p for p in selected if p.endswith(".py")]
    if runnable:
        lines.append("Run the commands above to verify the changed tests.")
    else:
        lines.append("No directly runnable pytest files changed.")
    lines.append("")
    lines.append(
        "Note: this report does not infer tests from source changes; "
        "it only lists directly changed files under `tests/`."
    )
    lines.append("Existing blocking CI remains the source of truth.")
    return "\n".join(lines) + "\n"


def changed_paths_from_merge_base(base_sha: str, head_sha: str) -> list[str]:
    """Tests/ paths changed on head since its merge-base with base."""
    merge_base = subprocess.check_output(
        ["git", "merge-base", base_sha, head_sha], text=True
    ).strip()
    raw = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRT",
            "-z",
            merge_base,
            head_sha,
            "--",
            "tests/",
        ]
    )
    return select_test_paths(parse_paths(raw))


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Base commit SHA")
    parser.add_argument("head", help="Head commit SHA")
    args = parser.parse_args()
    sys.stdout.write(format_report(changed_paths_from_merge_base(args.base, args.head)))
