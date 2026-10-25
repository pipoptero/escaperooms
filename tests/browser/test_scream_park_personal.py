"""Scream Parks personal controls with fictitious accounts and an in-memory transport."""

import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT.parent / 'v4-states-artifacts'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


class ScreamParkPersonalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.playwright = sync_playwright().start()
        cls.browser_name = os.getenv('VAULT_TEST_BROWSER', 'chromium')
        cls.browser = getattr(cls.playwright, cls.browser_name).launch()
        ARTIFACTS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def page(self, width):
        context = self.browser.new_context(viewport={'width': width, 'height': 850}, service_workers='block')
        page = context.new_page()
        if page.evaluate('innerWidth') != width:
            actual = page.evaluate('innerWidth')
            page.set_viewport_size({'width': round(width * width / actual), 'height': round(850 * width / actual)})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(f'http://127.0.0.1:{self.server.server_port}/', wait_until='domcontentloaded')
        self.assertEqual(response.status, 200)
        return context, page, errors

    def install_fake_account(self, context, page, backend, uid='alice'):
        def read(_source, path):
            if backend['fail']:
                raise RuntimeError('network offline')
            if path in backend['data']:
                return backend['data'][path]
            result = {}
            for key, value in backend['data'].items():
                if key.startswith(path + '/'):
                    parts = key[len(path) + 1:].split('/')
                    if len(parts) == 2:
                        result.setdefault(parts[0], {})[parts[1]] = value
            return result or None

        def put(_source, path, value):
            if backend['fail']:
                raise RuntimeError('network offline')
            backend['data'][path] = value

        def remove(_source, path):
            if backend['fail']:
                raise RuntimeError('network offline')
            backend['data'].pop(path, None)

        context.expose_binding('__spTestRead', read)
        context.expose_binding('__spTestPut', put)
        context.expose_binding('__spTestRemove', remove)
        page.evaluate("""async uid => {
          AUTH_USER = {uid}; USER_ID = uid;
          window.VaultScreamParkStates = VaultScreamParkPersonalState.create({
            read: window.__spTestRead, put: window.__spTestPut, remove: window.__spTestRemove,
            onChange: () => { window.TheVaultScreamParksPreview?.current?.refreshStates(); renderScreamParkLists(); }
          });
          window.VaultScreamParkStates.setSession(uid);
          await loadScreamParkEntries();
          await window.VaultScreamParkStates.load();
          switchTab('scream-parks');
        }""", uid)
        page.locator('#panel-scream-parks article.card').first.wait_for()

    def test_guest_and_account_states_desktop_mobile(self):
        for width in (1440, 390):
            with self.subTest(width=width):
                context, page, errors = self.page(width)
                try:
                    page.locator('#tab-scream').click()
                    page.locator('#panel-scream-parks article.card').first.wait_for()
                    self.assertEqual(page.locator('#panel-scream-parks article.card').count(), 22)
                    self.assertEqual(page.locator('#panel-scream-parks .sp-state-button').count(), 0)
                    backend = {'data': {}, 'fail': False}
                    self.install_fake_account(context, page, backend)
                    card = page.locator('#panel-scream-parks article.card[data-id="the-village"]')
                    card.locator('.sp-state-button.pending').click()
                    page.wait_for_function("() => document.querySelector('.card[data-id=\"the-village\"] .sp-state-button.pending')?.getAttribute('aria-pressed') === 'true'")
                    self.assertEqual(backend['data']['screamParkUserStates/alice/editions/the-village-2026']['pending'], True)
                    page.evaluate("switchTab('pendientes')")
                    self.assertEqual(page.locator('#sp-pending-count').inner_text(), '1')
                    page.evaluate("document.querySelector('#sp-pending-list')?.scrollIntoView()")
                    page.screenshot(path=str(ARTIFACTS / f'{self.browser_name}-{width}-pending.png'))
                    page.evaluate("switchTab('scream-parks')")
                    card.locator('.sp-state-button.done').click()
                    page.wait_for_function("() => document.querySelector('.card[data-id=\"the-village\"] .sp-state-button.done')?.getAttribute('aria-pressed') === 'true'")
                    self.assertFalse(backend['data']['screamParkUserStates/alice/editions/the-village-2026']['pending'])
                    card.locator('.sp-state-button.favorite').click()
                    page.wait_for_function("() => document.querySelector('.card[data-id=\"the-village\"] .sp-state-button.favorite')?.getAttribute('aria-pressed') === 'true'")
                    self.assertEqual(backend['data']['screamParkUserStates/alice/favorites/the-village'], True)
                    self.assertEqual(page.evaluate('personalDoneRoomIds().length'), 0)
                    page.screenshot(path=str(ARTIFACTS / f'{self.browser_name}-{width}-cards.png'), full_page=True)
                    card.get_by_role('button', name='VER FICHA').click()
                    page.locator('#sp-detail .sp-state-button.favorite.active').wait_for()
                    page.screenshot(path=str(ARTIFACTS / f'{self.browser_name}-{width}-detail.png'), full_page=True)
                    page.locator('#sp-back').click()
                    page.evaluate("switchTab('mis-hechos')")
                    self.assertEqual(page.locator('#sp-done-count').inner_text(), '1')
                    self.assertEqual(page.locator('#badge-mine').inner_text(), '0')
                    page.evaluate("switchTab('pendientes')")
                    self.assertEqual(page.locator('#sp-pending-count').inner_text(), '0')
                    page.evaluate("SETTINGS_TAB='profile'; renderProfile()")
                    self.assertIn('The Village', page.locator('#sp-profile-section').inner_text())
                    page.evaluate("openProfile('', false)")
                    page.locator('#profile-modal.open #sp-profile-section').wait_for()
                    page.evaluate("document.querySelector('#sp-profile-section')?.scrollIntoView()")
                    page.screenshot(path=str(ARTIFACTS / f'{self.browser_name}-{width}-profile.png'))
                    page.screenshot(path=str(ARTIFACTS / f'{self.browser_name}-{width}.png'), full_page=True)
                    page.reload(wait_until='domcontentloaded')
                    page.evaluate("""async () => {
                      AUTH_USER = {uid:'alice'}; USER_ID = 'alice';
                      window.VaultScreamParkStates = VaultScreamParkPersonalState.create({
                        read: window.__spTestRead, put: window.__spTestPut, remove: window.__spTestRemove,
                        onChange: () => { window.TheVaultScreamParksPreview?.current?.refreshStates(); renderScreamParkLists(); }
                      });
                      window.VaultScreamParkStates.setSession('alice');
                      await loadScreamParkEntries();
                      await window.VaultScreamParkStates.load();
                      switchTab('scream-parks');
                    }""")
                    restored = page.locator('#panel-scream-parks article.card[data-id="the-village"]')
                    restored.locator('.sp-state-button.done.active').wait_for()
                    self.assertEqual(restored.locator('.sp-state-button.favorite').get_attribute('aria-pressed'), 'true')
                    self.assertEqual(page.evaluate('personalDoneRoomIds().length'), 0)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width + 1)
                    self.assertEqual(errors, [])
                finally:
                    context.close()

    def test_network_error_and_second_account(self):
        context, page, errors = self.page(390)
        try:
            backend = {'data': {}, 'fail': False}
            self.install_fake_account(context, page, backend)
            backend['fail'] = True
            card = page.locator('#panel-scream-parks article.card[data-id="horrorland"]')
            card.locator('.sp-state-button.done').click()
            page.wait_for_function("() => document.querySelector('.card[data-id=\"horrorland\"] .sp-personal-status')?.textContent.includes('No se pudo guardar')")
            self.assertFalse(backend['data'])
            backend['fail'] = False
            page.evaluate("window.VaultScreamParkStates.setSession('bob'); AUTH_USER={uid:'bob'}; USER_ID='bob'")
            card.locator('.sp-state-button.done').click()
            page.wait_for_function("() => document.querySelector('.card[data-id=\"horrorland\"] .sp-state-button.done')?.getAttribute('aria-pressed') === 'true'")
            self.assertIn('screamParkUserStates/bob/editions/horrorland-2026', backend['data'])
            self.assertNotIn('screamParkUserStates/alice/editions/horrorland-2026', backend['data'])
            self.assertEqual(errors, [])
        finally:
            context.close()

    def test_pwa_shell_includes_personal_state_module(self):
        context = self.browser.new_context(service_workers='allow')
        page = context.new_page()
        try:
            page.goto(f'http://127.0.0.1:{self.server.server_port}/', wait_until='domcontentloaded')
            cached = page.evaluate("""async () => {
              await navigator.serviceWorker.register('/service-worker.js');
              await navigator.serviceWorker.ready;
              const shell = await caches.open('the-vault-v58-shell');
              return !!(await shell.match('/scream-parks/personal-state.js'));
            }""")
            self.assertTrue(cached)
        finally:
            context.close()
