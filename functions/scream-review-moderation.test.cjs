const test = require('node:test');
const assert = require('node:assert/strict');
const api = require('./scream-review-moderation');
const seasonId = 'horrorland-2026';
const author = { auth: { uid: 'alice', token: {} } };
const moderator = { auth: { uid: 'mod', token: { screamParksModerator: true } } };

function database() {
  const state = {};
  return { state, ref(path) {
    const keys = path.split('/');
    let node = state;
    for (const key of keys.slice(0, -1)) node = node[key] ||= {};
    const leaf = keys.at(-1);
    return {
      async once() { return { val: () => structuredClone(node[leaf] || null) }; },
      async transaction(update) {
        const next = update(structuredClone(node[leaf] || null));
        if (next === undefined) return { committed: false };
        node[leaf] = next;
        return { committed: true, snapshot: { val: () => structuredClone(next) } };
      }
    };
  } };
}
function input(comment = 'Visita de prueba con sustos') {
  return { seasonId, expectedRevision: 0, rating: 8.5, comment,
    visitDate: '2026-10-20', displayName: 'Ana' };
}
test('auth and moderator claim are mandatory', async () => {
  const db = database();
  await assert.rejects(api.submit({ data: input() }, db), { code: 'unauthenticated' });
  await assert.rejects(api.listPending({ ...author, data: { seasonId } }, db),
    { code: 'permission-denied' });
  await assert.rejects(api.decide({ ...author, data: { seasonId, uid: 'alice',
    action: 'APPROVED', expectedFingerprint: 'a'.repeat(64) } }, db), { code: 'permission-denied' });
});
test('one active review per user and season; approval, edit and delete are atomic', async () => {
  const db = database();
  await api.submit({ ...author, data: input() }, db, 1000);
  const queue = await api.listPending({ ...moderator, data: { seasonId } }, db);
  assert.equal(queue.rows.length, 1);
  await api.decide({ ...moderator, data: { seasonId, uid: 'alice', action: 'APPROVED',
    expectedFingerprint: queue.rows[0].fingerprint } }, db, 2000);
  let season = db.state.screamParkReviews[seasonId];
  assert.equal(Object.keys(season.approved).length, 1);
  assert.equal(JSON.stringify(season.approved).includes('alice'), false);
  const before = JSON.stringify(season);
  const duplicate = await api.decide({ ...moderator, data: { seasonId, uid: 'alice',
    action: 'APPROVED', expectedFingerprint: queue.rows[0].fingerprint } }, db, 2100);
  assert.equal(duplicate.changed, false);
  assert.equal(JSON.stringify(season), before);
  await assert.rejects(api.submit({ ...author, data: input('Another old tab') }, db, 3000),
    { code: 'failed-precondition' });
  await api.submit({ ...author, data: { ...input('Opinión editada y pendiente'), expectedRevision: 1 } }, db, 3000);
  season = db.state.screamParkReviews[seasonId];
  assert.equal(Object.keys(season.approved).length, 0);
  assert.equal(season.submissions.alice.status, 'PENDING');
  await assert.rejects(api.decide({ ...moderator, data: { seasonId, uid: 'alice',
    action: 'REJECTED', expectedFingerprint: queue.rows[0].fingerprint } }, db, 3100),
    { code: 'failed-precondition' });
  await api.deleteOwn({ ...author, data: { seasonId, expectedRevision: 2 } }, db, 4000);
  assert.equal(db.state.screamParkReviews[seasonId].submissions.alice, undefined);
});
test('rejection and hiding do not expose an opinion', async () => {
  const db = database();
  await api.submit({ ...author, data: input() }, db, 1000);
  let queue = await api.listPending({ ...moderator, data: { seasonId } }, db);
  await api.decide({ ...moderator, data: { seasonId, uid: 'alice', action: 'REJECTED',
    expectedFingerprint: queue.rows[0].fingerprint } }, db, 2000);
  assert.equal(Object.keys(db.state.screamParkReviews[seasonId].approved).length, 0);
  await api.submit({ ...author, data: { ...input(), expectedRevision: 1 } }, db, 3000);
  queue = await api.listPending({ ...moderator, data: { seasonId } }, db);
  await api.decide({ ...moderator, data: { seasonId, uid: 'alice', action: 'APPROVED',
    expectedFingerprint: queue.rows[0].fingerprint } }, db, 4000);
  await api.decide({ ...moderator, data: { seasonId, uid: 'alice', action: 'HIDDEN',
    expectedFingerprint: queue.rows[0].fingerprint } }, db, 5000);
  assert.equal(Object.keys(db.state.screamParkReviews[seasonId].approved).length, 0);
  assert.equal(db.state.screamParkReviews[seasonId].submissions.alice.status, 'HIDDEN');
});
