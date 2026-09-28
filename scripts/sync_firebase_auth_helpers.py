#!/usr/bin/env python3
"""Synchronise Firebase Auth helper assets for same-origin sign-in.

The files are copied byte-for-byte from the project's Firebase Hosting domain.
The generated lock file is intentionally public metadata: it contains hashes,
sizes and response MIME types, but never response bodies or credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path


UPSTREAM = "https://scapesrooms.firebaseapp.com"
PROJECT_ID = "scapesrooms"
AUTH_DOMAIN = "scapesrooms.firebaseapp.com"
APP_ID = "1:355203547760:web:25cb7dd64d2e793f12aab5"
DATABASE_URL = "https://scapesrooms-default-rtdb.europe-west1.firebasedatabase.app"
HELPERS = (
    "__/auth/handler",
    "__/auth/handler.js",
    "__/auth/experiments.js",
    "__/auth/iframe",
    "__/auth/iframe.js",
    "__/auth/links",
    "__/auth/links.js",
    "__/firebase/init.json",
)
EXPECTED_MEDIA_TYPES = {
    "__/auth/handler": {"text/html"},
    "__/auth/handler.js": {"application/javascript", "text/javascript"},
    "__/auth/experiments.js": {"application/javascript", "text/javascript"},
    "__/auth/iframe": {"text/html"},
    "__/auth/iframe.js": {"application/javascript", "text/javascript"},
    "__/auth/links": {"text/html"},
    "__/auth/links.js": {"application/javascript", "text/javascript"},
    "__/firebase/init.json": {"application/json"},
}
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb'"(?:clientSecret|privateKey|accessToken|refreshToken|idToken)"\s*:\s*"[^"\s]+"', re.I),
    re.compile(rb"\bya29\.[A-Za-z0-9_-]{20,}\b"),
)
FORBIDDEN_INIT_KEYS = {
    "clientsecret", "privatekey", "privatekeyid", "accesstoken",
    "refreshtoken", "idtoken", "password",
}
PUBLIC_INIT_KEYS = {
    "projectId", "appId", "databaseURL", "storageBucket", "apiKey", "authDomain",
    "messagingSenderId", "measurementId", "projectNumber", "version",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def media_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def fetch(url: str) -> tuple[bytes, str, int, str]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "TheVault-FirebaseAuthHelperSync/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        resolved_url = response.geturl()
        requested = urlsplit(url)
        resolved = urlsplit(resolved_url)
        if (resolved.scheme, resolved.netloc) != (requested.scheme, requested.netloc):
            raise ValueError("Upstream redirected a helper request outside the official origin")
        return response.read(), response.headers.get("Content-Type", ""), response.status, resolved_url


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def validate(path: str, data: bytes, content_type: str, status: int) -> dict | None:
    if status != 200:
        raise ValueError(f"{path}: HTTP {status}, expected 200")
    if not data:
        raise ValueError(f"{path}: empty response")
    actual_type = media_type(content_type)
    if actual_type not in EXPECTED_MEDIA_TYPES[path]:
        raise ValueError(f"{path}: unexpected Content-Type {content_type!r}")
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        if pattern.search(data):
            raise ValueError(f"{path}: response matches a forbidden secret pattern")

    if path != "__/firebase/init.json":
        if path in {"__/auth/handler", "__/auth/iframe", "__/auth/links"}:
            script = path.rsplit("/", 1)[1].encode("ascii") + b".js"
            if b"<html" not in data.lower() or script not in data:
                raise ValueError(f"{path}: not the expected helper HTML document")
        return None
    try:
        config = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: invalid UTF-8 JSON: {error}") from error
    if not isinstance(config, dict):
        raise ValueError(f"{path}: expected a public config object")
    if config.get("projectId") != PROJECT_ID:
        raise ValueError(f"{path}: unexpected projectId {config.get('projectId')!r}")
    if config.get("authDomain") != AUTH_DOMAIN:
        raise ValueError(f"{path}: unexpected upstream authDomain {config.get('authDomain')!r}")
    if config.get("appId") != APP_ID or config.get("databaseURL") != DATABASE_URL:
        raise ValueError(f"{path}: config does not belong to the expected Web App/database")
    if not isinstance(config.get("apiKey"), str) or not re.fullmatch(r"AIza[\w-]{35}", config["apiKey"]):
        raise ValueError(f"{path}: missing or invalid public Firebase apiKey")
    forbidden = sorted({key for key in walk_keys(config) if re.sub(r"[^a-z]", "", key.lower()) in FORBIDDEN_INIT_KEYS})
    if forbidden:
        raise ValueError(f"{path}: forbidden private fields present: {', '.join(forbidden)}")
    unexpected = sorted(set(config) - PUBLIC_INIT_KEYS)
    if unexpected or any(not isinstance(value, str) for value in config.values()):
        raise ValueError(f"{path}: unexpected fields/types in public config")
    return config


def pinned_init_fallback(destination: Path, lock: dict, source_base: str) -> bytes:
    """Never bootstrap or bless a changed local config when upstream returns 404."""
    provenance = lock.get("initFallback", {})
    expected = lock.get("files", {}).get("__/firebase/init.json", {})
    if (source_base != UPSTREAM or lock.get("upstream") != UPSTREAM
            or provenance.get("source") != "firebase-apps-sdkconfig"
            or provenance.get("projectId") != PROJECT_ID
            or provenance.get("appId") != APP_ID):
        raise ValueError("init.json 404: missing reviewed official SDK config provenance")
    data = destination.read_bytes()
    digest = sha256(data)
    if digest != provenance.get("sha256") or digest != expected.get("sha256") or len(data) != expected.get("bytes"):
        raise ValueError("init.json 404: local config differs from the reviewed official SDK config; refusing fallback")
    return data


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-base", default=UPSTREAM.rstrip("/"))
    parser.add_argument("--check", action="store_true", help="fail on drift without writing files")
    parser.add_argument("--report", type=Path, help="write a JSON run report (default: reports/...)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    source_base = args.source_base.rstrip("/")
    if source_base != UPSTREAM:
        print("ERROR: only the configured official Firebase upstream is allowed", file=sys.stderr)
        return 1
    lock_path = root / "firebase-auth-helpers.lock.json"
    old_lock = load_json(lock_path)
    results = []
    payloads: dict[str, bytes] = {}
    init_summary = None

    try:
        for relative in HELPERS:
            destination = root / Path(relative)
            source_url = f"{source_base}/{relative}"
            resolved_source = source_url
            source_mode = "upstream"
            upstream_status = 200
            try:
                data, response_type, status, resolved_source = fetch(source_url)
                if resolved_source != source_url:
                    source_mode = "upstream-same-origin-redirect"
            except urllib.error.HTTPError as error:
                if relative == "__/firebase/init.json" and error.code == 404 and destination.exists():
                    # Some Auth-enabled projects expose the Auth helpers before a
                    # Firebase Hosting release exists, so the reserved init.json
                    # can legitimately be absent. Keep the previously bootstrapped
                    # official Web App SDK config and validate it on every run.
                    data = pinned_init_fallback(destination, old_lock, source_base)
                    response_type = "application/json; source=official-firebase-sdk-config"
                    status = 200
                    upstream_status = 404
                    source_mode = "existing-official-sdk-config"
                else:
                    raise ValueError(f"{relative}: upstream HTTP {error.code}") from error
            config = validate(relative, data, response_type, status)
            if config is not None:
                init_summary = {
                    "projectId": config.get("projectId"),
                    "authDomain": config.get("authDomain"),
                    "hasApiKey": bool(config.get("apiKey")),
                    "hasAppId": bool(config.get("appId")),
                    "hasDatabaseURL": bool(config.get("databaseURL")),
                }
            old_data = destination.read_bytes() if destination.exists() else None
            digest = sha256(data)
            payloads[relative] = data
            results.append({
                "path": relative,
                "source": source_url,
                "resolvedSource": resolved_source,
                "upstreamStatus": upstream_status,
                "sourceMode": source_mode,
                "contentType": response_type,
                "bytes": len(data),
                "sha256": digest,
                "action": "unchanged" if old_data == data else "would-update" if args.check else "updated",
            })
    except (OSError, ValueError, urllib.error.URLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    changed = [item for item in results if item["action"] != "unchanged"]
    if args.check and changed:
        for item in changed:
            print(f"DRIFT {item['path']} {item['sha256']}")
        return 2

    if not args.check:
        for item in results:
            if item["action"] == "updated":
                atomic_write(root / Path(item["path"]), payloads[item["path"]])

    lock_files = {
        item["path"]: {
            "sha256": item["sha256"],
            "bytes": item["bytes"],
            "contentType": item["contentType"],
        }
        for item in results
    }
    lock_equivalent = (
        old_lock.get("schemaVersion") == 1
        and old_lock.get("upstream") == source_base
        and old_lock.get("projectId") == PROJECT_ID
        and old_lock.get("files") == lock_files
    )
    lock = {
        "schemaVersion": 1,
        "upstream": source_base,
        "projectId": PROJECT_ID,
        "syncedAt": old_lock.get("syncedAt") if lock_equivalent else datetime.now(timezone.utc).isoformat(),
        "files": lock_files,
    }
    if old_lock.get("initFallback"):
        lock["initFallback"] = old_lock["initFallback"]
    lock_bytes = (json.dumps(lock, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    lock_changed = old_lock != lock
    if args.check and lock_changed:
        print("DRIFT firebase-auth-helpers.lock.json")
        return 2
    if not args.check and lock_changed:
        atomic_write(lock_path, lock_bytes)

    report_path = args.report or root / "reports" / "firebase-auth-helpers-sync.json"
    report = {
        "schemaVersion": 1,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "check" if args.check else "sync",
        "upstream": source_base,
        "files": results,
        "changedCount": len(changed),
        "lockChanged": lock_changed,
        "init": init_summary,
        "secretScan": "pass",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(report_path, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    print(f"Firebase Auth helpers: {len(results)} valid, {len(changed)} changed, secrets scan PASS")
    for item in results:
        print(f"{item['action']:>9}  {item['sha256']}  {item['contentType']:<35}  {item['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
