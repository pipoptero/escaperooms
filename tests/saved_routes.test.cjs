const test = require('node:test');
const assert = require('node:assert/strict');
const routes = require('../saved-routes.js');

const base = overrides => routes.buildRecord({ name: 'Vitoria 2027', ownerUid: 'alice', roomIds: ['a', 'b', 'c'], ...overrides }, 200);

test('construye rutas personales con IDs canónicos sin duplicados', () => {
  assert.deepEqual(base({ roomIds: ['a', 'b', 'a'] }), {
    name: 'Vitoria 2027', description: '', scope: 'personal', ownerUid: 'alice', roomIds: ['a', 'b'],
    createdAt: 200, updatedAt: 200, status: 'active', schemaVersion: 1
  });
});

test('normaliza aliases conocidos y descarta IDs que el catálogo no puede resolver', () => {
  const canonical = { abduction_enterprises: 'enterprises', enterprises: 'enterprises' };
  const route = routes.buildRecord({ name: 'Canónica', ownerUid: 'alice', roomIds: ['abduction_enterprises', 'enterprises', 'desconocida'] }, 200, id => canonical[id] || '');
  assert.deepEqual(route.roomIds, ['enterprises']);
});

test('una ruta grupal conserva grupo, fecha y referencia oficial', () => {
  const route = base({ scope: 'group', groupId: 'g1', plannedDate: 300, officialRouteId: 'pain-route-3' });
  assert.equal(route.groupId, 'g1'); assert.equal(route.plannedDate, 300); assert.equal(route.officialRouteId, 'pain-route-3');
});

test('el progreso personal pasa de 2/4 a 3/4 sin modificar el JSON de la ruta', () => {
  const route = base({ roomIds: ['a', 'b', 'c', 'd'] });
  const stored = JSON.stringify(route);
  const first = routes.progress(route, { personal: { a: { done: true }, b: { done: true }, c: { pending: true } } });
  assert.deepEqual([first.completed, first.target, first.percent, first.phase], [2, 4, 50, 'in-progress']);
  const changed = routes.progress(route, { personal: { a: { done: true }, b: { done: true }, c: { done: true } } });
  assert.deepEqual([changed.completed, changed.target, changed.percent, changed.phase], [3, 4, 75, 'in-progress']);
  assert.equal(JSON.stringify(route), stored);
});

test('el progreso grupal pasa de 2/4 a 3/4, ignora lo personal y no modifica la ruta', () => {
  const route = base({ scope: 'group', groupId: 'g1', roomIds: ['a', 'b', 'c', 'd'] });
  const stored = JSON.stringify(route);
  const first = routes.progress(route, { personal: { c: { done: true }, d: { done: true } }, group: { a: { done: true }, b: { done: true }, c: { pending: true } } });
  assert.deepEqual([first.completed, first.target, first.percent], [2, 4, 50]);
  const changed = routes.progress(route, { personal: { d: { done: true } }, group: { a: { done: true }, b: { done: true }, c: { done: true } } });
  assert.deepEqual([changed.completed, changed.target, changed.percent], [3, 4, 75]);
  assert.equal(changed.rooms[3].done, false);
  assert.equal(JSON.stringify(route), stored);
});

test('reordena con controles discretos y respeta los límites', () => {
  assert.deepEqual(routes.moveRoom(['a', 'b', 'c'], 1, -1), ['b', 'a', 'c']);
  assert.deepEqual(routes.moveRoom(['a', 'b', 'c'], 0, -1), ['a', 'b', 'c']);
});

test('añade y quita salas sin duplicar identidad', () => {
  assert.deepEqual(routes.addRoom(['a'], 'b'), ['a', 'b']);
  assert.deepEqual(routes.addRoom(['a'], 'a'), ['a']);
  assert.deepEqual(routes.removeRoom(['a', 'b'], 'a'), ['b']);
});

test('rechaza rutas incompletas', () => {
  assert.throws(() => routes.buildRecord({ name: '', ownerUid: 'alice', roomIds: ['a'] }));
  assert.throws(() => routes.buildRecord({ name: 'Grupo', ownerUid: 'alice', scope: 'group', roomIds: ['a'] }));
});
