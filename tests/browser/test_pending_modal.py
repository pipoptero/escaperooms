"""Local browser regressions. All external traffic is blocked; Firebase is simulated.

Run: python -B -m unittest discover -s tests/browser -v
Set VAULT_TEST_BROWSER=webkit for the second engine.
Requires: pip install playwright; python -m playwright install chromium webkit
"""
import copy
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass  # Closing a test page cancels its in-flight image requests.


class PendingModalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        cls.browser_name = os.getenv('VAULT_TEST_BROWSER', 'chromium')
        cls.browser = getattr(cls.playwright, cls.browser_name).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.db = {
            'users': {'a': {'roomStates': {
                'parasomnia_bajo_segunda': {'nombre': 'Parasomnia Bajo Segunda', 'pending': True, 'done': False, 'updatedAt': 100},
                'parasomnia_bajo_2': {'nombre': 'Parasomnia Bajo 2ª', 'done': True, 'pending': False, 'updatedAt': 200}
            }}, 'b': {'roomStates': {}}},
            'userGroups': {uid: {'g1': {'name': 'Grupo Uno'}, 'g2': {'name': 'Grupo Dos'}} for uid in ['a', 'b']},
            'groupMembers': {gid: {uid: {'role': 'member', 'status': 'active'} for uid in ['a', 'b']} for gid in ['g1', 'g2']},
            'groupRooms': {}, 'groupPendingRooms': {}
        }
        self.patches = []
        self.puts = []
        self.deletes = []
        self.deny = False
        self.deny_group_membership_patch = False
        self.legacy_group_index_rules = False
        self.deny_put_prefixes = set()
        self.fail_patch_once = False
        self.fail_delete_once_prefixes = set()
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, service_workers='block')
        self.context.route('**/*', self.route)

    def tearDown(self):
        self.context.close()

    def route(self, route):
        request = route.request
        url = urlparse(request.url)
        if url.hostname == 'test.invalid':
            path = url.path.removesuffix('.json').strip('/')
            if request.method == 'PATCH':
                patch = json.loads(request.post_data)
                foreign_group_index = any(key.startswith('userGroups/') and not key.startswith('userGroups/a/') for key in patch)
                group_membership = any(key.startswith('groupMembers/') for key in patch)
                if self.deny or (self.legacy_group_index_rules and foreign_group_index) or (self.deny_group_membership_patch and group_membership):
                    return route.fulfill(status=403, content_type='application/json', body='{"error":"Permission denied"}', headers={'Access-Control-Allow-Origin': '*'})
                if self.fail_patch_once:
                    self.fail_patch_once = False
                    return route.fulfill(status=503, content_type='application/json', body='{"error":"Temporary failure"}', headers={'Access-Control-Allow-Origin': '*'})
                self.patches.append(patch)
                for key, value in patch.items():
                    parts = key.split('/')
                    node = self.db
                    for part in parts[:-1]:
                        node = node.setdefault(part, {})
                    if value is None:
                        node.pop(parts[-1], None)
                    else:
                        node[parts[-1]] = value
                value = patch
            elif request.method == 'PUT':
                value = json.loads(request.post_data)
                if self.deny or (self.deny_group_membership_patch and path.startswith('groupMembers/')) or any(path.startswith(prefix) for prefix in self.deny_put_prefixes):
                    return route.fulfill(status=403, content_type='application/json', body='{"error":"Permission denied"}', headers={'Access-Control-Allow-Origin': '*'})
                self.puts.append((path, value))
                parts = list(filter(None, path.split('/')))
                node = self.db
                for part in parts[:-1]:
                    node = node.setdefault(part, {})
                node[parts[-1]] = value
            elif request.method == 'DELETE':
                failed_prefix = next((prefix for prefix in self.fail_delete_once_prefixes if path.startswith(prefix)), None)
                if failed_prefix:
                    self.fail_delete_once_prefixes.remove(failed_prefix)
                    return route.fulfill(status=503, content_type='application/json', body='{"error":"Temporary failure"}', headers={'Access-Control-Allow-Origin': '*'})
                self.deletes.append(path)
                parts = list(filter(None, path.split('/')))
                node = self.db
                for part in parts[:-1]:
                    node = node.setdefault(part, {})
                node.pop(parts[-1], None)
                value = None
            elif request.method == 'GET':
                value = self.db
                for part in filter(None, path.split('/')):
                    value = value.get(part, {})
            else:
                value = {}
            return route.fulfill(content_type='application/json', body=json.dumps(value), headers={
                'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,PUT,PATCH,DELETE,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type'
            })
        if url.path == '/firebase-config.js':
            return route.fulfill(content_type='application/javascript', body="window.THE_VAULT_FIREBASE_CONFIG={databaseURL:'https://test.invalid',apiKey:'',authDomain:'',projectId:'',appId:''};")
        if url.hostname == '127.0.0.1':
            return route.continue_()
        route.abort()

    def page_for(self, uid='a'):
        page = self.context.new_page()
        page.goto(self.url, wait_until='load')
        page.evaluate("""async uid => {
            loadLiveDataAfterInitialRender = async () => {};
            AUTH_USER = {uid}; USER_ID = uid; USER_PROFILE = {};
            CATALOGO = (await (await fetch('catalog.json')).json()).catalogo;
            CATALOG_LOADED = true;
            await ensureStaticEnhancementsLoaded();
            await loadRoomAliases(); await loadUserRoomStates(true); await loadUserGroups(true);
            renderAuthStatus(); switchTab('catalogo');
        }""", uid)
        return page

    def visible_input_point(self, page, box):
        # The Windows WebKit port can expose CSS pixels at the OS display scale.
        # Native input uses the configured viewport coordinate space.
        if self.browser_name != 'webkit':
            return (box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        dimensions = page.evaluate('({width:innerWidth,height:innerHeight})')
        viewport = page.viewport_size
        return ((box['x'] + box['width'] / 2) * viewport['width'] / dimensions['width'],
                (box['y'] + box['height'] / 2) * viewport['height'] / dimensions['height'])

    def test_group_choice_shared_with_second_member_and_personal_scope_separate(self):
        first, second = self.page_for(), self.page_for('b')
        first.locator('#tab-cat').click()
        first.locator('#mobile-filter-toggle-cat').click()
        expect(first.locator('#search-cat')).to_be_visible()
        first.locator('#search-cat').fill('Olimpo')
        first.locator('#grid-catalogo').get_by_role('button', name='Pendiente…', exact=True).click()
        first.locator('.pending-destination', has_text='Grupo Dos').click()
        first.wait_for_function("!document.getElementById('pending-choice').open")
        self.assertIn('olimpo', self.db['groupPendingRooms']['g2'])
        self.assertNotIn('olimpo', self.db['users']['a']['roomStates'])
        self.assertNotIn('g1', self.db['groupPendingRooms'])
        second.evaluate("async () => { switchTab('pendientes'); await refreshRoomLists(); }")
        self.assertTrue(second.evaluate("personalPendingRooms().some(r => r.id === 'olimpo')"))
        self.assertEqual(second.evaluate("groupPendingEntriesForRoom(CATALOGO.find(r => r.id === 'olimpo'))[0].name"), 'Grupo Dos')
        first.evaluate("openPendingChoice('catalogo','katrina')")
        first.locator('.pending-destination', has_text='Solo para mí').click()
        first.wait_for_function("!document.getElementById('pending-choice').open")
        second.evaluate("refreshRoomLists()")
        self.assertFalse(second.evaluate("personalPendingRooms().some(r => r.id === 'katrina')"))

    def test_legacy_case_and_failed_write_do_not_mutate_local_state(self):
        page = self.page_for()
        self.assertFalse(page.evaluate("personalPendingRooms().some(r => /Parasomnia/.test(r.nombre))"))
        self.assertEqual(page.evaluate("progressPersonalDoneRooms().filter(r => /Parasomnia/.test(r.nombre)).length"), 1)
        before = copy.deepcopy(self.db)
        self.deny = True
        page.evaluate("openPendingChoice('catalogo','olimpo')")
        page.locator('.pending-destination', has_text='Grupo Uno').click()
        page.wait_for_function("document.getElementById('pending-choice-error').textContent.length > 0")
        self.assertEqual(self.db, before)
        self.assertFalse(page.evaluate("!!GROUP_PENDING_ROOMS.g1?.olimpo"))
        self.assertTrue(page.locator('#pending-choice').evaluate('(el) => el.open'))

    def test_group_completion_cleans_aliases_atomically_and_keeps_other_group(self):
        self.db['groupPendingRooms'] = {
            'g1': {'parasomnia_bajo_segunda': {'roomName': 'Parasomnia Bajo Segunda'}},
            'g2': {'parasomnia_bajo_segunda': {'roomName': 'Parasomnia Bajo Segunda'}}
        }
        page = self.page_for()
        page.evaluate("markGroupPendingAsDone('g1','bajo_segunda')")
        self.assertIn('bajo_segunda', self.db['groupRooms']['g1'])
        self.assertEqual(self.db['groupPendingRooms']['g1'], {})
        self.assertIn('parasomnia_bajo_segunda', self.db['groupPendingRooms']['g2'])
        self.assertEqual(len(self.patches), 1)

    def test_personal_edit_consolidates_legacy_keys_without_touching_another_user(self):
        page = self.page_for()
        other = copy.deepcopy(self.db['users']['b'])
        page.evaluate("saveUserRoomState(CATALOGO.find(r => r.id === 'bajo-segunda'), {done: true, pending: false, completedMinutes: 75})")
        records = self.db['users']['a']['roomStates']
        self.assertEqual(list(records), ['bajo_segunda'])
        self.assertEqual(records['bajo_segunda']['completedMinutes'], 75)
        self.assertEqual(self.db['users']['b'], other)
        self.assertEqual(len(self.patches), 1)

    def test_stale_pending_removal_preserves_a_group_completion_from_another_member(self):
        self.db['groupPendingRooms'] = {'g1': {'olimpo': {'roomName': 'Olimpo'}}}
        page = self.page_for()
        # Another member completes the room after this page has loaded its pending list.
        self.db['groupRooms'] = {'g1': {'olimpo': {'roomName': 'Olimpo', 'updatedAt': 999}}}
        self.db['groupPendingRooms']['g1'] = {}
        page.evaluate("applyPendingChoice('catalogo','olimpo','g1')")
        self.assertEqual(self.db['groupRooms']['g1']['olimpo']['updatedAt'], 999)
        self.assertEqual(self.db['groupPendingRooms']['g1'], {})

    def test_accepting_invite_updates_member_index_and_token_atomically(self):
        self.db['groups'] = {'g3': {'name': 'Grupo Tres', 'ownerUid': 'owner'}}
        self.db['groupMembers']['g3'] = {'owner': {'role': 'owner', 'status': 'active'}}
        self.db['groupInvites'] = {'token': {
            'groupId': 'g3', 'groupName': 'Grupo Tres', 'createdBy': 'owner',
            'status': 'pending', 'expiresAt': 9_999_999_999_999
        }}
        page = self.page_for()
        page.evaluate("acceptGroupInvite('token')")
        page.wait_for_function("GROUP_MEMBERS.g3?.a?.status === 'active'")
        self.assertEqual(self.db['groupMembers']['g3']['a']['role'], 'member')
        self.assertEqual(self.db['groupMembers']['g3']['a']['inviteId'], 'token')
        self.assertEqual(self.db['userGroups']['a']['g3']['status'], 'active')
        self.assertEqual(self.db['groupInvites']['token']['status'], 'accepted')
        self.assertEqual(len(self.patches), 1)

    def test_creating_group_prepares_owner_and_index_before_metadata(self):
        page = self.page_for()
        page.evaluate("SETTINGS_TAB = 'profile'; openProfile('', false)")
        page.locator('#new-group-name').fill('Grupo Seguro')
        page.evaluate("createEscapistGroup()")
        page.wait_for_function("Object.values(USER_GROUPS).some(group => group.name === 'Grupo Seguro')")
        group_id = next(key for key, value in self.db['groups'].items() if value['name'] == 'Grupo Seguro')
        self.assertEqual(self.db['groupMembers'][group_id]['a']['role'], 'owner')
        self.assertEqual(self.db['userGroups']['a'][group_id]['role'], 'owner')
        creation_paths = [path for path, _ in self.puts if group_id in path]
        self.assertEqual(creation_paths, [
            f'groupMembers/{group_id}/a', f'userGroups/a/{group_id}', f'groups/{group_id}'
        ])

    def test_failed_group_creation_leaves_no_incomplete_nodes(self):
        self.deny_group_membership_patch = True
        page = self.page_for()
        page.evaluate("SETTINGS_TAB = 'profile'; openProfile('', false)")
        page.locator('#new-group-name').fill('Grupo Fallido')
        page.evaluate("createEscapistGroup()")
        page.wait_for_function("document.getElementById('profile-status')?.textContent.includes('No se pudo crear')")
        self.assertIn('Recarga la aplicación', page.locator('#profile-status').text_content())
        self.assertFalse(any(value.get('name') == 'Grupo Fallido' for value in self.db.get('groups', {}).values()))
        self.assertFalse(any('Grupo Fallido' in json.dumps(patch) for patch in self.patches))

    def test_group_creation_cleans_failures_after_each_preparatory_step(self):
        page = self.page_for()
        page.evaluate("SETTINGS_TAB = 'profile'; openProfile('', false)")
        for denied_prefix, name in [('userGroups/', 'Fallo Indice'), ('groups/', 'Fallo Metadata')]:
            put_count = len(self.puts)
            self.deny_put_prefixes = {denied_prefix}
            if denied_prefix == 'groups/':
                self.fail_delete_once_prefixes = {'userGroups/'}
            page.locator('#new-group-name').fill(name)
            page.evaluate("createEscapistGroup()")
            page.wait_for_function("name => document.getElementById('profile-status')?.textContent.includes('No se pudo crear') && !Object.values(USER_GROUPS).some(group => group.name === name)", arg=name)
            self.deny_put_prefixes.clear()
            new_paths = [path for path, _ in self.puts[put_count:] if path.startswith('groupMembers/')]
            self.assertEqual(len(new_paths), 1)
            group_id = new_paths[0].split('/')[1]
            self.assertFalse(any(value.get('name') == name for value in self.db.get('groups', {}).values()))
            self.assertFalse(self.db.get('groupMembers', {}).get(group_id))
            self.assertNotIn(group_id, self.db.get('userGroups', {}).get('a', {}))

    def test_deleting_group_removes_metadata_before_auxiliary_data(self):
        self.db['groups'] = {'owned': {'name': 'Propio', 'ownerUid': 'a'}}
        self.db['userGroups']['a']['owned'] = {'name': 'Propio', 'role': 'owner', 'status': 'active'}
        self.db['userGroups']['b']['owned'] = {'name': 'Propio', 'role': 'member', 'status': 'active'}
        self.db['groupMembers']['owned'] = {
            'a': {'role': 'owner', 'status': 'active'},
            'b': {'role': 'member', 'status': 'active'}
        }
        self.db['groupRooms']['owned'] = {'olimpo': {'roomName': 'Olimpo'}}
        self.db['groupPendingRooms']['owned'] = {'katrina': {'roomName': 'Katrina'}}
        page = self.page_for()
        self.fail_patch_once = True
        page.on('dialog', lambda dialog: dialog.accept())
        page.evaluate("deleteEscapistGroup('owned')")
        page.wait_for_function("!USER_GROUPS.owned")
        self.assertNotIn('owned', self.db['groups'])
        self.assertFalse(self.db['groupMembers'].get('owned'))
        self.assertFalse(self.db['groupRooms'].get('owned'))
        self.assertFalse(self.db['groupPendingRooms'].get('owned'))
        self.assertNotIn('owned', self.db['userGroups']['a'])
        self.assertNotIn('owned', self.db['userGroups']['b'])
        self.assertIn('groups/owned', self.deletes)
        self.assertEqual(len(self.patches), 1)

    def test_group_deletion_falls_back_safely_with_current_production_rules(self):
        self.legacy_group_index_rules = True
        self.db['groups'] = {'owned': {'name': 'Propio', 'ownerUid': 'a'}}
        self.db['userGroups']['a']['owned'] = {'name': 'Propio', 'role': 'owner', 'status': 'active'}
        self.db['userGroups']['b']['owned'] = {'name': 'Propio', 'role': 'member', 'status': 'active'}
        self.db['groupMembers']['owned'] = {
            'a': {'role': 'owner', 'status': 'active'},
            'b': {'role': 'member', 'status': 'active'}
        }
        page = self.page_for()
        page.on('dialog', lambda dialog: dialog.accept())
        page.evaluate("deleteEscapistGroup('owned')")
        page.wait_for_function("!USER_GROUPS.owned")
        self.assertNotIn('owned', self.db['groups'])
        self.assertFalse(self.db['groupMembers'].get('owned'))
        self.assertNotIn('owned', self.db['userGroups']['a'])
        self.assertIn('owned', self.db['userGroups']['b'])
        self.assertIn('groups/owned', self.deletes)
        self.assertEqual(len(self.patches), 1)

    def test_desktop_close_works_with_mouse_and_focus_returns(self):
        self.context.close()
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 800}, service_workers='block')
        self.context.route('**/*', self.route)
        page = self.page_for()
        page.locator('#search-cat').focus()
        page.evaluate("openDetail('catalogo','olimpo')")
        page.evaluate("() => {const x=document.querySelector('.detail-content');x.insertAdjacentHTML('beforeend','<p>Texto</p>'.repeat(300));x.scrollTop=x.scrollHeight;}")
        button = page.locator('.detail-close')
        self.assertTrue(button.evaluate('(el) => {const r=el.getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===el;}'))
        box = button.bounding_box()
        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        expect(page.locator('#detail-modal')).to_have_attribute('aria-hidden', 'true')
        self.assertTrue(page.locator('#search-cat').evaluate('(el) => document.activeElement === el'))

    def test_close_remains_clickable_after_scroll_resize_and_reopen(self):
        page = self.page_for()
        for width, height in [(390, 844), (844, 390), (390, 430), (1280, 800)]:
            with self.subTest(viewport=f'{width}x{height}'):
                page.set_viewport_size({'width': width, 'height': height})
                page.evaluate("openDetail('catalogo','olimpo')")
                scroll_top = page.evaluate("""() => {
                    document.getElementById('detail-content').insertAdjacentHTML('beforeend', '<p>Texto largo</p>'.repeat(300));
                    const containers = [document.querySelector('.detail-dialog'), document.querySelector('.detail-content')];
                    const scroll = containers.find(el => el.scrollHeight > el.clientHeight + 1);
                    if (!scroll) return 0;
                    scroll.scrollTop = scroll.scrollHeight;
                    return scroll.scrollTop;
                }""")
                self.assertGreater(scroll_top, 0)
                button = page.locator('.detail-close')
                self.assertTrue(button.is_visible())
                box = button.bounding_box()
                self.assertGreaterEqual(box['x'], 0)
                self.assertGreaterEqual(box['y'], 0)
                self.assertLessEqual(box['y'] + box['height'], height + 1)
                hit = button.evaluate('(el) => {const r=el.getBoundingClientRect(); return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2) === el;}')
                self.assertTrue(hit, f'Close obscured at {width}x{height}')
                # Use a real touch at the visible viewport position in mobile emulation.
                # Assert hit testing first; do not force a click through an overlay.
                page.touchscreen.tap(*self.visible_input_point(page, box))
                expect(page.locator('#detail-modal')).to_have_attribute('aria-hidden', 'true')
        page.set_viewport_size({'width': 390, 'height': 844})
        page.evaluate("openDetail('catalogo','katrina')")
        self.assertEqual(page.locator('.detail-dialog').evaluate('(el) => el.scrollTop'), 0)
        page.evaluate("openPendingChoice('catalogo','olimpo')")
        page.keyboard.press('Escape')
        expect(page.locator('#detail-modal')).to_have_attribute('aria-hidden', 'false')
        page.keyboard.press('Escape')
        expect(page.locator('#detail-modal')).to_have_attribute('aria-hidden', 'true')


if __name__ == '__main__':
    unittest.main()
