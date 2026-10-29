"use strict";
const { createHash, randomUUID } = require("node:crypto");
const identities = require("./season-identities.json");

function fail(code, message) { const error = new Error(message); error.code = code; throw error; }
function season(seasonId) {
  if (!Object.hasOwn(identities, seasonId)) fail("invalid-argument", "Unknown season");
  return identities[seasonId];
}
function uid(request, moderator = false) {
  const value = request.auth?.uid;
  if (!value) fail("unauthenticated", "Sign in first");
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(value)) fail("invalid-argument", "Invalid user");
  if (moderator && request.auth.token?.screamParksModerator !== true)
    fail("permission-denied", "Moderator claim required");
  return value;
}
function normalize(input) {
  const rating = Number(input?.rating);
  const comment = String(input?.comment ?? "").trim();
  const visitDate = String(input?.visitDate ?? "").trim();
  const displayName = String(input?.displayName ?? "").trim();
  if (!Number.isFinite(rating) || rating < 1 || rating > 10 || rating * 2 % 1)
    fail("invalid-argument", "Rating must be 1–10 in half points");
  if (Array.from(comment).length < 10 || Array.from(comment).length > 5000)
    fail("invalid-argument", "Comment must have 10–5000 characters");
  if (visitDate && !/^(?:19|20)\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/.test(visitDate))
    fail("invalid-argument", "Invalid visit date");
  if (displayName && (Array.from(displayName).length > 40 || /[<>@\r\n]/.test(displayName)))
    fail("invalid-argument", "Invalid public name");
  return { rating, comment, visitDate, displayName: displayName || "Visitante" };
}
function fingerprint(item) {
  return createHash("sha256").update(JSON.stringify([
    item.entityId, item.seasonId, item.rating, item.comment, item.visitDate,
    item.displayName, item.createdAt, item.updatedAt, item.revision
  ])).digest("hex");
}
function ref(db, seasonId) { season(seasonId); return db.ref(`screamParkReviews/${seasonId}`); }

async function submit(request, db, now = Date.now()) {
  const author = uid(request);
  const { seasonId, expectedRevision } = request.data || {};
  const entityId = season(seasonId);
  const value = normalize(request.data);
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 0)
    fail("invalid-argument", "Invalid revision");
  const target = ref(db, seasonId);
  const before = (await target.once("value")).val();
  let primed = false;
  const result = await target.transaction(state => {
    if (state === null && before !== null && !primed) { primed = true; return before; }
    state ||= {};
    state.submissions ||= {};
    state.approved ||= {};
    const old = state.submissions[author];
    if ((old?.revision || 0) !== expectedRevision) return;
    if (old?.publicId) delete state.approved[old.publicId];
    state.submissions[author] = { entityId, seasonId, ...value, status: "PENDING",
      revision: expectedRevision + 1, createdAt: old?.createdAt || now, updatedAt: now };
    return state;
  }, undefined, false);
  if (!result.committed) fail("failed-precondition", "Opinion changed; reload before editing");
  return { status: "PENDING", revision: expectedRevision + 1 };
}

async function deleteOwn(request, db, now = Date.now()) {
  const author = uid(request);
  const { seasonId, expectedRevision } = request.data || {};
  if (!Number.isSafeInteger(expectedRevision) || expectedRevision < 1)
    fail("invalid-argument", "Invalid revision");
  const auditId = randomUUID().replaceAll("-", "");
  const target = ref(db, seasonId);
  const before = (await target.once("value")).val();
  if (!before?.submissions?.[author]) fail("failed-precondition", "Opinion changed; reload before deleting");
  let primed = false;
  const result = await target.transaction(state => {
    if (state === null && !primed) { primed = true; return before; }
    const old = state?.submissions?.[author];
    if (!old || old.revision !== expectedRevision) return;
    if (old.publicId) delete state.approved?.[old.publicId];
    delete state.submissions[author];
    state.audit ||= {};
    state.audit[auditId] = { uid: author, action: "DELETED_BY_AUTHOR", at: now,
      revision: expectedRevision };
    return state;
  }, undefined, false);
  if (!result.committed) fail("failed-precondition", "Opinion changed; reload before deleting");
  return { deleted: true };
}

async function listPending(request, db) {
  uid(request, true);
  const seasonId = request.data?.seasonId;
  const status = request.data?.status || "PENDING";
  if (!["PENDING", "APPROVED"].includes(status))
    fail("invalid-argument", "Invalid moderation filter");
  const state = (await ref(db, seasonId).once("value")).val() || {};
  const rows = [];
  for (const [author, item] of Object.entries(state.submissions || {})) {
    if (item?.status !== status || item.seasonId !== seasonId
        || item.entityId !== identities[seasonId]) continue;
    rows.push({ uid: author, seasonId, rating: item.rating, comment: item.comment,
      visitDate: item.visitDate, displayName: item.displayName,
      revision: item.revision, fingerprint: fingerprint(item) });
  }
  return { seasonId, status, rows };
}

async function decide(request, db, now = Date.now()) {
  const actorUid = uid(request, true);
  const { seasonId, uid: author, action, expectedFingerprint } = request.data || {};
  season(seasonId);
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(author || "")
      || !["APPROVED", "REJECTED", "HIDDEN"].includes(action)
      || !/^[a-f0-9]{64}$/.test(expectedFingerprint || ""))
    fail("invalid-argument", "Invalid moderation command");
  const publicId = randomUUID().replaceAll("-", "");
  const auditId = randomUUID().replaceAll("-", "");
  let already = false;
  const target = ref(db, seasonId);
  const before = (await target.once("value")).val();
  if (!before?.submissions?.[author]) fail("failed-precondition", "Opinion changed or is no longer pending");
  let primed = false;
  const result = await target.transaction(state => {
    // Admin SDK may invoke the callback with an uncached null before receiving
    // the server value. Returning the read value forces a compare-and-retry.
    if (state === null && !primed) { primed = true; return before; }
    const item = state?.submissions?.[author];
    if (!item || fingerprint(item) !== expectedFingerprint) return;
    if (item.status === action && state.moderation?.[author]?.fingerprint === expectedFingerprint) {
      already = true; return;
    }
    if (action === "HIDDEN" ? item.status !== "APPROVED" : item.status !== "PENDING") return;
    state.approved ||= {};
    state.moderation ||= {};
    state.audit ||= {};
    if (item.publicId) delete state.approved[item.publicId];
    const nextPublicId = action === "APPROVED" ? publicId : null;
    const record = { action, fingerprint: expectedFingerprint, actorUid, decidedAt: now,
      publicId: nextPublicId };
    state.submissions[author] = { ...item, status: action, publicId: nextPublicId };
    state.moderation[author] = record;
    state.audit[auditId] = { ...record, uid: author, seasonId };
    if (nextPublicId) state.approved[nextPublicId] = {
      entityId: item.entityId, seasonId, rating: item.rating, comment: item.comment,
      visitDate: item.visitDate, displayName: item.displayName || "Visitante",
      approvedAt: now, sourceUpdatedAt: item.updatedAt };
    return state;
  }, undefined, false);
  if (already) return { changed: false, seasonId, action };
  if (!result.committed) fail("failed-precondition", "Opinion changed or is no longer pending");
  return { changed: true, seasonId, action, fingerprint: expectedFingerprint };
}
module.exports = { normalize, fingerprint, submit, deleteOwn, listPending, decide };
