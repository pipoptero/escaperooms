import hashlib
import argparse
import io
import json
import re
import shutil
import tempfile
import unittest
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr

from scripts import sync_firebase_auth_helpers as sync
from scripts import check_firebase_auth_helpers_http as http_check


ROOT = Path(__file__).resolve().parents[1]
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


class FirebaseAuthHelperTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "firebase-auth-helpers.lock.json").read_text(encoding="utf-8"))

    def test_all_official_helper_files_match_locked_hashes(self):
        self.assertEqual(set(self.lock["files"]), set(HELPERS))
        for relative in HELPERS:
            body = (ROOT / relative).read_bytes()
            expected = self.lock["files"][relative]
            self.assertGreater(len(body), 0, relative)
            self.assertEqual(len(body), expected["bytes"], relative)
            self.assertEqual(hashlib.sha256(body).hexdigest(), expected["sha256"], relative)

    def test_init_json_is_the_expected_public_project_config(self):
        config = json.loads((ROOT / "__/firebase/init.json").read_text(encoding="utf-8"))
        self.assertEqual(config["projectId"], "scapesrooms")
        self.assertEqual(config["authDomain"], "scapesrooms.firebaseapp.com")
        for field in ("apiKey", "appId", "databaseURL"):
            self.assertTrue(config.get(field), field)
        forbidden = {"clientSecret", "privateKey", "accessToken", "refreshToken", "idToken", "password"}
        self.assertTrue(forbidden.isdisjoint(config))
        self.assertEqual(sync.validate("__/firebase/init.json", (ROOT / "__/firebase/init.json").read_bytes(), "application/json", 200), config)

    def test_init_rejects_wrong_app_and_private_or_unexpected_fields(self):
        original = json.loads((ROOT / "__/firebase/init.json").read_text(encoding="utf-8"))
        for changes in ({"appId": "1:other:web:other"}, {"apiKey": "not-a-key"},
                        {"private_key": "sensitive"}, {"client_secret": "sensitive"},
                        {"profile": {"email": "private@example.test"}}):
            with self.subTest(fields=list(changes)):
                body = json.dumps({**original, **changes}).encode()
                with self.assertRaises(ValueError):
                    sync.validate("__/firebase/init.json", body, "application/json", 200)
        with self.assertRaises(ValueError):
            sync.validate("__/firebase/init.json", b"[]", "application/json", 200)

    def test_404_fallback_requires_official_provenance_and_exact_pinned_bytes(self):
        source = ROOT / "__/firebase/init.json"
        self.assertEqual(sync.pinned_init_fallback(source, self.lock, sync.UPSTREAM), source.read_bytes())
        for lock in ({}, {**self.lock, "initFallback": {}},
                     {**self.lock, "initFallback": {**self.lock["initFallback"], "sha256": "0" * 64}}):
            with self.assertRaises(ValueError):
                sync.pinned_init_fallback(source, lock, sync.UPSTREAM)
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "init.json"
            changed.write_bytes(source.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                sync.pinned_init_fallback(changed, self.lock, sync.UPSTREAM)

    def test_sync_validates_all_downloads_before_any_asset_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "__", root / "__")
            shutil.copyfile(ROOT / "firebase-auth-helpers.lock.json", root / "firebase-auth-helpers.lock.json")
            before = {path: (root / path).read_bytes() for path in (*HELPERS, "firebase-auth-helpers.lock.json")}

            def fake_fetch(url):
                relative = url.removeprefix(sync.UPSTREAM + "/")
                if relative == "__/firebase/init.json":
                    return b"[]", "application/json", 200
                return before[relative] + b"\n", self.lock["files"][relative]["contentType"], 200, url

            args = argparse.Namespace(root=root, source_base=sync.UPSTREAM, check=False, report=None)
            with patch.object(sync, "parse_args", return_value=args), patch.object(sync, "fetch", side_effect=fake_fetch), redirect_stderr(io.StringIO()):
                self.assertEqual(sync.main(), 1)
            for path, data in before.items():
                self.assertEqual((root / path).read_bytes(), data, path)

    def test_sync_check_detects_drift_without_asset_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "__", root / "__")
            shutil.copyfile(ROOT / "firebase-auth-helpers.lock.json", root / "firebase-auth-helpers.lock.json")
            before = {path: (root / path).read_bytes() for path in (*HELPERS, "firebase-auth-helpers.lock.json")}

            def fake_fetch(url):
                relative = url.removeprefix(sync.UPSTREAM + "/")
                return before[relative] + (b"\n" if relative.endswith(".js") else b""), self.lock["files"][relative]["contentType"], 200, url

            args = argparse.Namespace(root=root, source_base=sync.UPSTREAM, check=True, report=None)
            with patch.object(sync, "parse_args", return_value=args), patch.object(sync, "fetch", side_effect=fake_fetch), redirect_stdout(io.StringIO()):
                self.assertEqual(sync.main(), 2)
            for path, data in before.items():
                self.assertEqual((root / path).read_bytes(), data, path)

    def test_http_checker_rejects_redirect_even_with_matching_bytes_and_mime(self):
        relative = "__/auth/handler"
        class Response:
            status = 200
            headers = {"Content-Type": "text/html"}
            def read(self):
                return (ROOT / relative).read_bytes()
            def geturl(self):
                return "https://example.test/__/auth/handler.html"
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass
        with patch.object(urllib.request, "urlopen", return_value=Response()):
            result = http_check.check_helper("https://example.test", relative, self.lock["files"][relative])
        self.assertTrue(result["checks"]["sha256"])
        self.assertTrue(result["checks"]["contentType"])
        self.assertFalse(result["checks"]["exactUrlNoRedirect"])

    def test_http_checker_reports_network_errors_without_response_data(self):
        with patch.object(urllib.request, "urlopen", side_effect=OSError("private transport details")):
            result = http_check.check_helper("https://example.test", "__/auth/handler", self.lock["files"]["__/auth/handler"])
        self.assertFalse(result["checks"]["network"])
        self.assertNotIn("private transport", json.dumps(result))

    def test_sync_follows_only_same_origin_upstream_redirects(self):
        url = f"{sync.UPSTREAM}/__/auth/handler"

        class Response:
            status = 200
            headers = {"Content-Type": "text/html"}
            def __init__(self, resolved_url):
                self.resolved_url = resolved_url
            def read(self):
                return b"official helper"
            def geturl(self):
                return self.resolved_url
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                pass

        redirected = url + "?revision=1"
        with patch.object(urllib.request, "urlopen", return_value=Response(redirected)):
            self.assertEqual(sync.fetch(url), (b"official helper", "text/html", 200, redirected))
        with patch.object(urllib.request, "urlopen", return_value=Response("https://example.test/handler")):
            with self.assertRaises(ValueError):
                sync.fetch(url)

    def test_helpers_do_not_contain_private_credentials(self):
        patterns = (
            rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            rb'"(?:clientSecret|privateKey|accessToken|refreshToken|idToken)"\s*:\s*"[^"\s]+"',
            rb"\bya29\.[A-Za-z0-9_-]{20,}\b",
        )
        for relative in HELPERS:
            body = (ROOT / relative).read_bytes()
            for pattern in patterns:
                self.assertIsNone(re.search(pattern, body, re.I), relative)

    def test_pages_artifact_includes_double_underscore_tree(self):
        workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertIn("cp -R __ public-site/", workflow)
        self.assertIn("touch public-site/.nojekyll", workflow)
        self.assertIn('mv "public-site/__/auth/${helper}" "public-site/__/auth/${helper}.html"', workflow)

    def test_pages_extensionless_html_adaptation_preserves_official_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "__"
            shutil.copytree(ROOT / "__", artifact)
            for name in ("handler", "iframe", "links"):
                source = artifact / "auth" / name
                expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
                target = source.with_suffix(".html")
                source.rename(target)
                self.assertFalse(source.exists())
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected_hash)

    def test_local_pages_like_preview_serves_exact_urls_mime_and_bytes(self):
        class PagesLikeHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                if self.path in ("/__/auth/handler", "/__/auth/iframe", "/__/auth/links"):
                    self.path += ".html"
                return super().do_GET()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "__", root / "__")
            for name in ("handler", "iframe", "links"):
                source = root / "__" / "auth" / name
                source.rename(source.with_suffix(".html"))
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(PagesLikeHandler, directory=str(root)))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for relative in HELPERS:
                    with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/{relative}") as response:
                        body = response.read()
                        content_type = response.headers.get_content_type()
                    self.assertEqual(response.status, 200, relative)
                    expected_types = {"text/html"} if relative in {
                        "__/auth/handler", "__/auth/iframe", "__/auth/links"
                    } else {"text/javascript", "application/javascript"} if relative.endswith(".js") else {"application/json"}
                    self.assertIn(content_type, expected_types, relative)
                    self.assertEqual(hashlib.sha256(body).hexdigest(), self.lock["files"][relative]["sha256"], relative)
            finally:
                server.shutdown()
                server.server_close()

    def test_service_worker_bypasses_reserved_auth_namespace_before_navigation(self):
        source = (ROOT / "service-worker.js").read_text(encoding="utf-8")
        bypass = "url.pathname.startsWith('/__/auth/') || url.pathname === '/__/firebase/init.json'"
        self.assertIn(bypass, source)
        self.assertIn("the-vault-v53", source)
        self.assertLess(source.index(bypass), source.index("request.mode === 'navigate'"))
        app_shell = source[source.index("const APP_SHELL"):source.index("const DATA_FILES")]
        self.assertNotIn("__/auth", app_shell)
        self.assertNotIn("__/firebase", app_shell)

    def test_same_origin_candidate_is_documented_and_not_part_of_pages_artifact(self):
        plan = (ROOT / "docs/FIREBASE_AUTH_SAME_ORIGIN.md").read_text(encoding="utf-8")
        self.assertIn("authDomain    thevaultescape.com", plan)
        candidate = (ROOT / "firebase-config.same-origin.example.js").read_text(encoding="utf-8")
        self.assertIn("authDomain: 'thevaultescape.com'", candidate)
        self.assertIn("projectId: 'scapesrooms'", candidate)
        self.assertIn("<EXISTING_FIREBASE_API_KEY>", candidate)
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="firebase-config.js?v=53"></script>', html)
        self.assertIn('>PWA v53</span>', html)
        workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")
        self.assertNotIn("firebase-config.same-origin.example.js", workflow)
        self.assertIn("authDomain: 'thevaultescape.com'", workflow)
        self.assertNotIn("secrets.FIREBASE_AUTH_DOMAIN", workflow)


if __name__ == "__main__":
    unittest.main()
