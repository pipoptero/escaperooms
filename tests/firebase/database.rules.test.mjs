import { after, before, beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { get, ref, remove, set, update } from 'firebase/database';

const PROJECT_ID = 'demo-the-vault';
let env;
const require = createRequire(import.meta.url);
const publicProfileClient = require('../../public-profile-firebase.js');

const group = (owner = 'owner') => ({ name: 'Equipo', ownerUid: owner, createdAt: 100, updatedAt: 100 });
const member = (role = 'member', extra = {}) => ({ role, status: 'active', displayName: role, photoURL: '', joinedAt: 100, ...extra });
const index = (role = 'member') => ({ name: 'Equipo', role, status: 'active', joinedAt: 100 });
const room = (uid) => ({ roomName: 'Bajo Segundo', addedBy: uid, addedAt: 100, updatedAt: 100 });
const invite = (overrides = {}) => ({
  groupId: 'g1', groupName: 'Equipo', createdBy: 'owner', createdByName: 'Owner',
  status: 'pending', createdAt: 100, expiresAt: Date.now() + 60_000, ...overrides
});
const savedRoute = (overrides = {}) => ({
  name: 'Vitoria 2027', description: '', scope: 'personal', ownerUid: 'alice', roomIds: ['room-a', 'room-b'],
  createdAt: 100, updatedAt: 100, status: 'active', schemaVersion: 1, ...overrides
});
const publicVisibility = (overrides = {}) => ({
  showAvatar: false, showProgress: false, showStats: false, showMap: false,
  showAchievements: false, showRoutes: false, showRoutesInProgress: false, showGroups: false,
  ...overrides
});
const publicControl = (overrides = {}) => ({
  schemaVersion: 1, published: false, indexable: false,
  currentUsername: '', pendingUsername: '', previousUsername: '',
  visibility: publicVisibility(), updatedAt: 100, ...overrides
});
const publicOwner = (uid = 'alice', overrides = {}) => ({
  ownerUid: uid, state: 'reserved', createdAt: 100, updatedAt: 100, ...overrides
});
const publicView = (username = 'isaac', overrides = {}) => ({
  schemaVersion: 1, published: true, indexable: false, username,
  displayName: 'Isaac', visibility: publicVisibility(), updatedAt: 100, ...overrides
});

async function seed(data) {
  await env.withSecurityRulesDisabled(async context => set(ref(context.database()), data));
}

function publicClientApi(database, anonymous, uid = 'alice') {
  let now = 100;
  return {
    now: () => ++now,
    get: async path => (await get(ref(database, path))).val(),
    put: async (path, value) => set(ref(database, path), value),
    remove: async path => remove(ref(database, path)),
    publicReadable: async username => {
      try { return (await get(ref(anonymous, `publicProfiles/${username}/view`))).exists(); }
      catch { return false; }
    },
    uid,
    tick: () => ++now
  };
}

before(async () => {
  env = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    database: { rules: await readFile(new URL('../../database.rules.json', import.meta.url), 'utf8') }
  });
});
beforeEach(async () => env.clearDatabase());
after(async () => env.cleanup());

test('cada usuario solo puede leer y modificar sus estados', async () => {
  const mine = env.authenticatedContext('alice').database();
  const other = env.authenticatedContext('bob').database();
  const state = { id: 'olimpo', nombre: 'Olimpo', pending: true, done: false, updatedAt: 100 };
  await assertSucceeds(set(ref(mine, 'users/alice/roomStates/olimpo'), state));
  await assertSucceeds(get(ref(mine, 'users/alice/roomStates')));
  await assertFails(get(ref(other, 'users/alice/roomStates')));
  await assertFails(set(ref(other, 'users/alice/roomStates/olimpo'), state));
  await assertFails(set(ref(mine, 'users/alice/roomStates/invalid'), { ...state, pending: true, done: true }));
  await assertSucceeds(set(ref(mine, 'users/alice/roomStates/dated'), { ...state, id: 'dated', pending: false, done: true, playedAt: '2024-05-17' }));
  await assertSucceeds(set(ref(mine, 'users/alice/roomStates/leap-date'), { ...state, id: 'leap-date', pending: false, done: true, playedAt: '2024-02-29' }));
  await assertSucceeds(set(ref(mine, 'users/alice/roomStates/legacy'), { ...state, id: 'legacy', pending: false, done: true }));
  await assertFails(set(ref(mine, 'users/alice/roomStates/bad-date'), { ...state, id: 'bad-date', pending: false, done: true, playedAt: '17/05/2024' }));
  await assertFails(set(ref(mine, 'users/alice/roomStates/impossible-date'), { ...state, id: 'impossible-date', pending: false, done: true, playedAt: '2024-02-31' }));
  await assertFails(set(ref(mine, 'users/alice/roomStates/non-leap-date'), { ...state, id: 'non-leap-date', pending: false, done: true, playedAt: '2023-02-29' }));
  await assertFails(set(ref(mine, 'users/alice/roomStates/unexpected-date-payload'), { ...state, id: 'unexpected-date-payload', pending: false, done: true, playedAt: { value: '2024-05-17' } }));
  await assertFails(set(ref(mine, 'users/alice/roomStates/pending-date'), { ...state, id: 'pending-date', playedAt: '2024-05-17' }));
});

