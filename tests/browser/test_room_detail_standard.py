"""The shared escape detail template keeps structure when optional data is absent."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass


class RoomDetailStandardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv('VAULT_TEST_BROWSER', 'chromium')).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_rich_and_partial_room_share_sections(self):
        for width in (1440, 390):
            context = self.browser.new_context(viewport={'width': width, 'height': 900}, service_workers='block')
            page = context.new_page()
            page.goto(f'http://127.0.0.1:{self.server.server_port}/', wait_until='domcontentloaded')
            page.wait_for_function("() => CATALOGO.some(room => room.id === 'oh-fortuna')", timeout=15000)
            for room_id in ('el-secreto-de-los-krugger', 'oh-fortuna'):
                with self.subTest(width=width, room=room_id):
                    page.evaluate('(rid) => openDetail("catalogo", rid)', room_id)
                    page.locator('#detail-modal.open').wait_for(timeout=15000)
                    labels = page.locator('#detail-content .detail-meta .meta-key').all_text_contents()
                    self.assertEqual(labels[:6], ['Duración', 'Jugadores', 'Dificultad', 'Precio', 'Ubicación', 'País'])
                    sections = page.locator('#detail-content .detail-section-title').all_text_contents()
                    for title in ('Fuentes del índice global', 'Premios y nominaciones', 'Sinopsis'):
                        self.assertIn(title, sections)
                    score = page.locator('#detail-content .detail-score-panel.global .detail-score-value').inner_text()
                    self.assertNotEqual(score, '0/10')
                    if room_id == 'oh-fortuna':
                        self.assertEqual(score, 'Pendiente de valoración')
                        self.assertIn('Sin valoraciones disponibles', page.locator('#detail-content').inner_text())
                        self.assertIn('Sin premios registrados en The Vault', page.locator('#detail-content').inner_text())
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                    self.assertIn('assistant-card', page.evaluate(
                        "recommendationCard(CATALOGO.find(room => room.id === 'oh-fortuna'))"))
            context.close()
