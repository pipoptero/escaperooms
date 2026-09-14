import { after, before, beforeEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { assertFails, assertSucceeds, initializeTestEnvironment } from '@firebase/rules-unit-testing';
import { get, ref, remove, set, update } from 'firebase/database';

const PROJECT_ID = 'demo-the-vault';
let env;

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

async function seed(data) {
  await env.withSecurityRulesDisabled(async context => set(ref(context.database()), data));
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