test('el PATCH de alias personal sigue permitido y es atómico', async () => {
  await seed({ users: { alice: { roomStates: { old: { id: 'old', nombre: 'Sala', pending: true, done: false, updatedAt: 1 } } } } });
  const db = env.authenticatedContext('alice').database();
  await assertSucceeds(update(ref(db), {
    'users/alice/roomStates/old': null,
    'users/alice/roomStates/canonical': { id: 'canonical', nombre: 'Sala', pending: false, done: true, updatedAt: 2 }
  }));
});

test('el perfil completo, incluido el email, solo lo puede leer su propietario', async () => {
  await seed({ profiles: { alice: { uid: 'alice', publicName: 'Alice', email: 'private@example.test' } } });
  const alice = env.authenticatedContext('alice').database();
  const bob = env.authenticatedContext('bob').database();
  await assertSucceeds(get(ref(alice, 'profiles/alice')));
  await assertFails(get(ref(bob, 'profiles/alice')));
});

test('el propietario puede crear el grupo y registrar su pertenencia', async () => {
  const db = env.authenticatedContext('owner').database();
  await assertSucceeds(set(ref(db, 'groupMembers/g1/owner'), member('owner')));
  await assertSucceeds(set(ref(db, 'userGroups/owner/g1'), index('owner')));
  await assertSucceeds(set(ref(db, 'groups/g1'), group()));
  await assertSucceeds(get(ref(db, 'groups/g1')));
});

test('no se puede crear únicamente el nodo groups', async () => {
  const db = env.authenticatedContext('owner').database();
  await assertFails(set(ref(db, 'groups/g1'), group()));
});

test('un propietario coherente puede actualizar metadatos sin cambiar ownerUid', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner') } },
    userGroups: { owner: { g1: index('owner') } }
  });
  const db = env.authenticatedContext('owner').database();
  await assertSucceeds(set(ref(db, 'groups/g1'), { ...group(), name: 'Equipo actualizado', updatedAt: 200 }));
});

test('el propietario no puede degradarse ni borrar su pertenencia o índice', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner') } },
    userGroups: { owner: { g1: index('owner') } }
  });
  const db = env.authenticatedContext('owner').database();
  await assertFails(set(ref(db, 'groupMembers/g1/owner'), member('member')));
  await assertFails(remove(ref(db, 'groupMembers/g1/owner')));
  await assertFails(set(ref(db, 'userGroups/owner/g1'), index('member')));
  await assertFails(remove(ref(db, 'userGroups/owner/g1')));
});

test('ownerUid es inmutable aunque el destino sea un miembro activo', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } }
  });
  const db = env.authenticatedContext('owner').database();
  await assertFails(set(ref(db, 'groups/g1/ownerUid'), 'alice'));
  await assertFails(update(ref(db), { 'groups/g1/ownerUid': 'alice' }));
});

test('un miembro no puede cambiar ownerUid, proclamarse owner ni eliminar al propietario', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } }
  });
  const db = env.authenticatedContext('alice').database();
  await assertFails(set(ref(db, 'groups/g1/ownerUid'), 'alice'));
  await assertFails(set(ref(db, 'groupMembers/g1/alice'), member('owner')));
  await assertFails(set(ref(db, 'userGroups/alice/g1'), index('owner')));
  await assertFails(remove(ref(db, 'groupMembers/g1/owner')));
});

test('la transferencia de propiedad permanece deshabilitada aunque el PATCH sea coherente', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } }
  });
  const db = env.authenticatedContext('owner').database();
  await assertFails(update(ref(db), {
    'groups/g1/ownerUid': 'alice',
    'groupMembers/g1/owner/role': 'member',
    'userGroups/owner/g1/role': 'member',
    'groupMembers/g1/alice/role': 'owner',
    'userGroups/alice/g1/role': 'owner'
  }));
});

test('nadie puede autoañadirse ni ascender a propietario sin invitación', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner'), alice: member('member') } } });
  const attacker = env.authenticatedContext('attacker').database();
  const alice = env.authenticatedContext('alice').database();
  await assertFails(set(ref(attacker, 'groupMembers/g1/attacker'), member('member')));
  await assertFails(set(ref(attacker, 'groupMembers/g1/attacker'), member('owner')));
  await assertFails(set(ref(alice, 'groupMembers/g1/alice'), member('owner')));
});

