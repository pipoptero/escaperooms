const test = require('node:test');
const assert = require('node:assert/strict');
const { identity, validStars, normalizeOpinion, aggregate, createStore } = require('../scream-parks/reviews.js');
const { renderEditorialReview } = require('../editorial-review-renderer.js');
const horrorland = { id: 'horrorland', seasonId: 'horrorland-2026' };
const scores = { ambientacion: 4.5, acting: 4, organizacion: 3.5, terror: 5, variedad: 4 };
const opinion = (extra = {}) => ({ scores, text: 'Una experiencia intensa y divertida.', userName: 'Ana', ...extra });

test('identity and five half-star scores are exact', () => {
  assert.deepEqual(identity(horrorland), { entityId: 'horrorland', seasonId: 'horrorland-2026' });
  assert.throws(() => identity({ id: 'horrorland', seasonId: 'the-village-2026' }));
  for (const value of [0.5, 1, 4.5, 5]) assert.equal(validStars(value), true);
  for (const value of [0, 5.5, 4.25, '4.5', NaN]) assert.equal(validStars(value), false);
  assert.deepEqual(normalizeOpinion(opinion()).scores, scores);
  assert.throws(() => normalizeOpinion(opinion({ scores: { ...scores, terror: 4.25 } })));
  assert.throws(() => normalizeOpinion(opinion({ scores: { ambientacion: 5 } })));
  assert.throws(() => normalizeOpinion(opinion({ userName: 'mail@example.com' })));
  assert.match(renderEditorialReview('## Título\n\n<script>alert(1)</script>'), /&lt;script&gt;/);
});

test('category and global means use raw scores, without weighting or pre-rounding', () => {
  const result = aggregate({ a: opinion(), b: opinion({ scores: {
    ambientacion: 5, acting: 3.5, organizacion: 4.5, terror: 4, variedad: 4.5
  } }) });
  assert.equal(result.count, 2);
  assert.deepEqual(result.categories, { ambientacion: 9.5, acting: 7.5, organizacion: 8, terror: 9, variedad: 8.5 });
  assert.equal(result.global, 8.5);
  assert.deepEqual(aggregate({}).count, 0);
});

function harness() {
  const values = new Map();
  const calls = [];
  let uid = 'alice';
  let tick = 1000;
  const getMap = path => values.get(path) || {};
  const store = createStore({
    getUid: () => uid, getUserName: () => 'Ana', isAdmin: () => uid === 'admin',
    clock: () => ++tick,
    read: async path => structuredClone(getMap(path)),
    put: async (path, value) => {
      calls.push({ kind: 'put', path, value });
      const parent = path.slice(0, path.lastIndexOf('/'));
      values.set(parent, { ...getMap(parent), [path.slice(path.lastIndexOf('/') + 1)]: structuredClone(value) });
    },
    remove: async path => {
      calls.push({ kind: 'remove', path });
      const parent = path.slice(0, path.lastIndexOf('/'));
      const copy = { ...getMap(parent) };
      delete copy[path.slice(path.lastIndexOf('/') + 1)];
      values.set(parent, copy);
    }
  });
  return { values, calls, store, setUid: value => { uid = value; } };
}

test('owner publishes immediately, edits once and deletes own review', async () => {
  const h = harness();
  await h.store.load(horrorland);
  await h.store.save(opinion());
  assert.equal(h.store.snapshot().count, 1);
  assert.equal(h.store.snapshot().own.revision, 1);
  await h.store.save(opinion({ text: 'Visita revisada y mejor explicada.' }));
  assert.equal(h.store.snapshot().own.revision, 2);
  assert.equal(h.calls[0].value.createdAt, h.calls[1].value.createdAt);
  assert.equal(h.calls[1].path, 'screamParkReviews/horrorland-2026/alice');
  await h.store.deleteOwn();
  assert.equal(h.store.snapshot().count, 0);
});

test('seasons and accounts are isolated; guest and read-only stores cannot write', async () => {
  const h = harness();
  await h.store.load(horrorland);
  await h.store.save(opinion());
  h.setUid('bob');
  await h.store.load(horrorland);
  assert.equal(h.store.snapshot().own, null);
  h.setUid('alice');
  await h.store.load({ id: 'horrorland', seasonId: 'horrorland-2025' });
  assert.equal(h.store.snapshot().count, 0);
  h.setUid(null);
  await assert.rejects(h.store.save(opinion()));
  const locked = createStore({ getUid: () => 'alice', read: async () => null,
    put: async () => { throw Error('unexpected'); }, writable: false });
  await locked.load(horrorland);
  await assert.rejects(locked.save(opinion()));
});

test('existing admin can remove but cannot edit through the public store', async () => {
  const h = harness();
  await h.store.load(horrorland);
  await h.store.save(opinion());
  h.setUid('admin');
  await h.store.load(horrorland);
  assert.equal(h.store.snapshot().admin, true);
  await h.store.removeAsAdmin('alice');
  assert.equal(h.store.snapshot().count, 0);
  assert.equal(h.calls.at(-1).path, 'screamParkReviews/horrorland-2026/alice');
});
