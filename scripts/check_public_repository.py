#!/usr/bin/env python3
"""Reject private research artifacts before a public release."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath


PRIVATE_SUFFIXES = (".xlsx", ".xls", ".sqlite", ".sqlite3", ".db", ".7z", ".pem", ".key", ".p12", ".pfx", ".kdbx")
PRIVATE_PARTS = {"private", "backup", "backups", "credentials", "checkpoints"}
PRIVATE_TERMS = ("source-checkpoint", "raw-response", "evidence-ledger", "firebase_backups")
PRIVATE_SCRIPT_NAMES = {"import_private_rooms_to_catalog.py", "audit_room_states.cjs",
                        "prepare_scream_editorial_release.py"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{35,}"),
)
TEXT_SUFFIXES = {".py", ".js", ".cjs", ".mjs", ".json", ".yml", ".yaml", ".md", ".txt", ".html", ".css", ".ps1"}
GENERATED_PREFIXES = ("salas/", "reviews/", "escape-rooms", "ranking/", "mejores-escape-rooms")


def is_private_path(name: str) -> bool:
    clean = name.replace("\\", "/").lower()
    path = PurePosixPath(clean)
    return (path.suffix in PRIVATE_SUFFIXES or path.name == ".env" or path.name.startswith(".env.")
            or path.name in PRIVATE_SCRIPT_NAMES
            or any(part in PRIVATE_PARTS for part in path.parts)
            or any(term in clean for term in PRIVATE_TERMS)
            or path.name.endswith("-backup.json"))


def tracked_paths(staged: bool = False) -> list[str]:
    args = ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"] if staged else ["git", "ls-files", "-z"]
    result = subprocess.run(args, check=True, capture_output=True)
    return [p.decode("utf-8", "replace") for p in result.stdout.split(b"\0") if p]


def check(staged: bool = False) -> list[str]:
    errors = []
    for name in tracked_paths(staged):
        if is_private_path(name):
            errors.append(f"Archivo privado en Git: {name}")
            continue
        path = Path(name)
        if path.suffix.lower() not in TEXT_SUFFIXES or (not staged and name.startswith(GENERATED_PREFIXES)):
            continue
        if staged:
            blob = subprocess.run(["git", "show", f":{name}"], capture_output=True)
            if blob.returncode != 0:
                errors.append(f"No se pudo inspeccionar el índice: {name}")
                continue
            data = blob.stdout
        else:
            if not path.is_file() or path.stat().st_size > 20_000_000:
                continue
            data = path.read_bytes()
        if b"\0" in data[:4096] or len(data) > 20_000_000:
            continue
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            errors.append(f"Posible secreto en: {name}")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    failures = check(args.staged)
    for failure in failures:
        print(failure)
    if failures:
        raise SystemExit(1)
    print("Public repository guard: PASS")