test('un miembro conserva su rol al actualizar identidad y solo miembros crean invitaciones', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner'), alice: member('member') } } });
  const alice = env.authenticatedContext('alice').database();
  await assertSucceeds(set(ref(alice, 'groupMembers/g1/alice'), member('member', { displayName: 'Alice nueva', updatedAt: 200 })));
  await assertSucceeds(set(ref(alice, 'groupInvites/member-token'), invite({ createdBy: 'alice', createdByName: 'Alice' })));
  const outsider = env.authenticatedContext('outsider').database();
  await assertFails(set(ref(outsider, 'groupInvites/outsider-token'), invite({ createdBy: 'outsider', createdByName: 'Outsider' })));
});

test('una invitación válida añade al miembro en una única actualización y no se reutiliza', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner') } }, userGroups: { owner: { g1: index('owner') } }, groupInvites: { token: invite() } });
  const alice = env.authenticatedContext('alice').database();
  await assertSucceeds(get(ref(alice, 'groupInvites/token')));
  await assertSucceeds(update(ref(alice), {
    'groupMembers/g1/alice': member('member', { inviteId: 'token' }),
    'userGroups/alice/g1': index('member'),
    'groupInvites/token': invite({ status: 'accepted', acceptedBy: 'alice', acceptedByName: 'Alice', acceptedAt: 200 })
  }));
  const bob = env.authenticatedContext('bob').database();
  await assertFails(set(ref(bob, 'groupMembers/g1/bob'), member('member', { inviteId: 'token' })));
});

test('una invitación caducada no permite entrar', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner') } }, userGroups: { owner: { g1: index('owner') } }, groupInvites: { old: invite({ expiresAt: 1 }) } });
  const db = env.authenticatedContext('alice').database();
  await assertFails(set(ref(db, 'groupMembers/g1/alice'), member('member', { inviteId: 'old' })));
});

test('solo miembros activos modifican salas y el cambio hecho/pendiente puede ser atómico', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner'), alice: member('member') } }, groupPendingRooms: { g1: { bajo_segunda: room('alice') } } });
  const alice = env.authenticatedContext('alice').database();
  await assertSucceeds(update(ref(alice), {
    'groupPendingRooms/g1/bajo_segunda': null,
    'groupRooms/g1/bajo_segunda': { ...room('alice'), updatedAt: 200 }
  }));
  const outsider = env.authenticatedContext('outsider').database();
  await assertFails(set(ref(outsider, 'groupPendingRooms/g1/olimpo'), room('outsider')));
});

test('el propietario puede eliminar primero el grupo y después sus datos auxiliares', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } },
    groupRooms: { g1: { room: room('owner') } }, groupPendingRooms: { g1: { pending: room('owner') } }
  });
  const db = env.authenticatedContext('owner').database();
  await assertSucceeds(remove(ref(db, 'groups/g1')));
  await assertSucceeds(update(ref(db), {
    'groupMembers/g1/owner': null, 'groupMembers/g1/alice': null,
    'userGroups/owner/g1': null, 'userGroups/alice/g1': null,
    'groupRooms/g1/room': null, 'groupPendingRooms/g1/pending': null
  }));
  await env.withSecurityRulesDisabled(async context => {
    const value = (await get(ref(context.database()))).val() || {};
    if (value.groups?.g1 || value.groupMembers?.g1 || value.userGroups?.alice?.g1) throw new Error('El grupo no se eliminó completamente');
  });
});

test('un miembro no puede eliminar el grupo ni el índice de otra persona', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner'), alice: member('member') } }, userGroups: { owner: { g1: index('owner') } } });
  const db = env.authenticatedContext('alice').database();
  await assertFails(remove(ref(db, 'groups/g1')));
  await assertFails(remove(ref(db, 'userGroups/owner/g1')));
});

test('una ruta personal es privada y solo su propietario puede administrarla', async () => {
  const alice = env.authenticatedContext('alice').database();
  const bob = env.authenticatedContext('bob').database();
  await assertSucceeds(set(ref(alice, 'userRoutes/alice/r1'), savedRoute()));
  await assertSucceeds(get(ref(alice, 'userRoutes/alice')));
  await assertSucceeds(set(ref(alice, 'userRoutes/alice/r1/name'), 'Vitoria actualizada'));
  await assertFails(get(ref(bob, 'userRoutes/alice')));
  await assertFails(set(ref(bob, 'userRoutes/alice/r1'), savedRoute({ ownerUid: 'bob' })));
  await assertSucceeds(remove(ref(alice, 'userRoutes/alice/r1')));
});

