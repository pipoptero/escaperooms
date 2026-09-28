#!/usr/bin/env python3
"""Verify deployed Firebase Auth helpers without exposing their bodies."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

try:
    from .sync_firebase_auth_helpers import EXPECTED_MEDIA_TYPES, HELPERS, media_type
except ImportError:  # Direct CLI execution.
    from sync_firebase_auth_helpers import EXPECTED_MEDIA_TYPES, HELPERS, media_type


def check_helper(base_url: str, relative: str, expected: dict) -> dict:
    url = f"{base_url.rstrip('/')}/{relative}"
    request = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache", "Accept-Encoding": "identity",
        "User-Agent": "TheVault-AuthHelperCheck/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = response.status
            content_type = response.headers.get("Content-Type", "")
            cache_control = response.headers.get("Cache-Control", "")
            unchanged_url = response.geturl() == url
    except urllib.error.HTTPError as error:
        status = error.code
        content_type = error.headers.get("Content-Type", "")
        cache_control = error.headers.get("Cache-Control", "")
        body = error.read()
        unchanged_url = error.geturl() == url
    except (OSError, urllib.error.URLError) as error:
        return {"path": relative, "error": type(error).__name__, "checks": {"network": False}}

    digest = hashlib.sha256(body).hexdigest()
    return {
        "path": relative, "status": status, "contentType": content_type,
        "cacheControl": cache_control, "bytes": len(body), "sha256": digest,
        "checks": {
            "status": status == 200,
            "contentType": media_type(content_type) in EXPECTED_MEDIA_TYPES[relative],
            "sha256": digest == expected["sha256"],
            "bytes": len(body) == expected["bytes"],
            "exactUrlNoRedirect": unchanged_url,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Origin to verify, for example https://thevaultescape.com")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        parser.error("--base-url must be an origin without credentials, path, query or fragment")

    lock = json.loads((args.root / "firebase-auth-helpers.lock.json").read_text(encoding="utf-8"))
    failures = []
    for relative in HELPERS:
        result = check_helper(args.base_url, relative, lock["files"][relative])
        if not all(result["checks"].values()):
            failures.append(relative)
        print(json.dumps(result, ensure_ascii=False))

    if failures:
        print(f"FAIL: {len(failures)} helper routes failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"PASS: {len(HELPERS)} helper routes match status, MIME and SHA-256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
