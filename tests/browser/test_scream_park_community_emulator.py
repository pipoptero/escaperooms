"""End-to-end public opinion write through the existing client and Auth+RTDB emulators."""
import os
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from tests.browser.test_public_profile_emulator import (
    ROOT, QuietHandler, request_json, DATABASE_NAMESPACE, DB, AUTH
)


@unittest.skipUnless(os.getenv('VAULT_FIREBASE_EMULATOR') == '1', 'requiere Firebase Emulator')
class ScreamParkCommunityEmulatorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.alice = request_json(f'{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-key',
                                 'POST', {'email': 'scream-alice@example.test', 'password': 'Local-only-123!',
                                          'returnSecureToken': True})
        cls.bob = request_json(f'{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-key',
                               'POST', {'email': 'scream-bob@example.test', 'password': 'Local-only-123!',
                                        'returnSecureToken': True})
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv('VAULT_TEST_BROWSER', 'chromium')).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_publish_edit_public_read_and_delete(self):
        uid, token = self.alice['localId'], self.alice['idToken']
        context = self.browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        errors = []

        def route_request(route):
            url = route.request.url
            if urlparse(url).path.endswith('/firebase-config.js'):
                script = ("window.THE_VAULT_FIREBASE_CONFIG={databaseURL:"
                          "'http://127.0.0.1:9000?ns=demo-the-vault-default-rtdb',apiKey:'fake-key',"
                          "authDomain:'localhost',projectId:'demo-the-vault',appId:'1:1:web:test',"
                          "screamReviewsEnabled:true};")
                return route.fulfill(content_type='application/javascript', body=script)
            if url.startswith(('http://127.0.0.1:', 'data:')):
                return route.continue_()
            return route.abort()

        context.route('**/*', route_request)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(self.url, wait_until='load')
            page.evaluate("""({uid,token}) => {
              AUTH_USER = {uid, displayName:'Ana', getIdToken: async () => token};
              AUTH_TOKEN = token; USER_ID = uid;
            }""", {'uid': uid, 'token': token})
            page.locator('#tab-scream').click()
            page.locator('#panel-scream-parks article.card[data-id=horrorland] button').first.click()
            page.get_by_role('button', name='ESCRIBIR MI OPINIÓN').click()
            for category in ('ambientacion', 'acting', 'organizacion', 'terror', 'variedad'):
                page.locator(f'.sp-community-form .review-stars[data-category="{category}"]').click(position={'x': 70, 'y': 10})
            page.locator('.sp-community-form textarea').fill('Una experiencia intensa y divertida.')
            page.get_by_role('button', name='PUBLICAR OPINIÓN').click()
            page.locator('.sp-community-opinion').wait_for()
            path = f'screamParkReviews/horrorland-2026/{uid}'
            url = f'{DB}/{path}.json?ns={DATABASE_NAMESPACE}'
            record = request_json(url)
            self.assertEqual(record['revision'], 1)
            self.assertEqual(len(record['scores']), 5)
            self.assertNotIn('email', record)
            self.assertNotIn('PENDING', page.locator('#sp-community').inner_text())
            capture = os.getenv('VAULT_V61_CAPTURE_DIR')
            if capture:
                destination = Path(capture) / f'{self.browser.browser_type.name}-390-community-published.png'
                destination.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(destination), full_page=True)
            try:
                request_json(f'{url}&auth={self.bob["idToken"]}', 'DELETE')
                self.fail('Otro usuario eliminó una opinión ajena')
            except HTTPError as error:
                self.assertIn(error.code, (401, 403))
            page.get_by_role('button', name='EDITAR MI OPINIÓN').click()
            page.locator('.sp-community-form textarea').fill('Versión revisada de nuestra visita.')
            page.get_by_role('button', name='ACTUALIZAR OPINIÓN').click()
            page.wait_for_function("() => document.querySelector('.sp-community-opinion')?.textContent.includes('Versión revisada')")
            self.assertEqual(request_json(url)['revision'], 2)
            page.on('dialog', lambda dialog: dialog.accept())
            page.get_by_role('button', name='ELIMINAR MI OPINIÓN').click()
            page.wait_for_function("() => !document.querySelector('.sp-community-opinion')")
            self.assertIsNone(request_json(url))
            self.assertEqual(errors, [])
        finally:
            context.close()