test('las rutas personales validan ámbito, propietario e IDs de sala', async () => {
  const alice = env.authenticatedContext('alice').database();
  await assertFails(set(ref(alice, 'userRoutes/alice/bad-owner'), savedRoute({ ownerUid: 'bob' })));
  await assertFails(set(ref(alice, 'userRoutes/alice/bad-scope'), savedRoute({ scope: 'group', groupId: 'g1' })));
  await assertFails(set(ref(alice, 'userRoutes/alice/no-rooms'), savedRoute({ roomIds: [] })));
  await assertFails(set(ref(alice, 'userRoutes/alice/bad-room'), savedRoute({ roomIds: [42] })));
  await assertFails(set(ref(alice, 'userRoutes/alice/legacy-room'), savedRoute({ roomIds: ['Room Angie 2'] })));
  await assertFails(set(ref(alice, 'userRoutes/alice/too-many'), savedRoute({ roomIds: Array.from({ length: 21 }, (_, i) => `room-${i}`) })));
  await assertFails(set(ref(alice, 'userRoutes/alice/bad-time'), savedRoute({ createdAt: 200, updatedAt: 100 })));
  await assertFails(set(ref(alice, 'userRoutes/alice/bad-date'), savedRoute({ plannedDate: -1 })));
  await assertFails(set(ref(alice, 'userRoutes/alice/bad-official'), savedRoute({ officialRouteId: 'Movie Route' })));
  await assertFails(set(ref(alice, 'userRoutes/alice/extra'), savedRoute({ copiedCatalogPayload: { price: 20 } })));
  await assertFails(set(ref(alice, 'userRoutes/alice/progress'), savedRoute({ done: true, pending: false, percent: 100 })));
});

test('solo el propietario del grupo administra rutas grupales y los miembros las leen', async () => {
  await seed({
    groups: { g1: group() },
    groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } }
  });
  const owner = env.authenticatedContext('owner').database();
  const alice = env.authenticatedContext('alice').database();
  const outsider = env.authenticatedContext('outsider').database();
  const route = savedRoute({ scope: 'group', ownerUid: 'owner', groupId: 'g1' });
  await assertSucceeds(set(ref(owner, 'groupRoutes/g1/r1'), route));
  await assertSucceeds(get(ref(alice, 'groupRoutes/g1')));
  await assertFails(set(ref(alice, 'groupRoutes/g1/r1/name'), 'Cambio no autorizado'));
  await assertFails(get(ref(outsider, 'groupRoutes/g1')));
  await assertFails(set(ref(outsider, 'groupRoutes/g1/r2'), route));
  await assertSucceeds(remove(ref(owner, 'groupRoutes/g1/r1')));
});

test('una ruta grupal no puede apuntar a otro grupo o propietario', async () => {
  await seed({ groups: { g1: group() }, groupMembers: { g1: { owner: member('owner') } }, userGroups: { owner: { g1: index('owner') } } });
  const owner = env.authenticatedContext('owner').database();
  await assertFails(set(ref(owner, 'groupRoutes/g1/bad-group'), savedRoute({ scope: 'group', ownerUid: 'owner', groupId: 'g2' })));
  await assertFails(set(ref(owner, 'groupRoutes/g1/bad-owner'), savedRoute({ scope: 'group', ownerUid: 'alice', groupId: 'g1' })));
});

test('v46 no puede borrar un grupo con rutas y deja todos sus datos intactos', async () => {
  await seed({
    groups: { g1: group() }, groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } },
    groupRooms: { g1: { room: room('owner') } }, groupPendingRooms: { g1: { pending: room('alice') } },
    groupRoutes: { g1: { r1: savedRoute({ scope: 'group', ownerUid: 'owner', groupId: 'g1' }) } }
  });
  const owner = env.authenticatedContext('owner').database();
  await assertFails(remove(ref(owner, 'groups/g1')));
  await env.withSecurityRulesDisabled(async context => {
    const value = (await get(ref(context.database()))).val() || {};
    for (const path of ['groups', 'groupMembers', 'userGroups', 'groupRooms', 'groupPendingRooms', 'groupRoutes']) {
      if (!value[path]) throw new Error(`v46 alteró ${path}`);
    }
  });
});

test('v47 elimina primero las rutas y después todo el grupo sin ramas huérfanas', async () => {
  await seed({
    groups: { g1: group() }, groupMembers: { g1: { owner: member('owner'), alice: member('member') } },
    userGroups: { owner: { g1: index('owner') }, alice: { g1: index('member') } },
    groupRooms: { g1: { room: room('owner') } }, groupPendingRooms: { g1: { pending: room('alice') } },
    groupRoutes: { g1: { r1: savedRoute({ scope: 'group', ownerUid: 'owner', groupId: 'g1' }) } }
  });
  const owner = env.authenticatedContext('owner').database();
  await assertSucceeds(remove(ref(owner, 'groupRoutes/g1/r1')));
  await assertSucceeds(remove(ref(owner, 'groups/g1')));
  await assertSucceeds(update(ref(owner), {
    'groupMembers/g1/owner': null, 'groupMembers/g1/alice': null,
    'userGroups/owner/g1': null, 'userGroups/alice/g1': null,
    'groupRooms/g1/room': null, 'groupPendingRooms/g1/pending': null
  }));
  await env.withSecurityRulesDisabled(async context => {
    const value = (await get(ref(context.database()))).val() || {};
    for (const path of ['groups', 'groupMembers', 'userGroups', 'groupRooms', 'groupPendingRooms', 'groupRoutes']) {
      const branch = value[path] || {};
      if (path === 'userGroups' ? branch.owner?.g1 || branch.alice?.g1 : branch.g1) throw new Error(`Quedó una referencia en ${path}`);
    }
  });
});

