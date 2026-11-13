#!/usr/bin/env python3
"""Reject private workspace material from staged and tracked public files."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from pathlib import Path, PurePosixPath


PRIVATE_SUFFIXES = (".xlsx", ".xls", ".sqlite", ".sqlite3", ".db", ".7z", ".pem", ".key", ".p12", ".pfx", ".kdbx", ".log")
PRIVATE_PARTS = {"private", "backup", "backups", "credentials", "checkpoints", "snapshots", "ledgers", "gestion-jobs", "gestion-app", "workspace-governance", "adapters", "reports", "research"}
PRIVATE_TERMS = ("source-checkpoint", "raw-response", "evidence-ledger", "firebase_backups", "workspace_inventory", "workspace-inventory")
PRIVATE_SCRIPT_NAMES = {"import_private_rooms_to_catalog.py", "audit_room_states.cjs",
                        "prepare_scream_editorial_release.py"}
PRIVATE_SCRIPT_PREFIXES = ("collect_", "download_", "scrape_", "research_", "detect_", "enrich_", "import_private_", "build_catalog_")
PRIVATE_DOCUMENT_NAMES = {"agents.md", "workspace_and_privacy.md", "private_documentation_plan.md", "public_exposure_audit.md"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9_]{35,}"),
    re.compile(rb"(?i)[a-z]:[\\/]+users[\\/]+[^\\/\s]+[\\/]"),
    re.compile(rb"(?i)file:///(?:[a-z]:/|users/)"),
    re.compile(rb'(?i)"(?:source_checkpoint|raw_response|external_source_id|source_entity_scope)"\s*:'),
)
TEXT_SUFFIXES = {".py", ".js", ".cjs", ".mjs", ".json", ".yml", ".yaml", ".md", ".txt", ".html", ".css", ".ps1"}
MAX_TEXT_BYTES = 20_000_000


def is_private_path(name: str) -> bool:
    clean = name.replace("\\", "/").lower()
    path = PurePosixPath(clean)
    return (path.suffix in PRIVATE_SUFFIXES or path.name == ".env" or path.name.startswith(".env.")
            or path.name in PRIVATE_DOCUMENT_NAMES or clean.startswith("docs/standards/")
            or (path.suffix == ".csv" and clean != "image_sources.example.csv")
            or path.name in PRIVATE_SCRIPT_NAMES
            or (path.parts[0] == "scripts" and path.name.startswith(PRIVATE_SCRIPT_PREFIXES))
            or any(part in PRIVATE_PARTS for part in path.parts)
            or any(term in clean for term in PRIVATE_TERMS)
            or path.name.endswith("-backup.json")
            or path.name.endswith("-snapshot.json"))


def tracked_paths(staged: bool = False) -> list[str]:
    args = ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"] if staged else ["git", "ls-files", "-z"]
    result = subprocess.run(args, check=True, capture_output=True)
    return [p.decode("utf-8", "replace") for p in result.stdout.split(b"\0") if p]


def private_reference(name: str) -> str:
    """Identify a blocked path locally without printing its sensitive name in CI."""
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]


def check(staged: bool = False) -> list[str]:
    errors = []
    for name in tracked_paths(staged):
        if is_private_path(name):
            errors.append(f"Archivo privado en Git (ref {private_reference(name)})")
            continue
        path = Path(name)
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if staged:
            blob = subprocess.run(["git", "show", f":{name}"], capture_output=True)
            if blob.returncode != 0:
                errors.append(f"No se pudo inspeccionar el índice (ref {private_reference(name)})")
                continue
            data = blob.stdout
        else:
            if not path.is_file():
                errors.append(f"No se pudo inspeccionar archivo rastreado (ref {private_reference(name)})")
                continue
            if path.stat().st_size > MAX_TEXT_BYTES:
                errors.append(f"Archivo de texto demasiado grande para inspección (ref {private_reference(name)})")
                continue
            data = path.read_bytes()
        if len(data) > MAX_TEXT_BYTES:
            errors.append(f"Archivo de texto demasiado grande para inspección (ref {private_reference(name)})")
            continue
        if b"\0" in data[:4096]:
            errors.append(f"Archivo de texto binario no inspeccionable (ref {private_reference(name)})")
            continue
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            errors.append(f"Posible secreto en archivo público (ref {private_reference(name)})")
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
