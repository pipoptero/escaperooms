#!/usr/bin/env python3
"""Detect an exact Vault release trailer and verify a read-only Actions job."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


TRAILER = "Vault-Managed-Release: true"


def git(*args: str, cwd: Path | None = None, input_text: str | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, input=input_text,
                            text=True, capture_output=True, encoding="utf-8", check=True)
    return result.stdout.strip()


def is_managed_release(cwd: Path | None = None) -> bool:
    message = git("log", "-1", "--format=%B", cwd=cwd)
    parsed = git("interpret-trailers", "--parse", cwd=cwd, input_text=message)
    matches = [line for line in parsed.splitlines()
               if line.split(":", 1)[0].casefold() == "vault-managed-release"]
    return matches == [TRAILER]


def verify_validation_only(expected_sha: str, cwd: Path | None = None) -> None:
    head = git("rev-parse", "HEAD", cwd=cwd)
    if not expected_sha or head != expected_sha:
        raise ValueError("Managed release HEAD differs from the triggering push")
    if git("status", "--porcelain", "--untracked-files=all", cwd=cwd):
        raise ValueError("Managed release validation left the worktree dirty")
    if git("rev-list", "--count", f"{expected_sha}..HEAD", cwd=cwd) != "0":
        raise ValueError("Managed release created an unexpected child commit")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("detect", "verify"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-sha", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args()
    if args.command == "detect":
        managed = is_managed_release()
        value = "true" if managed else "false"
        print("managed=" + value)
        if args.output:
            with args.output.open("a", encoding="utf-8") as stream:
                stream.write("managed=" + value + "\n")
        return 0
    verify_validation_only(args.expected_sha)
    print("Managed release HEAD unchanged; worktree clean; child commits 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