test('un username reservado no publica ningún perfil por sí solo', async () => {
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({ pendingUsername: 'isaac' })));
  await assertSucceeds(set(ref(alice, 'publicProfileOwners/isaac'), publicOwner()));
  await assertFails(get(ref(anonymous, 'publicProfileOwners/isaac')));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
});

test('el visitante lee solo view cuando el owner y el control la activan', async () => {
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({ pendingUsername: 'isaac' })));
  await assertSucceeds(set(ref(alice, 'publicProfileOwners/isaac'), publicOwner()));
  await assertSucceeds(set(ref(alice, 'publicProfiles/isaac/view'), publicView()));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertSucceeds(set(ref(alice, 'publicProfileOwners/isaac/state'), 'active'));
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({
    published: true, currentUsername: 'isaac', pendingUsername: '', updatedAt: 200
  })));
  await assertSucceeds(get(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac')));
  await assertFails(get(ref(anonymous, 'publicProfileOwners/isaac')));
  await assertFails(get(ref(anonymous, 'publicProfileControls/alice')));
});

test('la reserva concurrente concede un username a exactamente un usuario', async () => {
  const alice = env.authenticatedContext('alice').database();
  const bob = env.authenticatedContext('bob').database();
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({ pendingUsername: 'isaac' })));
  await assertSucceeds(set(ref(bob, 'publicProfileControls/bob'), publicControl({ pendingUsername: 'isaac' })));
  const outcomes = await Promise.allSettled([
    set(ref(alice, 'publicProfileOwners/isaac'), publicOwner('alice')),
    set(ref(bob, 'publicProfileOwners/isaac'), publicOwner('bob'))
  ]);
  assert.equal(outcomes.filter(result => result.status === 'fulfilled').length, 1);
  assert.equal(outcomes.filter(result => result.status === 'rejected').length, 1);
});

test('usernames inválidos, mayúsculas y reservados son denegados por reglas', async () => {
  const alice = env.authenticatedContext('alice').database();
  for (const username of ['Isaac', 'ab']) {
    await assertFails(set(ref(alice, 'publicProfileControls/alice'), publicControl({ pendingUsername: username })));
  }
  for (const username of ['admin', 'administrador', 'profiles', 'escapistas', 'codex-smoke-user']) {
    await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({ pendingUsername: username })));
    await assertFails(set(ref(alice, `publicProfileOwners/${username}`), publicOwner()));
  }
});

test('el namespace codex-smoke permanece bloqueado para usuarios normales', async () => {
  const alice = env.authenticatedContext('alice').database();
  const username = 'codex-smoke-prueba';
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({ pendingUsername: username })));
  await assertFails(set(ref(alice, `publicProfileOwners/${username}`), publicOwner()));
});

test('dos usernames operativos normales completan reserva, publicación y cleanup', async () => {
  const alice = env.authenticatedContext('alice').database();
  const outsider = env.authenticatedContext('outsider').database();
  const anonymous = env.unauthenticatedContext().database();
  for (const [index, username] of ['v48test-preflight-a', 'v48test-preflight-b'].entries()) {
    const createdAt = 500 + index * 100;
    await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({
      pendingUsername: username, updatedAt: createdAt
    })));
    await assertSucceeds(set(ref(alice, `publicProfileOwners/${username}`), publicOwner('alice', {
      createdAt, updatedAt: createdAt
    })));
    await assertFails(set(ref(outsider, `publicProfileOwners/${username}`), publicOwner('outsider', {
      createdAt, updatedAt: createdAt
    })));
    await assertSucceeds(set(ref(alice, `publicProfiles/${username}/view`), publicView(username, {
      updatedAt: createdAt
    })));
    await assertFails(get(ref(anonymous, `publicProfiles/${username}/view`)));
    await assertSucceeds(set(ref(alice, `publicProfileOwners/${username}/state`), 'active'));
    await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({
      published: true, currentUsername: username, updatedAt: createdAt + 1
    })));
    await assertSucceeds(get(ref(anonymous, `publicProfiles/${username}/view`)));
    await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({
      published: false, currentUsername: '', updatedAt: createdAt + 2
    })));
    await assertFails(get(ref(anonymous, `publicProfiles/${username}/view`)));
    await assertSucceeds(remove(ref(alice, `publicProfiles/${username}/view`)));
    await assertSucceeds(remove(ref(alice, `publicProfileOwners/${username}`)));
  }
});

