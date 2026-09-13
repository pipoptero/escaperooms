const test = require('node:test');
const assert = require('node:assert/strict');
const planner = require('../route-planner.js');

const room = (id, overrides = {}) => ({
  id, nombre: id, empresa: 'Empresa', ciudad: 'Madrid', provincia: 'Madrid', comunidad: 'Comunidad de Madrid',
  duracion: 60, min_personas: 2, max_personas: 6, dificultad: 'Media', terror: false,
  plannerRating: 8, plannerAwardCount: 0, plannerState: {}, ...overrides
});
const config = (overrides = {}) => ({
  zone: { level: 'city', value: 'Madrid' }, count: 3, players: 4,
  experience: 'any', difficulty: 'any', priority: 'recommended', onlyNobody: false, ...overrides
});

test('funciona en modo personal sin grupo y respeta cantidades 1-5', () => {
  const rooms = Array.from({ length: 8 }, (_, i) => room(`r${i}`, { plannerRating: 9 - i / 10 }));
  for (let count = 1; count <= 5; count++) assert.equal(planner.build(rooms, config({ count })).proposals[0].items.length, count);
});

test('excluye hechas en el ámbito y permite pendientes sin duplicarlas', () => {
  const result = planner.build([
    room('done', { plannerState: { scopeDone: true } }),
    room('pending', { plannerState: { scopePending: true } }),
    room('new')
  ], config());
  assert.deepEqual(result.candidates.map(x => x.room.id).sort(), ['new', 'pending']);
  assert.equal(result.proposals[0].items[0].room.id, 'pending');
});

test('la opción estricta excluye estados personales hechos en modo grupo', () => {
  const rooms = [room('mine', { plannerState: { personalDone: true } }), room('nobody')];
  assert.equal(planner.build(rooms, config({ onlyNobody: true })).candidates.length, 1);
  assert.equal(planner.build(rooms, config({ onlyNobody: false })).candidates.length, 2);
});

test('filtra jugadores incompatibles y conserva límites incompletos en cualquiera', () => {
  const rooms = [room('small', { max_personas: 3 }), room('large', { min_personas: 5 }), room('unknown', { min_personas: null, max_personas: null })];
  assert.deepEqual(planner.build(rooms, config({ players: 4 })).candidates.map(x => x.room.id), ['unknown']);
});

test('terror y dificultad son estrictos cuando se solicitan', () => {
  const rooms = [
    room('terror', { terror: true, dificultad: 'Alta' }),
    room('calm', { terror: false, dificultad: 'Baja' }),
    room('unknown', { terror: null, dificultad: null })
  ];
  assert.deepEqual(planner.build(rooms, config({ experience: 'terror', difficulty: 'hard' })).candidates.map(x => x.room.id), ['terror']);
  assert.deepEqual(planner.build(rooms, config({ experience: 'no-terror', difficulty: 'easy' })).candidates.map(x => x.room.id), ['calm']);
});

test('una zona escasa devuelve lo disponible sin rellenar con otras zonas', () => {
  const result = planner.build([room('madrid'), room('toledo', { ciudad: 'Toledo' })], config({ count: 5 }));
  assert.equal(result.available, 1);
  assert.equal(result.proposals[0].items.length, 1);
});

test('solo ofrece ruta compacta con coordenadas suficientes y alternativa distinta', () => {
  const coords = [
    room('a', { plannerRating: 10, plannerCoord: { lat: 40.40, lon: -3.70 } }),
    room('b', { plannerRating: 7, plannerCoord: { lat: 40.401, lon: -3.701 } }),
    room('c', { plannerRating: 9, plannerCoord: { lat: 41.0, lon: -3.0 } })
  ];
  const result = planner.build(coords, config({ count: 2 }));
  assert.ok(result.proposals.some(x => x.id === 'compact'));
  assert.ok(result.proposals.find(x => x.id === 'compact').distanceKm < 1);
  assert.equal(planner.build(coords.map(x => ({ ...x, plannerCoord: null })), config({ count: 2 })).proposals.some(x => x.id === 'compact'), false);
});

test('la prioridad de valoración es independiente de la recomendación', () => {
  const rooms = [room('rated', { plannerRating: 9 }), room('pending', { plannerRating: 7, plannerState: { scopePending: true } })];
  assert.equal(planner.build(rooms, config({ count: 1, priority: 'pending' })).proposals[0].items[0].room.id, 'pending');
  assert.equal(planner.build(rooms, config({ count: 1, priority: 'rated' })).proposals[0].items[0].room.id, 'rated');
});

test('pendiente pesa, pero no desplaza siempre una sala claramente mejor', () => {
  const close = [room('rated', { plannerRating: 9 }), room('pending', { plannerRating: 7, plannerState: { scopePending: true } })];
  const far = [room('excellent', { plannerRating: 10 }), room('weak-pending', { plannerRating: 5, plannerState: { scopePending: true } })];
  assert.equal(planner.build(close, config({ count: 1, priority: 'pending' })).proposals[0].items[0].room.id, 'pending');
  assert.equal(planner.build(far, config({ count: 1, priority: 'pending' })).proposals[0].items[0].room.id, 'excellent');
});

test('mejor valoradas no aplica bonificación de pendiente', () => {
  const items = planner.build([
    room('best', { plannerRating: 9 }),
    room('pending', { plannerRating: 8.9, plannerAwardCount: 5, plannerState: { scopePending: true } })
  ], config({ count: 1, priority: 'rated' })).proposals[0].items;
  assert.equal(items[0].room.id, 'best');
  assert.equal(items[0].plannerScore, 59);
});
