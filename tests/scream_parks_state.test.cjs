const test = require('node:test');
const assert = require('node:assert/strict');
const State = require('../scream-parks/personal-state.js');

const village2025 = { id: 'the-village', seasonId: 'the-village-2025', name: 'The Village' };
const village2026 = { id: 'the-village', seasonId: 'the-village-2026', name: 'The Village' };
const park = { id: 'horrorland', seasonId: 'horrorland-2026', name: 'Horrorland' };

function fixture() {
  const records = new Map();
  const calls = [];
  let failure = null;
  const api = {
    read: async path => {
      calls.push(['get', path]);
      if (failure) throw failure;
      if (records.has(path)) return records.get(path);
      const descendants = [...records.entries()].filter(([key]) => key.startsWith(`${path}/`));
      if (!descendants.length) return null;
      const result = {};
      for (const [key, value] of descendants) {
        const parts = key.slice(path.length + 1).split('/');
        if (parts.length === 2) (result[parts[0]] ||= {})[parts[1]] = value;
      }
      return result;
    },
    put: async (path, value) => { calls.push(['put', path, value]); if (failure) throw failure; records.set(path, value); },
    remove: async path => { calls.push(['remove', path]); if (failure) throw failure; records.delete(path); },
    now: () => 100,
    setFailure: value => { failure = value; }
  };
  return { records, calls, api, store: State.create(api) };
}

test('edición y entidad tienen identidades estables y no colisionan con escapes', () => {
  assert.deepEqual(State.identity(village2026), { entityId: 'the-village', seasonId: 'the-village-2026' });
  assert.throws(() => State.identity({ id: 'the-village', seasonId: 'horrorland-2026' }));
  assert.throws(() => State.identity({ id: 'the.village', seasonId: 'the.village-2026' }));
});

test('Hecho y Pendiente son exclusivos para una edición y 2025 no completa 2026', async () => {
  const { store, records } = fixture();
  store.setEntries([village2025, village2026]);
  store.setSession('alice');
  await store.transition(village2025, 'pending');
  assert.equal(store.current(village2025).pending, true);
  await store.transition(village2025, 'done');
  assert.deepEqual(store.current(village2025), { done: true, pending: false, favorite: false });
  assert.deepEqual(store.current(village2026), { done: false, pending: false, favorite: false });
  assert.equal(records.get('screamParkUserStates/alice/editions/the-village-2025').seasonId, 'the-village-2025');
  await store.transition(village2025, 'done');
  assert.equal(store.current(village2025).done, false);
});

test('Favorito pertenece a la entidad y se mantiene entre temporadas', async () => {
  const { store, records } = fixture();
  store.setEntries([village2025, village2026]);
  store.setSession('alice');
  await store.transition(village2026, 'favorite');
  assert.equal(store.current(village2025).favorite, true);
  assert.equal(store.current(village2026).favorite, true);
  assert.equal(records.get('screamParkUserStates/alice/favorites/the-village'), true);
  await store.transition(village2025, 'favorite');
  assert.equal(store.current(village2026).favorite, false);
});

test('invitado no escribe; cuentas separadas y recarga recupera sus estados', async () => {
  const { store, records, calls, api } = fixture();
  store.setEntries([park]);
  await assert.rejects(store.transition(park, 'done'), /Entra con Google/);
  assert.equal(calls.length, 0);
  store.setSession('alice');
  await store.transition(park, 'done');
  store.setSession('bob');
  await store.load();
  assert.equal(store.current(park).done, false);
  assert.equal(records.has('screamParkUserStates/bob/editions/horrorland-2026'), false);
  const reopened = State.create(api);
  reopened.setEntries([park]);
  reopened.setSession('alice');
  await reopened.load();
  assert.equal(reopened.current(park).done, true);
});

test('fallo de red no confirma un estado que no se ha guardado', async () => {
  const { store, api } = fixture();
  store.setEntries([park]);
  store.setSession('alice');
  api.setFailure(new Error('network offline'));
  await assert.rejects(store.transition(park, 'pending'), /network offline/);
  assert.equal(store.current(park).pending, false);
  api.setFailure(null);
  await store.transition(park, 'pending');
  assert.equal(store.current(park).pending, true);
});

test('cambios rápidos se serializan por edición y mantienen exclusividad', async () => {
  const { store, records } = fixture();
  store.setEntries([park]);
  store.setSession('alice');
  await Promise.all([store.transition(park, 'pending'), store.transition(park, 'done')]);
  assert.deepEqual(store.current(park), { done: true, pending: false, favorite: false });
  assert.deepEqual(records.get('screamParkUserStates/alice/editions/horrorland-2026').done, true);
});

test('los registros ajenos o con identidad cruzada no aparecen en las listas', async () => {
  const { store, records } = fixture();
  store.setEntries([park]);
  records.set('screamParkUserStates/alice', { editions: {
    'horrorland-2026': { entityId: 'the-village', seasonId: 'horrorland-2026', done: true, pending: false }
  }, favorites: { 'the-village': true } });
  store.setSession('alice');
  await store.load();
  assert.equal(store.selected('done').length, 0);
  assert.equal(store.selected('favorite').length, 0);
});
