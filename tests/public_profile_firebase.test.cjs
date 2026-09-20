const test = require('node:test');
const assert = require('node:assert/strict');
const profile = require('../public-profile.js');
const client = require('../public-profile-firebase.js');

const UID = 'owner-public-profile';
const VISIBILITY = Object.freeze({
  showAvatar: true, showProgress: true, showStats: true, showMap: true,
  showAchievements: true, showRoutes: true, showRoutesInProgress: true, showGroups: true
});

function clone(value) { return value == null ? value : JSON.parse(JSON.stringify(value)); }
function pathParts(path) { return String(path || '').split('/').filter(Boolean); }
function read(root, path) {
  let node = root;
  for (const part of pathParts(path)) node = node?.[part];
  return clone(node ?? null);
}
function write(root, path, value) {
  const parts = pathParts(path);
  let node = root;
  parts.slice(0, -1).forEach(part => { node[part] ||= {}; node = node[part]; });
  if (value == null) delete node[parts.at(-1)];
  else node[parts.at(-1)] = clone(value);
}

function memoryApi(root = {}, uid = UID) {
  let clock = 1000;
  return {
    root,
    now: () => ++clock,
    get: async path => read(root, path),
    put: async (path, value) => {
      const ownerMatch = /^publicProfileOwners\/([^/]+)$/.exec(path);
      if (ownerMatch) {
        const existing = read(root, path);
        if (existing && existing.ownerUid !== uid) throw new Error('PERMISSION_DENIED');
        if (value.ownerUid !== uid) throw new Error('PERMISSION_DENIED');
      }
      write(root, path, value);
      return clone(value);
    },
    remove: async path => write(root, path, null),
    publicReadable: async username => {
      const view = read(root, `publicProfiles/${username}/view`);
      const owner = read(root, `publicProfileOwners/${username}`);
      const control = owner?.ownerUid ? read(root, `publicProfileControls/${owner.ownerUid}`) : null;
      return !!view && view.published === true && owner?.state === 'active' &&
        control?.published === true && control.currentUsername === username &&
        JSON.stringify(view.visibility) === JSON.stringify(control.visibility);
    }
  };
}

function projection({ username, visibility }) {
  return profile.buildPublicProfileProjection({
    username, displayName: 'Isaac', updatedAt: 1234, visibility,
    appearance: { avatarId: 'avatar_vault', frameId: 'frame_none', titleId: 'title_none' },
    xp: 420,
    stats: { personalEscapes: 2, cities: 1, zones: 1, terror: 1, nonTerror: 1, routesCompleted: 1, reviews: 1, awardedRooms: 0 },
    mapRoomIds: ['room-one', 'room-two'], achievementIds: ['first_escape'], featuredAchievementIds: [],
    routes: { official: [{ id: 'route-one', completed: 2, target: 2 }], personal: [] }, groupCount: 2
  });
}

function saveInput(username, published = true, visibility = VISIBILITY) {
  return { uid: UID, username, published, visibility, buildProjection: projection };
}

async function eventuallySave(api, input, failStep) {
  await assert.rejects(client.save(api, input, {
    afterStep(step) { if (step === failStep) throw new Error(`fallo:${step}`); }
  }), new RegExp(`fallo:${failStep}`));
  return client.save(api, input);
}

test('primera publicación es privada hasta activar control y admite retry en cada residuo', async t => {
  const steps = ['control-intent', 'owner-reserved', 'view-staged', 'owner-activated', 'control-activated', 'publish-verified'];
  for (const step of steps) await t.test(step, async () => {
    const api = memoryApi();
    await eventuallySave(api, saveInput('isaac-vault'), step);
    assert.equal(await api.publicReadable('isaac-vault'), true);
    assert.equal(read(api.root, `publicProfileControls/${UID}`).pendingUsername, '');
    assert.equal(read(api.root, 'publicProfileOwners/isaac-vault').state, 'active');
  });
});

test('reservar username con perfil privado nunca crea una proyección pública', async () => {
  const api = memoryApi();
  const result = await client.save(api, saveInput('isaac-private', false));
  assert.equal(result.control.published, false);
  assert.equal(result.control.currentUsername, 'isaac-private');
  assert.equal(read(api.root, 'publicProfiles/isaac-private/view'), null);
  assert.equal(await api.publicReadable('isaac-private'), false);
});

