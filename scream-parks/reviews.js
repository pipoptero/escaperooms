/* Public Scream Park reviews: one author record per season, separate from escape rooms. */
(function (root) {
  'use strict';
  const ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const SEASON = /^[a-z0-9]+(?:-[a-z0-9]+)*-(?:19|20)\d{2}$/;
  const CATEGORIES = Object.freeze([
    ['ambientacion', 'Ambientación'], ['acting', 'Acting'],
    ['organizacion', 'Organización'], ['terror', 'Terror'], ['variedad', 'Variedad']
  ]);

  function identity(entry) {
    const entityId = entry?.id || entry?.entityId;
    const seasonId = entry?.seasonId;
    if (!ID.test(entityId || '') || !SEASON.test(seasonId || '') || !seasonId.startsWith(`${entityId}-`))
      throw new Error('Identidad de edición no válida.');
    return { entityId, seasonId };
  }

  function validStars(value) {
    return typeof value === 'number' && Number.isFinite(value)
      && value >= 0.5 && value <= 5 && value * 2 % 1 === 0;
  }

  function normalizeOpinion(value) {
    const scores = value?.scores;
    if (!scores || typeof scores !== 'object' || Array.isArray(scores)
        || Object.keys(scores).length !== CATEGORIES.length
        || CATEGORIES.some(([key]) => !validStars(scores[key])))
      throw new Error('Puntúa las cinco categorías de 0,5 a 5 estrellas, en medios puntos.');
    const text = String(value?.text ?? '').trim();
    if (Array.from(text).length < 10 || Array.from(text).length > 10000)
      throw new Error('La opinión debe tener entre 10 y 10.000 caracteres.');
    const userName = String(value?.userName ?? '').trim() || 'Visitante';
    if (Array.from(userName).length < 2 || Array.from(userName).length > 40 || /[<>@\r\n]/.test(userName))
      throw new Error('El nombre público debe tener entre 2 y 40 caracteres y no ser un correo.');
    return { scores: Object.fromEntries(CATEGORIES.map(([key]) => [key, scores[key]])), text, userName };
  }

  function aggregate(records) {
    const valid = Object.values(records || {}).filter(item => item && CATEGORIES.every(([key]) => validStars(item.scores?.[key])));
    const count = valid.length;
    const categories = Object.fromEntries(CATEGORIES.map(([key]) => [key, count
      ? Math.round(valid.reduce((sum, item) => sum + item.scores[key], 0) / count * 20) / 10 : null]));
    const global = count ? Math.round(valid.reduce((sum, item) => sum
      + CATEGORIES.reduce((subtotal, [key]) => subtotal + item.scores[key], 0), 0)
      / (count * CATEGORIES.length) * 20) / 10 : null;
    return { count, categories, global };
  }

  function createStore({ read, put, remove, getUid, getUserName = () => 'Visitante',
    isAdmin = () => false, onChange = () => {}, writable = true, clock = Date.now }) {
    let entry = null;
    let rows = {};
    let pending = false;
    let generation = 0;
    let viewerUid = null;
    async function load(nextEntry) {
      const { seasonId } = identity(nextEntry);
      const current = ++generation;
      entry = nextEntry;
      viewerUid = getUid();
      rows = {};
      pending = true;
      onChange();
      try {
        const result = await read(`screamParkReviews/${seasonId}`);
        if (current !== generation) return;
        rows = result && typeof result === 'object' ? result : {};
      } finally {
        if (current === generation) { pending = false; onChange(); }
      }
    }
    async function save(input) {
      if (!writable) throw new Error('Las opiniones no están disponibles.');
      const uid = getUid();
      if (!uid || !entry) throw new Error('Entra con Google para escribir tu opinión.');
      const { entityId, seasonId } = identity(entry);
      const previous = rows[uid];
      const value = normalizeOpinion({ ...input, userName: input?.userName || getUserName() });
      const now = clock();
      const record = { entityId, seasonId, ...value, createdAt: previous?.createdAt || now,
        updatedAt: now, revision: (previous?.revision || 0) + 1 };
      await put(`screamParkReviews/${seasonId}/${uid}`, record);
      await load(entry);
      return record;
    }
    async function deleteOwn() {
      const uid = getUid();
      if (!writable || !uid || !entry) throw new Error('Entra con Google para eliminar tu opinión.');
      const { seasonId } = identity(entry);
      if (rows[uid]) await remove(`screamParkReviews/${seasonId}/${uid}`);
      await load(entry);
    }
    async function removeAsAdmin(authorUid) {
      if (!writable || !entry || !getUid() || !isAdmin()) throw new Error('No tienes permisos de administración.');
      const { seasonId } = identity(entry);
      if (!rows[authorUid]) throw new Error('La opinión ya no está disponible.');
      await remove(`screamParkReviews/${seasonId}/${authorUid}`);
      await load(entry);
    }
    function snapshot() {
      const own = viewerUid ? rows[viewerUid] || null : null;
      return { entry, rows, own, pending, writable, admin: !!getUid() && !!isAdmin(), ...aggregate(rows) };
    }
    return { load, save, deleteOwn, removeAsAdmin, snapshot, currentUid: getUid };
  }

  const api = { CATEGORIES, identity, validStars, normalizeOpinion, aggregate, createStore };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.VaultScreamParkReviews = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
