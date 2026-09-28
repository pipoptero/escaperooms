"""Editorial/community regression in a local browser. No Firebase access."""

import os
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

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


class EditorialReviewBrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv('VAULT_TEST_BROWSER', 'chromium')).launch()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def test_editorial_copy_is_formatted_once_and_other_community_review_survives(self):
        for width in (390, 1280):
            with self.subTest(width=width):
                context = self.browser.new_context(viewport={'width': width, 'height': 844}, service_workers='block')
                context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname == '127.0.0.1' else route.abort())
                page = context.new_page()
                try:
                    page.goto(self.url + '/', wait_until='domcontentloaded')
                    result = page.evaluate("""() => {
                      const text = '## HISTORIA\\n\\nUna historia.\\n\\n## NUESTRA OPINIÓN\\n\\nMuy buena.';
                      const room = { id:'la-vitrina', nombre:'La Vitrina', empresa:'Fixture',
                        descripcion:text.replace(/\\n/g, ' '), historia:9, ambientacion:8,
                        _adminPublished:true, _editorialPublishedBy:'author' };
                      roomReviewsCache = { la_vitrina: {
                        author:{uid:'author',userName:'Autor',text,scores:{historia:4.5}},
                        other:{uid:'other',userName:'Otra persona',text:'Opinión diferente.',scores:{historia:4}},
                        sameTextOther:{uid:'sameTextOther',userName:'Autor distinto',text,scores:{historia:3}}
                      }};
                      const editorial = reviewBlockHtml(room);
                      const community = communityReviewsHtml(room, 'hechos');
                      document.getElementById('detail-content').innerHTML = editorial + community;
                      return {editorial, community, headings:document.querySelectorAll('.detail-review-text h4').length,
                        communityCount:document.querySelectorAll('.community-review').length,
                        overflow:document.documentElement.scrollWidth > innerWidth};
                    }""")
                    self.assertEqual(result['headings'], 2)
                    self.assertIn('Valoración por categorías', result['editorial'])
                    self.assertIn('Review The Vault', result['editorial'])
                    self.assertEqual(result['communityCount'], 2)
                    self.assertIn('Otra persona', result['community'])
                    self.assertIn('Autor distinto', result['community'])
                    self.assertNotIn('Autor</span>', result['community'])
                    self.assertFalse(result['overflow'])
                finally:
                    context.close()

    def test_profile_editor_requires_canonical_room_and_keeps_newlines(self):
        context = self.browser.new_context(service_workers='block')
        context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname == '127.0.0.1' else route.abort())
        page = context.new_page()
        try:
            page.goto(self.url + '/', wait_until='domcontentloaded')
            page.wait_for_function("CATALOGO.some(room => room.id === 'la-vitrina')", timeout=30000)
            result = page.evaluate("""() => {
              const ids = ['room-search','name','company','city','province','duration','difficulty',
                'rating','history','ambient','gameplay','gamemaster','text'];
              ids.forEach(id => { const input = document.createElement('textarea');
                input.id = 'admin-review-' + id; document.body.appendChild(input); });
              document.getElementById('admin-review-name').value = 'La Vitrina';
              document.getElementById('admin-review-text').value = 'HISTORIA\\n\\nPárrafo.';
              document.getElementById('admin-review-room-search').value = 'La Vitrina nombre libre';
              const invalid = adminReviewFromForm();
              const room = CATALOGO.find(item => item.id === 'la-vitrina');
              document.getElementById('admin-review-room-search').value = adminReviewRoomLabel(room);
              const valid = adminReviewFromForm();
              return {invalid: invalid.error, roomKey:valid.roomKey, id:valid.review.id,
                text:valid.review.descripcion};
            }""")
            self.assertIn('catálogo', result['invalid'])
            self.assertEqual(result['roomKey'], 'la_vitrina')
            self.assertEqual(result['id'], 'la-vitrina')
            self.assertEqual(result['text'], 'HISTORIA\n\nPárrafo.')
        finally:
            context.close()


if __name__ == '__main__':
    unittest.main()
