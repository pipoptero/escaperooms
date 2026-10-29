import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { initializeApp, deleteApp } from 'firebase/app';
import { getAuth, connectAuthEmulator, createUserWithEmailAndPassword } from 'firebase/auth';
import { getFunctions, connectFunctionsEmulator, httpsCallable } from 'firebase/functions';
import { getDatabase, connectDatabaseEmulator, get, goOffline, ref, set } from 'firebase/database';

const requireAdmin = createRequire(new URL('../../functions/package.json', import.meta.url));
const { initializeApp: initializeAdminApp, deleteApp: deleteAdminApp } = requireAdmin('firebase-admin/app');
const { getAuth: getAdminAuth } = requireAdmin('firebase-admin/auth');
const { getDatabase: getAdminDatabase } = requireAdmin('firebase-admin/database');
const projectId = 'demo-the-vault';
process.env.FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:9099';
process.env.FIREBASE_DATABASE_EMULATOR_HOST = '127.0.0.1:9000';
const adminApp = initializeAdminApp({ projectId,
  databaseURL: 'https://demo-the-vault-default-rtdb.firebaseio.com' });
const config = { apiKey: 'demo', authDomain: 'demo-the-vault.firebaseapp.com',
  databaseURL: 'https://demo-the-vault-default-rtdb.firebaseio.com',
  projectId, appId: 'demo-app' };

function client(name) {
  const app = initializeApp(config, name);
  const auth = getAuth(app);
  connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
  const functions = getFunctions(app, 'europe-west1');
  connectFunctionsEmulator(functions, '127.0.0.1', 5001);
  const database = getDatabase(app);
  connectDatabaseEmulator(database, '127.0.0.1', 9000);
  const testAppCheckToken = [
    Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64url'),
    Buffer.from(JSON.stringify({ sub: 'demo-app' })).toString('base64url'),
    'test'
  ].join('.');
  return { app, auth, database,
    noAppCheck: (name, data) => httpsCallable(functions, name)(data),
    async call(name, data) {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      const response = await fetch(`http://127.0.0.1:5001/${projectId}/europe-west1/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Firebase-AppCheck': testAppCheckToken,
          ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ data })
      });
      const body = await response.json();
      if (!response.ok) throw new Error(`${response.status}: ${body.error?.status || 'unknown'} ${body.error?.message || ''}`);
      return { data: body.result ?? body.data };
    }
  };
}
const alice = client('review-alice');
const bob = client('review-bob');
const moderator = client('review-moderator');
const guest = client('review-guest');
const seasonId = 'horrorland-2026';
const approvedPath = `screamParkReviews/${seasonId}/approved`;
try {
  await Promise.all([
    createUserWithEmailAndPassword(alice.auth, 'alice@example.test', 'test-password-123'),
    createUserWithEmailAndPassword(bob.auth, 'bob@example.test', 'test-password-123'),
    createUserWithEmailAndPassword(moderator.auth, 'mod@example.test', 'test-password-123')
  ]);
  await getAdminAuth(adminApp).setCustomUserClaims(moderator.auth.currentUser.uid,
    { screamParksModerator: true });
  await moderator.auth.currentUser.getIdToken(true);
  await assert.rejects(alice.noAppCheck('submitScreamParkReview', { seasonId,
    expectedRevision: 0, rating: 8, comment: 'Visita sin App Check' }));

  await assert.rejects(guest.call('submitScreamParkReview', { seasonId, expectedRevision: 0,
    rating: 8, comment: 'Visita de prueba' }));
  await assert.rejects(alice.call('listScreamParkReviewQueue', { seasonId }));
  await alice.call('submitScreamParkReview', { seasonId, expectedRevision: 0,
    rating: 8.5, comment: 'Una visita de prueba con sustos', displayName: 'Ana', visitDate: '' });
  await assert.rejects(bob.call('submitScreamParkReview', { seasonId: 'unknown-2026',
    expectedRevision: 0, rating: 8, comment: 'Visita de prueba' }));
  assert.equal((await get(ref(guest.database, approvedPath))).exists(), false);
  const queue = (await moderator.call('listScreamParkReviewQueue', { seasonId })).data.rows;
  assert.equal(queue.length, 1);
  assert.equal(queue[0].uid, alice.auth.currentUser.uid);
  await moderator.call('moderateScreamParkReview', { seasonId, uid: alice.auth.currentUser.uid,
    action: 'APPROVED', expectedFingerprint: queue[0].fingerprint });
  const publicRows = (await get(ref(guest.database, approvedPath))).val();
  assert.equal(Object.values(publicRows).length, 1);
  assert.equal(JSON.stringify(publicRows).includes(alice.auth.currentUser.uid), false);
  assert.equal(Object.values(publicRows)[0].displayName, 'Ana');
  await assert.rejects(set(ref(alice.database, approvedPath + '/injected'), { rating: 10 }));
  await assert.rejects(get(ref(bob.database,
    `screamParkReviews/${seasonId}/submissions/${alice.auth.currentUser.uid}`)));
  await alice.call('submitScreamParkReview', { seasonId, expectedRevision: 1,
    rating: 9, comment: 'Opinión editada para nueva moderación', displayName: 'Ana', visitDate: '' });
  assert.equal((await get(ref(guest.database, approvedPath))).exists(), false);
  await assert.rejects(alice.call('submitScreamParkReview', { seasonId, expectedRevision: 1,
    rating: 10, comment: 'Edición obsoleta desde otra pestaña', displayName: 'Ana', visitDate: '' }));
  const revised = (await moderator.call('listScreamParkReviewQueue', { seasonId })).data.rows;
  await moderator.call('moderateScreamParkReview', { seasonId, uid: alice.auth.currentUser.uid,
    action: 'REJECTED', expectedFingerprint: revised[0].fingerprint });
  assert.equal((await get(ref(guest.database, approvedPath))).exists(), false);
  await alice.call('deleteScreamParkReview', { seasonId, expectedRevision: 2 });
  assert.equal((await get(ref(alice.database,
    `screamParkReviews/${seasonId}/submissions/${alice.auth.currentUser.uid}`))).exists(), false);
  console.log('PASS Auth + RTDB + Functions emulator: auth, claim, moderation, privacy, edits, delete, concurrency');
} finally {
  for (const item of [alice, bob, moderator, guest]) goOffline(item.database);
  getAdminDatabase(adminApp).goOffline();
  await Promise.all([alice, bob, moderator, guest].map(item => deleteApp(item.app)));
  await deleteAdminApp(adminApp);
}
process.exit(0);
