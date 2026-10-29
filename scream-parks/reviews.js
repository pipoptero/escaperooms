/* Scream Park reviews: season-scoped and separate from escape-room reviews/votes. */
(function (root) {
  'use strict';
  const ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const SEASON = /^[a-z0-9]+(?:-[a-z0-9]+)*-(?:19|20)\d{2}$/;

  function identity(entry) {
    const entityId = entry?.id || entry?.entityId;
    const seasonId = entry?.seasonId;
    if (!ID.test(entityId || '') || !SEASON.test(seasonId || '') || !seasonId.startsWith(`${entityId}-`))
      throw new Error('Identidad de edición no válida.');
    return { entityId, seasonId };
  }

  function normalizeOpinion(value) {
    const rating = Number(value?.rating);
    const comment = String(value?.comment ?? '').trim();
    const visitDate = String(value?.visitDate ?? '').trim();
    if (!Number.isFinite(rating) || rating < 1 || rating > 10 || rating * 2 % 1 !== 0)
      throw new Error('La valoración debe estar entre 1 y 10, en pasos de 0,5.');
    if (Array.from(comment).length < 10 || Array.from(comment).length > 5000)
      throw new Error('La opinión debe tener entre 10 y 5000 caracteres.');
    if (visitDate && !/^(?:19|20)\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/.test(visitDate))
      throw new Error('Fecha de visita no válida.');
    const displayName = String(value?.displayName ?? '').trim();
    if (displayName && (Array.from(displayName).length > 40 || /[<>@\r\n]/.test(displayName)))
      throw new Error('El nombre público debe tener como máximo 40 caracteres.');
    return { rating, comment, visitDate, displayName };
  }

  function aggregate(approved) {
    const records = Object.values(approved || {}).filter(item => item && Number.isFinite(Number(item.rating))
      && Number(item.rating) >= 1 && Number(item.rating) <= 10);
    return { count: records.length, average: records.length
      ? Math.round(records.reduce((sum, item) => sum + Number(item.rating), 0) / records.length * 10) / 10 : null };
  }

  function createStore({ read, call, getUid, getModerator = async () => false,
    onChange = () => {}, writable = true }) {
    let entry = null;
    let generation = 0;
    let own = null;
    let approved = {};
    let pending = false;
    let moderator = false;
    let queue = [];
    let queueStatus = 'PENDING';
    let loadedUid = null;
    async function load(nextEntry) {
      const { seasonId } = identity(nextEntry);
      const localGeneration = ++generation;
      const viewerUid = getUid();
      if (entry?.seasonId !== seasonId || loadedUid !== viewerUid) {
        queue = [];
        queueStatus = 'PENDING';
      }
      loadedUid = viewerUid;
      entry = nextEntry;
      pending = true;
      onChange();
      try {
        const uid = getUid();
        const [publicRows, personal, moderatorClaim] = await Promise.all([
          read(`screamParkReviews/${seasonId}/approved`, false),
          uid ? read(`screamParkReviews/${seasonId}/submissions/${uid}`, true) : Promise.resolve(null),
          uid ? getModerator() : Promise.resolve(false)
        ]);
        if (localGeneration !== generation) return;
        approved = publicRows && typeof publicRows === 'object' ? publicRows : {};
        own = personal || null;
        moderator = moderatorClaim === true;
      } finally {
        if (localGeneration === generation) { pending = false; onChange(); }
      }
    }
    async function submit(value) {
      if (!writable) throw new Error('Las opiniones nuevas siguen desactivadas.');
      if (!entry) throw new Error('Abre primero la ficha del parque.');
      const uid = getUid();
      if (!uid) throw new Error('Entra con Google para publicar tu opinión.');
      const { seasonId } = identity(entry);
      const normalized = normalizeOpinion(value);
      const next = await call('submitScreamParkReview',
        { seasonId, expectedRevision: own?.revision || 0, ...normalized });
      await load(entry);
      return next;
    }
    async function deleteOwn() {
      if (!writable) throw new Error('Las opiniones nuevas siguen desactivadas.');
      if (!entry || !getUid()) throw new Error('Entra con Google para eliminar tu opinión.');
      const { seasonId } = identity(entry);
      if (own) await call('deleteScreamParkReview',
        { seasonId, expectedRevision: own.revision });
      await load(entry);
    }
    async function loadQueue(status = 'PENDING') {
      if (!entry || !moderator) throw new Error('No tienes permisos de moderación.');
      const { seasonId } = identity(entry);
      const result = await call('listScreamParkReviewQueue', { seasonId, status });
      queue = result.rows || [];
      queueStatus = status;
      onChange();
      return queue;
    }
    async function moderate(row, action) {
      if (!entry || !moderator) throw new Error('No tienes permisos de moderación.');
      const { seasonId } = identity(entry);
      const result = await call('moderateScreamParkReview',
        { seasonId, uid: row.uid, action, expectedFingerprint: row.fingerprint });
      await Promise.all([loadQueue(queueStatus), load(entry)]);
      return result;
    }
    function snapshot() { return { entry, own, approved, pending, writable,
      moderator, queue, queueStatus, ...aggregate(approved) }; }
    return { load, submit, deleteOwn, loadQueue, moderate, snapshot, currentUid: getUid };
  }

  const api = { identity, normalizeOpinion, aggregate, createStore };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.VaultScreamParkReviews = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