test('solo el owner administra la proyección y el ownerUid no puede cambiar', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) },
    publicProfiles: { isaac: { view: publicView() } }
  });
  const bob = env.authenticatedContext('bob').database();
  const alice = env.authenticatedContext('alice').database();
  await assertFails(set(ref(bob, 'publicProfiles/isaac/view'), publicView('isaac', { displayName: 'Bob' })));
  await assertFails(remove(ref(bob, 'publicProfiles/isaac/view')));
  await assertFails(set(ref(bob, 'publicProfileOwners/isaac/ownerUid'), 'bob'));
  await assertFails(set(ref(alice, 'publicProfileOwners/isaac/ownerUid'), 'bob'));
  await assertSucceeds(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', { displayName: 'Isaac Vault', updatedAt: 200 })));
});

test('la view rechaza UID, email, campos internos y bloques ocultos', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) }
  });
  const alice = env.authenticatedContext('alice').database();
  await assertFails(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', { uid: 'alice' })));
  await assertFails(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', { email: 'private@example.test' })));
  await assertFails(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', { displayName: 'private@example.test' })));
  await assertFails(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', {
    visibility: publicVisibility({ showMap: false }), map: { count: 1, roomIds: ['olimpo'] }
  })));
  await assertFails(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', {
    visibility: publicVisibility({ showGroups: true }), groupCount: 2, groupIds: ['g1']
  })));
});

test('una proyección completa válida admite solo sus secciones activas', async () => {
  const visibility = publicVisibility({
    showAvatar: true, showProgress: true, showStats: true, showMap: true,
    showAchievements: true, showRoutes: true, showRoutesInProgress: true, showGroups: true
  });
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac', visibility }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) }
  });
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  const value = publicView('isaac', {
    visibility,
    appearance: { avatarId: 'avatar_vault', avatarImage: '/images/brand/icon-round-192.png', frameId: 'gold', titleId: 'title_legend' },
    xp: 1500,
    stats: { personalEscapes: 100, cities: 20, zones: 8, terror: 30, nonTerror: 65, unclassifiedTerror: 5, routesCompleted: 4, reviews: 12, awardedRooms: 18 },
    map: { count: 2, roomIds: ['olimpo', 'katrina'] },
    achievements: { count: 2, unlocked: ['first_escape', 'enthusiast'], featured: ['enthusiast'] },
    routes: {
      completedCount: 1,
      official: [{ id: 'achoporte', completed: 4, target: 4, state: 'completed', missingRooms: 0 }],
      personal: [{ name: 'Ruta con retirada', completed: 2, target: 4, state: 'degraded', missingRooms: 1 }]
    },
    groupCount: 3
  });
  await assertSucceeds(set(ref(alice, 'publicProfiles/isaac/view'), value));
  await assertSucceeds(get(ref(anonymous, 'publicProfiles/isaac/view')));
});

test('cada bloque público permitido valida de forma independiente', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) }
  });
  const alice = env.authenticatedContext('alice').database();
  const cases = [
    publicView('isaac', {
      visibility: publicVisibility({ showAvatar: true }),
      appearance: { avatarId: 'avatar_vault', avatarImage: '/images/brand/icon-round-192.png', frameId: 'gold', titleId: 'title_legend' }
    }),
    publicView('isaac', { visibility: publicVisibility({ showProgress: true }), xp: 1500 }),
    publicView('isaac', {
      visibility: publicVisibility({ showStats: true }),
      stats: { personalEscapes: 1, cities: 1, zones: 1, terror: 0, nonTerror: 1, unclassifiedTerror: 0, routesCompleted: 0, reviews: 0, awardedRooms: 0 }
    }),
    publicView('isaac', { visibility: publicVisibility({ showMap: true }), map: { count: 2, roomIds: ['olimpo', 'katrina'] } }),
    publicView('isaac', {
      visibility: publicVisibility({ showAchievements: true }),
      achievements: { count: 2, unlocked: ['first_escape', 'enthusiast'], featured: ['enthusiast'] }
    }),
    publicView('isaac', {
      visibility: publicVisibility({ showRoutes: true, showRoutesInProgress: true }),
      routes: { completedCount: 1 }
    }),
    publicView('isaac', {
      visibility: publicVisibility({ showRoutes: true, showRoutesInProgress: true }),
      routes: {
        completedCount: 1,
        official: [{ id: 'achoporte', completed: 4, target: 4, state: 'completed', missingRooms: 0 }]
      }
    }),
    publicView('isaac', {
      visibility: publicVisibility({ showRoutes: true, showRoutesInProgress: true }),
      routes: {
        completedCount: 1,
        personal: [{ name: 'Ruta con retirada', completed: 2, target: 4, state: 'degraded', missingRooms: 1 }]
      }
    }),
    publicView('isaac', { visibility: publicVisibility({ showGroups: true }), groupCount: 3 })
  ];
  const labels = ['appearance', 'progress', 'stats', 'map', 'achievements', 'routes-base', 'routes-official', 'routes-personal', 'groups'];
  for (const [index, value] of cases.entries()) {
    try {
      await assertSucceeds(set(ref(alice, 'publicProfiles/isaac/view'), { ...value, updatedAt: 200 + index }));
    } catch (error) {
      throw new Error(`bloque ${labels[index]} rechazado`, { cause: error });
    }
  }
});

