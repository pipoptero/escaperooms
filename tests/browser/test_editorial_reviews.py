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

    def test_la_vitrina_official_video_uses_portrait_player(self):
        for width in (390, 1280):
            with self.subTest(width=width):
                context = self.browser.new_context(viewport={'width': width, 'height': 844}, service_workers='block')
                context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname == '127.0.0.1' else route.abort())
                page = context.new_page()
                try:
                    page.goto(self.url + '/', wait_until='domcontentloaded')
                    page.evaluate('loadOfficialVideos()')
                    page.evaluate("""() => {
                      const room = {id:'la-vitrina', nombre:'La Vitrina',
                        imagen:'images/catalgo_propio_web_escape/optimized/la-vitrina.jpg'};
                      document.getElementById('detail-content').innerHTML = officialVideoHtml(room);
                      document.getElementById('detail-modal').classList.add('open');
                    }""")
                    card = page.locator('.detail-video-card--portrait')
                    self.assertEqual(card.count(), 1)
                    box = card.bounding_box()
                    self.assertLessEqual(box['width'], 340)
                    self.assertAlmostEqual(box['height'] / box['width'], 16 / 9, delta=.02)
                    self.assertEqual(page.locator('.detail-video-frame').count(), 0)
                    page.locator('.detail-video-preview').click()
                    src = page.locator('.detail-video-frame').get_attribute('src')
                    self.assertIn('player.vimeo.com/video/1167130701', src)
                    self.assertIn('autoplay=1', src)
                finally:
                    context.close()

    def test_review_listing_preview_is_compact_safe_and_opens_full_detail(self):
        for width in (1440, 768, 390):
            with self.subTest(width=width):
                context = self.browser.new_context(viewport={'width': width, 'height': 900}, service_workers='block')
                context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname == '127.0.0.1' else route.abort())
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                try:
                    page.goto(self.url + '/', wait_until='domcontentloaded')
                    page.wait_for_function("reviewRooms().some(room => room.id === 'la-vitrina')", timeout=30000)
                    result = page.evaluate("""() => {
                      switchTab('hechos');
                      const room = reviewRooms().find(item => item.id === 'la-vitrina');
                      document.getElementById('grid-hechos').innerHTML = cardHecho(room, 1);
                      const row = document.querySelector('#grid-hechos .review-row');
                      const text = row.querySelector('.rv-opinion-text');
                      return {originalLength: room.descripcion.length, previewLength: text.textContent.length,
                        excerptLength: Array.from(TheVaultEditorialReview.excerptEditorialReview(editorialTextForDisplay(room), 600).text).length,
                        paragraphs: text.querySelectorAll('p').length,
                        headings: text.querySelectorAll('h3,h4').length,
                        buttonCount: row.querySelectorAll('.rv-read-full').length,
                        height: row.getBoundingClientRect().height,
                        overflow: document.documentElement.scrollWidth - innerWidth};
                    }""")
                    self.assertGreater(result['originalLength'], 9000)
                    self.assertLessEqual(result['excerptLength'], 600)
                    self.assertLessEqual(result['previewLength'], 650)
                    self.assertGreater(result['paragraphs'], 1)
                    self.assertGreater(result['headings'], 0)
                    self.assertEqual(result['buttonCount'], 1)
                    self.assertLess(result['height'], 1500)
                    self.assertLessEqual(result['overflow'], 1)
                    page.locator('#grid-hechos .rv-read-full').click()
                    self.assertTrue(page.locator('#detail-modal').evaluate("el => el.classList.contains('open')"))
                    self.assertGreater(page.locator('#detail-content .detail-review-text').inner_text().__len__(), 9000)
                    self.assertEqual(errors, [])
                finally:
                    context.close()

    def test_short_arkkadia_and_malicious_review_cards(self):
        context = self.browser.new_context(service_workers='block')
        context.route('**/*', lambda route: route.continue_() if urlparse(route.request.url).hostname == '127.0.0.1' else route.abort())
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(self.url + '/', wait_until='domcontentloaded')
            result = page.evaluate("""() => {
              const room = {id:'fixture-review',nombre:'Fixture',empresa:'Fixture',
                descripcion:'## OPINIÓN\\n\\n**Buena** 🔐\\n\\n- Uno\\n- Dos',
                _arkkadiaCommunityReview:true,_reviewAuthorName:'Autor'};
              const unsafe = {...room, descripcion:'<img src=x onerror="window.reviewPwned=1">'};
              const host = document.createElement('div'); document.body.appendChild(host);
              host.innerHTML = cardHecho(room, 1) + cardHecho(unsafe, 2);
              const [short, attack] = host.querySelectorAll('.review-row');
              const result = {
                label:short.querySelector('.rv-opinion-label').textContent,
                heading:short.querySelectorAll('.rv-opinion-text h4').length,
                bold:short.querySelectorAll('.rv-opinion-text strong').length,
                lists:short.querySelectorAll('.rv-opinion-text li').length,
                emoji:short.querySelector('.rv-opinion-text').textContent.includes('🔐'),
                shortButton:short.querySelectorAll('.rv-read-full').length,
                injectedImage:attack.querySelectorAll('.rv-opinion-text img').length,
                escaped:attack.querySelector('.rv-opinion-text').textContent.includes('<img'),
                pwned:!!window.reviewPwned
              };
              host.remove(); return result;
            }""")
            self.assertIn('Arkkadia', result['label'])
            self.assertEqual(result['heading'], 1)
            self.assertEqual(result['bold'], 1)
            self.assertEqual(result['lists'], 2)
            self.assertTrue(result['emoji'])
            self.assertEqual(result['shortButton'], 0)
            self.assertEqual(result['injectedImage'], 0)
            self.assertTrue(result['escaped'])
            self.assertFalse(result['pwned'])
            self.assertEqual(errors, [])
        finally:
            context.close()


if __name__ == '__main__':
    unittest.main()
