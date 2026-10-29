const test = require('node:test');
const assert = require('node:assert/strict');
const { identity, normalizeOpinion, aggregate, createStore } = require('../scream-parks/reviews.js');
const { renderEditorialReview } = require('../editorial-review-renderer.js');
const horrorland = { id: 'horrorland', seasonId: 'horrorland-2026' };

test('park and season identities cannot cross', () => {
  assert.deepEqual(identity(horrorland), { entityId: 'horrorland', seasonId: 'horrorland-2026' });
  assert.throws(() => identity({ id: 'horrorland', seasonId: 'the-village-2026' }));
});
test('opinion validation and HTML escaping', () => {
  assert.equal(normalizeOpinion({ rating: 8.5, comment: 'Muy buena experiencia' }).rating, 8.5);
  for (const rating of [0, 10.1, 8.25, 'NaN'])
    assert.throws(() => normalizeOpinion({ rating, comment: 'Muy buena experiencia' }));
  assert.throws(() => normalizeOpinion({ rating: 8, comment: 'Buena experiencia', displayName: '<script>' }));
  assert.match(renderEditorialReview('## Título\n\n<script>alert(1)</script>'), /&lt;script&gt;/);
});
test('average counts approved records only', () => {
  assert.deepEqual(aggregate({ a: { rating: 8 }, b: { rating: 9 } }), { count: 2, average: 8.5 });
  assert.deepEqual(aggregate({}), { count: 0, average: null });
});
function harness() {
  const values = new Map();
  const calls = [];
  let uid = 'alice';
  const store = createStore({
    getUid: () => uid,
    read: async path => values.get(path) || null,
    call: async (name, payload) => {
      calls.push({ name, payload });
      const path = `screamParkReviews/${payload.seasonId}/submissions/${uid}`;
      if (name === 'submitScreamParkReview') values.set(path, {
        ...payload, entityId: 'horrorland', status: 'PENDING', revision: payload.expectedRevision + 1
      });
      else values.delete(path);
    }
  });
  return { values, calls, store, setUid: value => { uid = value; } };
}
test('client submits and edits through callable with revision guard', async () => {
  const h = harness();
  await h.store.load(horrorland);
  await h.store.submit({ rating: 9, comment: 'Primera opinión', displayName: 'Ana' });
  await h.store.submit({ rating: 8, comment: 'Opinión corregida', displayName: 'Ana' });
  assert.deepEqual(h.calls.map(x => x.payload.expectedRevision), [0, 1]);
  assert.equal(h.store.snapshot().own.status, 'PENDING');
  assert.equal(h.store.snapshot().own.rating, 8);
});
test('delete uses callable, never direct RTDB mutation', async () => {
  const h = harness();
  await h.store.load(horrorland);
  await h.store.submit({ rating: 9, comment: 'Primera opinión' });
  await h.store.deleteOwn();
  assert.equal(h.calls.at(-1).name, 'deleteScreamParkReview');
  assert.equal(h.calls.at(-1).payload.expectedRevision, 1);
  assert.equal(h.store.snapshot().own, null);
});
test('accounts and editions are isolated; guests cannot write', async () => {
  const h = harness();
  await h.store.load(horrorland);
  await h.store.submit({ rating: 8, comment: 'Visita de 2026' });
  h.setUid('bob');
  await h.store.load({ id: 'horrorland', seasonId: 'horrorland-2025' });
  assert.equal(h.store.snapshot().own, null);
  h.setUid(null);
  await assert.rejects(h.store.submit({ rating: 8, comment: 'Visita de prueba' }));
  const locked = createStore({ getUid: () => 'alice', read: async () => null,
    call: async () => { throw Error('unexpected'); }, writable: false });
  await locked.load(horrorland);
  await assert.rejects(locked.submit({ rating: 8, comment: 'Visita de prueba' }));
});
test('moderation queue is cleared when edition or signed-in account changes', async () => {
  let uid = 'moderator-a';
  const store = createStore({
    getUid: () => uid,
    getModerator: async () => true,
    read: async () => null,
    call: async () => ({ rows: [{ uid: 'visitor', fingerprint: 'stale' }] })
  });
  await store.load(horrorland);
  await store.loadQueue();
  assert.equal(store.snapshot().queue.length, 1);
  await store.load({ id: 'horrorland', seasonId: 'horrorland-2025' });
  assert.equal(store.snapshot().queue.length, 0);
  await store.loadQueue();
  uid = 'moderator-b';
  await store.load({ id: 'horrorland', seasonId: 'horrorland-2025' });
  assert.equal(store.snapshot().queue.length, 0);
});