test('ocultar logros sustituye la view completa y elimina el bloque', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) },
    publicProfiles: { isaac: { view: publicView('isaac', {
      visibility: publicVisibility({ showAchievements: true }),
      achievements: { count: 1, unlocked: ['first_escape'], featured: ['first_escape'] }
    }) } }
  });
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  await assertSucceeds(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', { updatedAt: 200 })));
  const result = (await get(ref(anonymous, 'publicProfiles/isaac/view'))).val();
  assert.equal(Object.hasOwn(result, 'achievements'), false);
});

test('despublicar corta primero la lectura y después permite borrar la view', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) },
    publicProfiles: { isaac: { view: publicView() } }
  });
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice/published'), false));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertSucceeds(remove(ref(alice, 'publicProfiles/isaac/view')));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
});

test('cambiar username prepara la nueva view y conmuta una sola URL pública', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) },
    publicProfiles: { isaac: { view: publicView() } }
  });
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice/pendingUsername'), 'isaac-vault'));
  await assertSucceeds(set(ref(alice, 'publicProfileOwners/isaac-vault'), publicOwner('alice', { createdAt: 200, updatedAt: 200 })));
  await assertSucceeds(set(ref(alice, 'publicProfiles/isaac-vault/view'), publicView('isaac-vault', { updatedAt: 200 })));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac-vault/view')));
  await assertSucceeds(set(ref(alice, 'publicProfileOwners/isaac-vault/state'), 'active'));
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({
    published: true, currentUsername: 'isaac-vault', pendingUsername: 'isaac-vault', previousUsername: 'isaac', updatedAt: 300
  })));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertSucceeds(get(ref(anonymous, 'publicProfiles/isaac-vault/view')));
  await assertSucceeds(remove(ref(alice, 'publicProfiles/isaac/view')));
  await assertSucceeds(set(ref(alice, 'publicProfileOwners/isaac/state'), 'retired'));
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice'), publicControl({
    published: true, currentUsername: 'isaac-vault', updatedAt: 400
  })));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertSucceeds(get(ref(anonymous, 'publicProfiles/isaac-vault/view')));
});

test('un cambio de visibilidad corta la lectura hasta reemplazar la proyección', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) },
    publicProfiles: { isaac: { view: publicView() } }
  });
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  const visibility = publicVisibility({ showStats: true });
  await assertSucceeds(set(ref(alice, 'publicProfileControls/alice/visibility'), visibility));
  await assertFails(get(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertSucceeds(set(ref(alice, 'publicProfiles/isaac/view'), publicView('isaac', {
    visibility,
    stats: { personalEscapes: 1, cities: 1, zones: 1, terror: 0, nonTerror: 1, unclassifiedTerror: 0, routesCompleted: 0, reviews: 0, awardedRooms: 0 },
    updatedAt: 200
  })));
  await assertSucceeds(get(ref(anonymous, 'publicProfiles/isaac/view')));
});

test('el cliente real publica, renombra y despublica usando exclusivamente las ramas autorizadas', async () => {
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  const api = publicClientApi(alice, anonymous);
  const buildProjection = ({ username, visibility }) => publicView(username, { visibility, updatedAt: api.tick() });

  await publicProfileClient.save(api, { uid: 'alice', username: 'isaac', published: true, visibility: publicVisibility(), buildProjection });
  assert.equal(await api.publicReadable('isaac'), true);
  await publicProfileClient.save(api, { uid: 'alice', username: 'isaac-vault', published: true, visibility: publicVisibility(), buildProjection });
  assert.equal(await api.publicReadable('isaac'), false);
  assert.equal(await api.publicReadable('isaac-vault'), true);
  await publicProfileClient.unpublish(api, 'alice');
  assert.equal(await api.publicReadable('isaac-vault'), false);
  await assertFails(get(ref(anonymous, 'publicProfileOwners/isaac-vault')));
  await assertFails(get(ref(anonymous, 'publicProfileControls/alice')));
});

