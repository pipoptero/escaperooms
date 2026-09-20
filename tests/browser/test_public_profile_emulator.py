"""Authenticated browser smoke against Firebase Auth + RTDB Emulator.

Run under:
  firebase emulators:exec --only auth,database --project demo-the-vault \
    "python -B -m unittest tests.browser.test_public_profile_emulator -v"
"""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
DATABASE_NAMESPACE = 'demo-the-vault-default-rtdb'
DB = 'http://127.0.0.1:9000'
AUTH = 'http://127.0.0.1:9099'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def request_json(url, method='GET', payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=body, method=method, headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=10) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


@unittest.skipUnless(os.getenv('VAULT_FIREBASE_EMULATOR') == '1', 'requiere Firebase Emulator')
class PublicProfileEmulatorBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.account = request_json(
            f'{AUTH}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-key',
            'POST', {'email': 'codex-public-profile@example.test', 'password': 'Local-only-123!', 'returnSecureToken': True}
        )
        cls.playwright = sync_playwright().start()
        browser_name = os.getenv('VAULT_TEST_BROWSER', 'chromium')
        cls.browser = getattr(cls.playwright, browser_name).launch()

    @classmethod
    def tearDownClass(cls):
        try:
            token = cls.account['idToken']
            uid = cls.account['localId']
            for path in ['publicProfiles/emulator-profile', 'publicProfiles/emulator-renamed', f'publicProfileControls/{uid}',
                         'publicProfileOwners/emulator-profile', 'publicProfileOwners/emulator-renamed']:
                try:
                    request_json(f'{DB}/{path}.json?ns={DATABASE_NAMESPACE}&auth={token}', 'DELETE')
                except HTTPError:
                    pass
            request_json(f'{AUTH}/identitytoolkit.googleapis.com/v1/accounts:delete?key=fake-key', 'POST', {'idToken': token})
        finally:
            cls.browser.close()
            cls.playwright.stop()
            cls.server.shutdown()
            cls.server.server_close()

    def test_authenticated_publish_privacy_and_unpublish(self):
        uid = self.account['localId']
        token = self.account['idToken']
        context = self.browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')

        def route_request(route):
            url = route.request.url
            if url.endswith('/firebase-config.js'):
                script = "window.THE_VAULT_FIREBASE_CONFIG={databaseURL:'http://127.0.0.1:9000?ns=demo-the-vault-default-rtdb',apiKey:'fake-key',authDomain:'localhost',projectId:'demo-the-vault',appId:'1:1:web:test'};"
                return route.fulfill(content_type='application/javascript', body=script)
            if url.startswith(('http://127.0.0.1:', 'data:')):
                return route.continue_()
            return route.abort()

        context.route('**/*', route_request)
        page = context.new_page()
        page.goto(self.url, wait_until='load')
        page.evaluate("""async ({uid,token}) => {
          loadLiveDataAfterInitialRender = async () => {};
          AUTH_USER = {uid, email:'codex-public-profile@example.test'};
          AUTH_TOKEN = token; USER_ID = uid;
          USER_PROFILE = {publicName:'Emulator', equippedAvatar:'avatar_vault', equippedFrame:'frame_none'};
          USER_ROOM_STATES = {olimpo:{id:'olimpo', nombre:'Olimpo', done:true, pending:false, updatedAt:100}};
          CATALOGO = (await (await fetch('catalog.json')).json()).catalogo;
          CATALOG_LOADED = true;
          await ensureStaticEnhancementsLoaded(); await loadRoomAliases(); await loadPublicProfileControl();
          renderAuthStatus(); openProfile('', false);
        }""", {'uid': uid, 'token': token})

        page.locator('#public-profile-username').fill('Emulator Profile')
        page.get_by_role('button', name='Guardar perfil público').click()
        page.wait_for_function("PUBLIC_PROFILE_CONTROL.currentUsername === 'emulator-profile'")
        reserved_owner = request_json(f'{DB}/publicProfileOwners/emulator-profile.json?ns={DATABASE_NAMESPACE}&auth={token}')
        self.assertEqual(reserved_owner['state'], 'active')
        try:
            reserved_view = request_json(f'{DB}/publicProfiles/emulator-profile/view.json?ns={DATABASE_NAMESPACE}')
        except HTTPError:
            reserved_view = None
        self.assertIsNone(reserved_view)

        page.locator('#public-profile-published').check(force=True)
        page.locator('#public-show-stats').check()
        page.locator('#public-show-map').check()
        page.get_by_role('button', name='Guardar perfil público').click()
        expect(page.locator('#public-profile-demo-status')).to_contain_text('Perfil publicado')
        view = request_json(f'{DB}/publicProfiles/emulator-profile/view.json?ns={DATABASE_NAMESPACE}')
        self.assertEqual(view['username'], 'emulator-profile')
        self.assertEqual(view['stats']['personalEscapes'], 1)
        self.assertIn('map', view)
        self.assertNotIn(uid, json.dumps(view))
        self.assertNotIn('codex-public-profile@example.test', json.dumps(view))

        page.get_by_role('button', name='Guardar perfil público').click()
        page.wait_for_function("PUBLIC_PROFILE_CONTROL.published === true")
        repeated_view = request_json(f'{DB}/publicProfiles/emulator-profile/view.json?ns={DATABASE_NAMESPACE}')
        self.assertEqual(repeated_view['username'], 'emulator-profile')
        self.assertEqual(repeated_view['stats']['personalEscapes'], 1)
        self.assertIn('map', repeated_view)

        captured_public_payloads = []
        public_page = context.new_page()
        public_page.on('response', lambda response: captured_public_payloads.append(response.text())
                       if '/publicProfiles/' in response.url and response.ok else None)
        public_page.goto(f'{self.url}/escapista/?u=emulator-profile', wait_until='networkidle')
        public_page.wait_for_function("document.getElementById('profile-loading').hidden")
        expect(public_page.locator('#profile-public')).to_be_visible()
        expect(public_page.get_by_text('Emulator', exact=True)).to_be_visible()
        public_serialized = '\n'.join(captured_public_payloads)
        self.assertNotIn(uid, public_serialized)
        self.assertNotIn('codex-public-profile@example.test', public_serialized)
        self.assertNotIn('groupId', public_serialized)

        page.locator('#public-show-stats').uncheck()
        page.get_by_role('button', name='Guardar perfil público').click()
        page.wait_for_function("PUBLIC_PROFILE_CONTROL.visibility.showStats === false")
        view = request_json(f'{DB}/publicProfiles/emulator-profile/view.json?ns={DATABASE_NAMESPACE}')
        self.assertNotIn('stats', view)
        public_page.reload(wait_until='networkidle')
        public_page.wait_for_function("document.getElementById('profile-loading').hidden")
        expect(public_page.get_by_text('Estadísticas personales')).to_have_count(0)

        page.locator('#public-show-map').uncheck()
        page.get_by_role('button', name='Guardar perfil público').click()
        page.wait_for_function("PUBLIC_PROFILE_CONTROL.visibility.showMap === false")
        view = request_json(f'{DB}/publicProfiles/emulator-profile/view.json?ns={DATABASE_NAMESPACE}')
        self.assertNotIn('map', view)
        self.assertNotIn('latitude', json.dumps(view).lower())
        self.assertNotIn('longitude', json.dumps(view).lower())
        self.assertNotIn('coordinates', json.dumps(view).lower())

        page.locator('#public-profile-username').fill('emulator-renamed')
        page.get_by_role('button', name='Guardar perfil público').click()
        page.wait_for_function("PUBLIC_PROFILE_CONTROL.currentUsername === 'emulator-renamed'")
        try:
            old_payload = request_json(f'{DB}/publicProfiles/emulator-profile/view.json?ns={DATABASE_NAMESPACE}')
        except HTTPError:
            old_payload = None
        remote_control = request_json(f'{DB}/publicProfileControls/{uid}.json?ns={DATABASE_NAMESPACE}&auth={token}')
        self.assertIsNone(old_payload, json.dumps({'control': remote_control, 'oldPayload': old_payload}, ensure_ascii=False))
        public_page.reload(wait_until='networkidle')
        public_page.wait_for_function("['profile-unavailable','profile-error','profile-public'].some(id => !document.getElementById(id).hidden)")
        state = public_page.evaluate("['profile-unavailable','profile-error','profile-public'].find(id => !document.getElementById(id).hidden)")
        self.assertEqual(state, 'profile-unavailable')
        renamed_page = context.new_page()
        renamed_page.goto(f'{self.url}/escapista/?u=emulator-renamed', wait_until='networkidle')
        renamed_page.wait_for_function("document.getElementById('profile-loading').hidden")
        expect(renamed_page.locator('#profile-public')).to_be_visible()

        page.locator('#public-profile-published').uncheck(force=True)
        page.get_by_role('button', name='Guardar perfil público').click()
        page.wait_for_function("PUBLIC_PROFILE_CONTROL.published === false")
        try:
            unavailable = request_json(f'{DB}/publicProfiles/emulator-renamed/view.json?ns={DATABASE_NAMESPACE}')
        except HTTPError:
            unavailable = None
        self.assertIsNone(unavailable)
        renamed_page.reload(wait_until='networkidle')
        renamed_page.wait_for_function("['profile-unavailable','profile-error','profile-public'].some(id => !document.getElementById(id).hidden)")
        state = renamed_page.evaluate("['profile-unavailable','profile-error','profile-public'].find(id => !document.getElementById(id).hidden)")
        self.assertEqual(state, 'profile-unavailable')
        context.close()
