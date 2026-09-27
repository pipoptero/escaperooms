"""Home map regressions with fixture states and Leaflet, without external traffic."""
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass


class HomeMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.getenv('VAULT_TEST_BROWSER', 'chromium')).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        self.context.route('**/*', self.route)
        self.page = self.context.new_page()
        self.page.goto(self.url, wait_until='load')
        expect(self.page.locator('#app')).to_be_visible()
        self.page.evaluate("""() => {
          loadLiveDataAfterInitialRender = async () => {};
          AUTH_USER = {uid:'home-map-fixture'}; USER_ID = AUTH_USER.uid; USER_PROFILE = {};
          CATALOGO = [
            {id:'map-personal',nombre:'Personal fixture',empresa:'Fixture A',ciudad:'Madrid'},
            {id:'map-shared',nombre:'Shared fixture',empresa:'Fixture B',ciudad:'Barcelona'},
            {id:'map-pending',nombre:'Pending fixture',empresa:'Fixture C',ciudad:'Valencia'}
          ];
          CATALOG_LOADED = true;
          USER_ROOM_STATES = {map_personal:{done:true},map_pending:{pending:true}};
          USER_GROUPS = {fixture_group:{name:'Fixture group',status:'active'}};
          GROUP_ROOMS = {fixture_group:{map_shared:{roomName:'Shared fixture',city:'Barcelona'}}};
          GROUP_PENDING_ROOMS = {fixture_group:{map_pending:{roomName:'Pending fixture'}}};
          ROOM_LOCATIONS = {
            'map-personal':{lat:40.42,lon:-3.70,confidence:99},
            'map-shared':{lat:41.39,lon:2.17,confidence:99},
            'map-pending':{lat:39.47,lon:-0.38,confidence:99}
          };
          PENDIENTES = []; HECHOS = [];
          window.__mapDataCalls = 0; window.__leafletCalls = 0; window.__maps = [];
          ensureProfileMapDataLoaded = async () => { window.__mapDataCalls++; return true; };
          ensureLeafletAssets = async () => { window.__leafletCalls++; return true; };
          window.L = {
            map(node) {
              const map = {node,removed:false,remove(){this.removed=true;this.node.innerHTML='';},
                fitBounds(){},setView(){},invalidateSize(){}};
              window.__maps.push(map); return map;
            },
            tileLayer:()=>({addTo:()=>{}}), divIcon:options=>options,
            marker:(coords,options)=>({addTo(map){
              const marker=document.createElement('div'); marker.innerHTML=options.icon.html;
              map.node.appendChild(marker); this.marker=marker; return this;
            },on(event,callback){this.marker.addEventListener(event,callback);return this;}})
          };
          window.__realProgressModel = progressModel;
          progressModel = () => ({doneRooms:CATALOGO.slice(0,2),personalDoneRooms:CATALOGO.slice(0,2)});
          vaultHomeIdentityHtml = () => '';
          vaultHomeProgressHtml = () => '';
          vaultHomeActivityHtml = () => '';
          vaultHomeDiscoveryHtml = () => '';
          vaultGuestOverviewHtml = () => '<p>Guest fixture</p>';
          document.getElementById('panel-thevault').style.display='block';
          ACTIVE_TAB = 'thevault';
        }""")

    def tearDown(self):
        self.context.close()

    def route(self, route):
        url = urlparse(route.request.url)
        if url.path == '/firebase-config.js':
            return route.fulfill(content_type='application/javascript', body='window.THE_VAULT_FIREBASE_CONFIG={};')
        if url.hostname == '127.0.0.1':
            return route.continue_()
        route.abort()

    def render(self):
        self.page.evaluate('renderVaultGuide()')

    def show_map(self):
        self.page.locator('.vault-home-map-canvas').scroll_into_view_if_needed()
        expect(self.page.locator('#vault-home-leaflet-map')).to_have_attribute('data-map-state', 'ready')

    def test_visible_map_restores_only_personal_done_markers(self):
        for width in (375, 390, 430, 768, 1365):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 844})
                self.render()
                self.show_map()
                expect(self.page.locator('#vault-home-leaflet-map')).to_be_visible()
                expect(self.page.locator('#vault-home-leaflet-map .personal')).to_have_count(1)
                expect(self.page.locator('#vault-home-leaflet-map .group')).to_have_count(0)
                expect(self.page.locator('#vault-home-leaflet-map .pending')).to_have_count(0)
                expect(self.page.locator('#vault-home-map-coverage')).to_contain_text('Ubicación fiable: 1 de 1')
                expect(self.page.locator('.vault-home-map-placeholder')).to_be_hidden()
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
        self.assertTrue(self.page.evaluate('__maps[0].removed'))

    def test_sanitized_63_59_fixture_keeps_personal_count_after_catalog_load(self):
        counts = self.page.evaluate("""() => {
          progressModel = window.__realProgressModel;
          REVIEW_ROOM_ALIASES = {legacy_fixture_0:'fixture_room_0',legacy_fixture_1:'fixture_room_1'};
          const raw = {};
          for (let i=0;i<63;i++) raw[i<2 ? `legacy_fixture_${i}` : `fixture_room_${i}`] =
            {done:true,nombre:`Fixture room ${i}`,empresa:'Sanitized test'};
          USER_ROOM_STATES = VaultRoomState.normalize(raw,REVIEW_ROOM_ALIASES,true).data;
          USER_GROUPS = {fixture_group:{name:'Group',status:'active'}};
          GROUP_ROOMS = {fixture_group:{group_only:{roomName:'Group only'}}};
          GROUP_PENDING_ROOMS = {fixture_group:{pending_only:{roomName:'Pending only'}}};
          CATALOGO=[];
          const before={ids:personalDoneRoomIds().length,progress:progressModel().personalDoneRooms.length};
          CATALOGO=Array.from({length:61},(_,i)=>({id:`fixture-room-${i}`,nombre:`Fixture room ${i}`,
            empresa:'Sanitized test',ciudad:'Madrid'}));
          ROOM_LOCATIONS=Object.fromEntries(Array.from({length:59},(_,i)=>
            [`fixture-room-${i}`,{lat:40+i/1000,lon:-3.7,confidence:99,precision:'nominatim'}]));
          const after={ids:personalDoneRoomIds().length,progress:progressModel().personalDoneRooms.length,
            sharedProgress:progressModel().doneRooms.length,
            visual:personalDoneRooms().length,mapped:personalHomeMapLocations().reduce((n,l)=>n+l.rooms.length,0)};
          renderStats(); renderVaultGuide();
          return {before,after,stats:document.querySelector('#stats-bar .stat-num')?.textContent,
            home:document.querySelector('.vault-home-map-stat strong')?.textContent};
        }""")
        self.assertEqual(counts['before'], {'ids': 63, 'progress': 63})
        self.assertEqual(counts['after'], {'ids': 63, 'progress': 63, 'sharedProgress': 64,
                                          'visual': 64, 'mapped': 59})
        self.assertEqual(counts['stats'], '63')
        self.assertEqual(counts['home'], '63')
        self.show_map()
        expect(self.page.locator('#vault-home-leaflet-map .personal')).to_have_count(59)
        expect(self.page.locator('#vault-home-map-coverage')).to_contain_text('Ubicación fiable: 59 de 63')
        self.page.evaluate("""() => {
          HECHOS=[{id:'fixture-room-0',nombre:'Fixture room 0',empresa:'Sanitized test',valoracion:9}];
          renderHechos(); renderRanking(); renderStats(); renderVaultGuide();
        }""")
        self.assertEqual(self.page.evaluate('personalDoneRoomIds().length'), 63)
        self.assertEqual(self.page.locator('#stats-bar .stat-num').first.inner_text(), '63')
        self.assertEqual(self.page.locator('.vault-home-map-stat strong').first.inner_text(), '63')

    def test_four_historical_collision_classes_keep_distinct_personal_states(self):
        result = self.page.evaluate("""() => {
          progressModel = window.__realProgressModel;
          USER_ROOM_STATES = {
            el_torneo_de_los_3_magos:{done:true,nombre:'Torneo fixture',empresa:'Madrid fixture'},
            the_haunted_prison_350741:{done:true,nombre:'Prison fixture',empresa:'Company A'},
            vinoteca:{done:true,nombre:'Vinoteca fixture',empresa:'Company B'},
            xperiment_insomnia_hotel:{done:true,id:'xperiment-insomnia-hotel',nombre:'Xperiment fixture',empresa:'Company C'}
          };
          CATALOGO = [
            {id:'el-torneo-de-los-3-magos-2-0',nombre:'Torneo fixture',empresa:'Valencia fixture'},
            {id:'el-torneo-de-los-3-magos',nombre:'Torneo fixture',empresa:'Madrid fixture'},
            {id:'the-haunted-prison-622551',nombre:'Prison fixture',empresa:'Company A'},
            {id:'the-haunted-prison-350741',nombre:'Prison fixture',empresa:'Company A'},
            {id:'vinoteca',nombre:'Vinoteca fixture',empresa:'Company B'},
            {id:'xperiment-insomnia-hotel',nombre:'Xperiment fixture',empresa:'Company C'}
          ];
          ROOM_LOCATIONS = {
            'el-torneo-de-los-3-magos':{lat:40.42,lon:-3.7,confidence:74},
            'the-haunted-prison-350741':{lat:40.43,lon:-3.7,confidence:61}
          };
          renderStats(); renderVaultGuide();
          return {keys:personalCompletedRooms().map(room=>room._personalStateKey),
            count:personalDoneRoomIds().length, mapped:personalHomeMapLocations().length,
            stats:document.querySelector('#stats-bar .stat-num')?.textContent,
            home:document.querySelector('.vault-home-map-stat strong')?.textContent};
        }""")
        self.assertCountEqual(result['keys'], [
            'el_torneo_de_los_3_magos', 'the_haunted_prison_350741',
            'vinoteca', 'xperiment_insomnia_hotel'])
        self.assertEqual(result['count'], 4)
        self.assertEqual(result['mapped'], 1)
        self.assertEqual(result['stats'], '4')
        self.assertEqual(result['home'], '4')

    def test_distinct_homonyms_survive_catalogue_and_true_alias_is_single(self):
        result = self.page.evaluate("""() => {
          REVIEW_ROOM_ALIASES={old_room:'canonical_room'};
          USER_ROOM_STATES=VaultRoomState.normalize({
            old_room:{done:true,nombre:'Alias room',updatedAt:1},
            canonical_room:{done:true,nombre:'Alias room',updatedAt:2},
            same_title_a:{done:true,nombre:'Same title',empresa:'Company A'},
            same_title_b:{done:true,nombre:'Same title',empresa:'Company B'}
          },REVIEW_ROOM_ALIASES,true).data;
          CATALOGO=[];
          const before=personalDoneRoomIds().length;
          CATALOGO=[
            {id:'same-title-a',nombre:'Same title',empresa:'Company A'},
            {id:'same-title-b',nombre:'Same title',empresa:'Company B'},
            {id:'canonical-room',nombre:'Alias room'}
          ];
          return {before,after:personalDoneRoomIds().length,
            keys:personalCompletedRooms().map(room=>room._personalStateKey)};
        }""")
        self.assertEqual(result['before'], 3)
        self.assertEqual(result['after'], 3)
        self.assertCountEqual(result['keys'], ['canonical_room', 'same_title_a', 'same_title_b'])

    def test_only_documented_id_alias_enriches_a_historical_state(self):
        result = self.page.evaluate("""() => {
          ROOM_EXPLICIT_ALIASES={legacy_fixture:'canonical_room'};
          REVIEW_ROOM_ALIASES={...ROOM_EXPLICIT_ALIASES};
          USER_ROOM_STATES={canonical_room:{done:true,nombre:'Historical name'}};
          CATALOGO=[{id:'legacy-fixture',nombre:'Current name',empresa:'Fixture'}];
          const documented=personalCompletedRooms()[0];
          ROOM_EXPLICIT_ALIASES={};
          const undocumented=personalCompletedRooms()[0];
          return {documented:documented.id,undocumented:undocumented.id,
            bothCount:personalDoneRoomIds().length};
        }""")
        self.assertEqual(result, {'documented': 'legacy-fixture', 'undocumented': 'canonical_room', 'bothCount': 1})

    def test_map_waits_for_viewport_and_authenticated_visible_panel(self):
        self.page.evaluate("vaultHomeIdentityHtml = () => '<div style=\"height:2600px\">Identity fixture</div>'")
        self.render()
        self.page.wait_for_timeout(150)
        self.assertEqual(self.page.evaluate('__mapDataCalls'), 0)
        self.show_map()
        self.assertEqual(self.page.evaluate('__mapDataCalls'), 1)
        self.page.evaluate("AUTH_USER=null; renderVaultGuide()")
        self.assertTrue(self.page.evaluate('__maps[0].removed'))
        expect(self.page.locator('#vault-home-leaflet-map')).to_have_count(0)
        self.page.evaluate("AUTH_USER={uid:'home-map-fixture'}; ACTIVE_TAB='catalogo'; renderVaultGuide()")
        self.page.wait_for_timeout(100)
        self.assertEqual(self.page.evaluate('__mapDataCalls'), 1)

    def test_obsolete_async_load_cannot_create_map_after_rerender_or_logout(self):
        self.page.evaluate("""() => {
          window.__mapResolves=[];
          ensureProfileMapDataLoaded=()=>new Promise(resolve=>__mapResolves.push(resolve));
        }""")
        self.render()
        self.page.locator('.vault-home-map-canvas').scroll_into_view_if_needed()
        self.page.wait_for_function('__mapResolves.length===1')
        self.render()
        self.page.wait_for_function('__mapResolves.length===2')
        self.page.evaluate('__mapResolves[0](true)')
        self.assertEqual(self.page.evaluate('__maps.length'), 0)
        self.page.evaluate('__mapResolves[1](true)')
        expect(self.page.locator('#vault-home-leaflet-map')).to_have_attribute('data-map-state', 'ready')
        self.assertEqual(self.page.evaluate('__maps.length'), 1)
        self.render()
        self.page.wait_for_function('__mapResolves.length===3')
        self.page.evaluate("AUTH_USER=null; renderVaultGuide(); __mapResolves[2](true)")
        self.assertEqual(self.page.evaluate('__maps.length'), 1)
        self.assertTrue(self.page.evaluate('__maps[0].removed'))

    def test_failed_assets_leave_clear_fallback_and_full_map_access(self):
        self.page.evaluate('ensureLeafletAssets=async()=>false')
        self.render()
        self.page.locator('.vault-home-map-canvas').scroll_into_view_if_needed()
        expect(self.page.locator('#vault-home-leaflet-map')).to_have_attribute('data-map-state', 'error')
        expect(self.page.locator('#vault-home-leaflet-map')).to_be_hidden()
        expect(self.page.locator('.vault-home-map-placeholder')).to_be_visible()
        expect(self.page.locator('.vault-home-map-placeholder')).to_contain_text('No hemos podido cargar el mapa')
        self.page.evaluate('openVaultHomeMap=()=>{window.__fullMapOpened=true;}')
        self.page.locator('.vault-home-map-placeholder button').click()
        self.assertTrue(self.page.evaluate('__fullMapOpened'))

    def test_no_reliable_coordinates_keeps_done_count_and_skips_leaflet(self):
        self.page.evaluate("ROOM_LOCATIONS={'map-personal':{lat:40.42,lon:-3.70,confidence:1}}")
        self.render()
        self.page.locator('.vault-home-map-canvas').scroll_into_view_if_needed()
        expect(self.page.locator('#vault-home-leaflet-map')).to_have_attribute('data-map-state', 'empty')
        self.assertEqual(self.page.evaluate('__leafletCalls'), 0)
        expect(self.page.locator('#vault-home-map-coverage')).to_contain_text('Ubicación fiable: 0 de 1')


if __name__ == '__main__':
    unittest.main()