test('fallos parciales del cliente son privados, recuperables e idempotentes en Emulator', async () => {
  const publishSteps = ['control-intent', 'owner-reserved', 'view-staged', 'owner-activated'];
  for (const [index, failStep] of publishSteps.entries()) {
    await env.clearDatabase();
    const alice = env.authenticatedContext('alice').database();
    const anonymous = env.unauthenticatedContext().database();
    const api = publicClientApi(alice, anonymous);
    const username = `publish-${index}`;
    const buildProjection = ({ username: name, visibility }) => publicView(name, { visibility, updatedAt: api.tick() });
    const input = { uid: 'alice', username, published: true, visibility: publicVisibility(), buildProjection };
    await assert.rejects(publicProfileClient.save(api, input, {
      afterStep(step) { if (step === failStep) throw new Error(failStep); }
    }));
    assert.equal(await api.publicReadable(username), false, `${failStep} no debe publicar`);
    await publicProfileClient.save(api, input);
    assert.equal(await api.publicReadable(username), true, `${failStep} debe recuperarse`);
  }

  const renameSteps = ['rename-control-intent', 'rename-owner-reserved', 'rename-view-staged', 'rename-owner-activated', 'rename-control-switched', 'rename-old-view-removed', 'rename-old-owner-retired'];
  for (const [index, failStep] of renameSteps.entries()) {
    await env.clearDatabase();
    const alice = env.authenticatedContext('alice').database();
    const anonymous = env.unauthenticatedContext().database();
    const api = publicClientApi(alice, anonymous);
    const oldUsername = `old-${index}`;
    const nextUsername = `next-${index}`;
    const buildProjection = ({ username, visibility }) => publicView(username, { visibility, updatedAt: api.tick() });
    await publicProfileClient.save(api, { uid: 'alice', username: oldUsername, published: true, visibility: publicVisibility(), buildProjection });
    const input = { uid: 'alice', username: nextUsername, published: true, visibility: publicVisibility(), buildProjection };
    await assert.rejects(publicProfileClient.save(api, input, {
      afterStep(step) { if (step === failStep) throw new Error(failStep); }
    }));
    const visibleCount = Number(await api.publicReadable(oldUsername)) + Number(await api.publicReadable(nextUsername));
    assert.ok(visibleCount <= 1, `${failStep} activó dos URLs`);
    await publicProfileClient.save(api, input);
    assert.equal(await api.publicReadable(oldUsername), false);
    assert.equal(await api.publicReadable(nextUsername), true);
    const oldOwner = (await get(ref(alice, `publicProfileOwners/${oldUsername}`))).val();
    assert.equal(oldOwner.state, 'retired');
  }

  await env.clearDatabase();
  const alice = env.authenticatedContext('alice').database();
  const anonymous = env.unauthenticatedContext().database();
  const api = publicClientApi(alice, anonymous);
  const buildProjection = ({ username, visibility }) => publicView(username, { visibility, updatedAt: api.tick() });
  await publicProfileClient.save(api, { uid: 'alice', username: 'cleanup-fail', published: true, visibility: publicVisibility(), buildProjection });
  await assert.rejects(publicProfileClient.unpublish(api, 'alice', {
    afterStep(step) { if (step === 'unpublish-verified-private') throw new Error(step); }
  }));
  assert.equal(await api.publicReadable('cleanup-fail'), false);
  await publicProfileClient.unpublish(api, 'alice');
  await env.withSecurityRulesDisabled(async context => {
    assert.equal((await get(ref(context.database(), 'publicProfiles/cleanup-fail/view'))).exists(), false);
  });
});

test('outsider y anónimo no administran ninguna rama pública ajena', async () => {
  await seed({
    publicProfileControls: { alice: publicControl({ published: true, currentUsername: 'isaac' }) },
    publicProfileOwners: { isaac: publicOwner('alice', { state: 'active' }) },
    publicProfiles: { isaac: { view: publicView() } }
  });
  const bob = env.authenticatedContext('bob').database();
  const anonymous = env.unauthenticatedContext().database();
  await assertFails(set(ref(bob, 'publicProfileControls/alice/published'), false));
  await assertFails(set(ref(bob, 'publicProfileOwners/isaac/state'), 'retired'));
  await assertFails(set(ref(bob, 'publicProfileOwners/isaac'), publicOwner('bob')));
  await assertFails(set(ref(bob, 'publicProfiles/isaac/view'), publicView('isaac', { displayName: 'Ataque' })));
  await assertFails(remove(ref(bob, 'publicProfiles/isaac/view')));
  await assertFails(set(ref(anonymous, 'publicProfiles/isaac/view'), publicView()));
  await assertFails(remove(ref(anonymous, 'publicProfiles/isaac/view')));
  await assertSucceeds(get(ref(anonymous, 'publicProfiles/isaac/view')));
});