test('ocultar un bloque bloquea primero la vista anterior y elimina el bloque al reintentar', async () => {
  const api = memoryApi();
  await client.save(api, saveInput('isaac-privacy'));
  const hidden = { ...VISIBILITY, showMap: false };
  await assert.rejects(client.save(api, saveInput('isaac-privacy', true, hidden), {
    afterStep(step) { if (step === 'control-intent') throw new Error('corte'); }
  }));
  assert.equal(await api.publicReadable('isaac-privacy'), false);
  await client.save(api, saveInput('isaac-privacy', true, hidden));
  assert.equal(await api.publicReadable('isaac-privacy'), true);
  assert.equal(read(api.root, 'publicProfiles/isaac-privacy/view').map, undefined);
});

test('despublicar corta lectura antes de borrar y el retry completa limpieza', async () => {
  const api = memoryApi();
  await client.save(api, saveInput('isaac-off'));
  await assert.rejects(client.unpublish(api, UID, {
    afterStep(step) { if (step === 'unpublish-verified-private') throw new Error('corte'); }
  }));
  assert.equal(await api.publicReadable('isaac-off'), false);
  assert.ok(read(api.root, 'publicProfiles/isaac-off/view'));
  await client.unpublish(api, UID);
  assert.equal(read(api.root, 'publicProfiles/isaac-off/view'), null);
});

test('rename publicado se recupera en cada paso sin dos perfiles legibles', async t => {
  const steps = ['rename-control-intent', 'rename-owner-reserved', 'rename-view-staged', 'rename-owner-activated', 'rename-control-switched', 'rename-public-verified', 'rename-old-view-removed', 'rename-old-owner-retired'];
  for (const step of steps) await t.test(step, async () => {
    const api = memoryApi();
    await client.save(api, saveInput('isaac-old'));
    await assert.rejects(client.save(api, saveInput('isaac-new'), {
      afterStep(current) { if (current === step) throw new Error(`fallo:${step}`); }
    }));
    assert.ok(Number(await api.publicReadable('isaac-old')) + Number(await api.publicReadable('isaac-new')) <= 1);
    await client.save(api, saveInput('isaac-new'));
    assert.equal(await api.publicReadable('isaac-old'), false);
    assert.equal(await api.publicReadable('isaac-new'), true);
    assert.equal(read(api.root, 'publicProfileOwners/isaac-old').state, 'retired');
    assert.equal(read(api.root, 'publicProfiles/isaac-old/view'), null);
  });
});

test('rename privado conserva ambos usernames y ninguna vista', async () => {
  const api = memoryApi();
  await client.save(api, saveInput('private-old', false));
  await client.save(api, saveInput('private-new', false));
  assert.equal(read(api.root, 'publicProfileOwners/private-old').state, 'retired');
  assert.equal(read(api.root, 'publicProfileOwners/private-new').state, 'active');
  assert.equal(read(api.root, 'publicProfiles/private-old/view'), null);
  assert.equal(read(api.root, 'publicProfiles/private-new/view'), null);
});

test('reserva concurrente deja un único propietario', async () => {
  const root = {};
  const a = memoryApi(root, 'user-a');
  const b = memoryApi(root, 'user-b');
  write(root, 'publicProfileControls/user-a', client.normalizeControl({ pendingUsername: 'shared-name' }));
  write(root, 'publicProfileControls/user-b', client.normalizeControl({ pendingUsername: 'shared-name' }));
  await client.reserveUsername(a, 'user-a', 'shared-name');
  await assert.rejects(client.reserveUsername(b, 'user-b', 'shared-name'), error => error.code === 'USERNAME_TAKEN');
  assert.equal(read(root, 'publicProfileOwners/shared-name').ownerUid, 'user-a');
});

test('refresh es idempotente y respeta límites sin truncar', async () => {
  const api = memoryApi();
  await client.save(api, saveInput('isaac-refresh'));
  const first = await client.refresh(api, { uid: UID, buildProjection: projection });
  const second = await client.refresh(api, { uid: UID, buildProjection: projection });
  assert.equal(first.view.username, second.view.username);
  assert.throws(() => profile.buildPublicProfileProjection({
    username: 'too-many', displayName: 'Límites', visibility: { showMap: true },
    mapRoomIds: Array.from({ length: profile.PUBLIC_LIMITS.mapRooms + 1 }, (_, index) => `room-${index}`)
  }), /límite/);
});
