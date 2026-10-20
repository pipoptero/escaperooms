/* Personal Scream Parks state. Escapes, groups, ratings and public profiles are separate. */
(function (root) {
  'use strict';

  const idPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const seasonPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*-(?:19|20)\d{2}$/;

  function identity(entry) {
    const entityId = entry?.id;
    const seasonId = entry?.seasonId;
    if (typeof entityId !== 'string' || !idPattern.test(entityId)
      || typeof seasonId !== 'string' || !seasonPattern.test(seasonId)
      || !seasonId.startsWith(`${entityId}-`)) throw new Error('Identidad de Scream Park no válida.');
    return { entityId, seasonId };
  }

  function nextEdition(entry, previous, action, now) {
    const { entityId, seasonId } = identity(entry);
    if (!['done', 'pending'].includes(action)) throw new Error('Estado desconocido.');
    const done = action === 'done' ? !previous?.done : false;
    const pending = action === 'pending' ? !previous?.pending : false;
    if (!done && !pending) return null;
    return { entityId, seasonId, done, pending, updatedAt: now };
  }

  function create({ read, put, remove, onChange = () => {}, now = Date.now }) {
    let uid = null;
    let editions = {};
    let favorites = {};
    let entries = [];
    let revision = 0;
    let mutationRevision = 0;
    const queue = new Map();

    function notify() { onChange(); }
    function setSession(nextUid) {
      const normalized = typeof nextUid === 'string' && nextUid ? nextUid : null;
      if (uid === normalized) return;
      uid = normalized;
      editions = {};
      favorites = {};
      revision++;
      queue.clear();
      notify();
    }
    function setEntries(nextEntries) {
      if (!Array.isArray(nextEntries)) throw new Error('Catálogo Scream Parks no válido.');
      const seen = new Set();
      nextEntries.forEach(entry => {
        const { entityId, seasonId } = identity(entry);
        if (seen.has(seasonId)) throw new Error('Identidad Scream Park duplicada.');
        seen.add(seasonId);
      });
      entries = nextEntries;
      notify();
    }
    function current(entry) {
      const { entityId, seasonId } = identity(entry);
      const edition = editions[seasonId]?.entityId === entityId ? editions[seasonId] : null;
      return { done: !!edition?.done, pending: !edition?.done && !!edition?.pending,
        favorite: favorites[entityId] === true };
    }
    function selected(kind) {
      if (!['done', 'pending', 'favorite'].includes(kind)) return [];
      const matching = entries.filter(entry => current(entry)[kind]);
      if (kind !== 'favorite') return matching;
      const latestByEntity = new Map();
      matching.forEach(entry => {
        if (!latestByEntity.has(entry.id) || entry.seasonId > latestByEntity.get(entry.id).seasonId)
          latestByEntity.set(entry.id, entry);
      });
      return [...latestByEntity.values()];
    }
    async function load() {
      const loadingUid = uid;
      const generation = revision;
      const mutationAtStart = mutationRevision;
      if (!loadingUid) return;
      const raw = await read(`screamParkUserStates/${loadingUid}`);
      if (uid !== loadingUid || generation !== revision || mutationAtStart !== mutationRevision) return;
      editions = raw?.editions || {};
      favorites = raw?.favorites || {};
      notify();
    }
    function transition(entry, action) {
      const { entityId, seasonId } = identity(entry);
      if (!['done', 'pending', 'favorite'].includes(action)) return Promise.reject(new Error('Estado desconocido.'));
      if (!entries.some(item => item.id === entityId && item.seasonId === seasonId))
        return Promise.reject(new Error('La ficha ya no figura en el catálogo.'));
      const scope = action === 'favorite' ? `favorites/${entityId}` : `editions/${seasonId}`;
      mutationRevision++;
      const waitingFor = queue.get(scope) || Promise.resolve();
      const work = waitingFor.catch(() => {}).then(async () => {
        const savingUid = uid;
        const generation = revision;
        if (!savingUid) throw new Error('Entra con Google para guardar tus Scream Parks.');
        const path = `screamParkUserStates/${savingUid}/${scope}`;
        const previous = await read(path);
        if (uid !== savingUid || generation !== revision) throw new Error('La sesión ha cambiado.');
        const next = action === 'favorite' ? (previous === true ? null : true)
          : nextEdition(entry, previous, action, now());
        if (next === null) await remove(path);
        else await put(path, next);
        if (uid !== savingUid || generation !== revision) return;
        if (action === 'favorite') {
          if (next === null) delete favorites[entityId];
          else favorites[entityId] = true;
        } else if (next === null) delete editions[seasonId];
        else editions[seasonId] = next;
        notify();
      });
      queue.set(scope, work);
      work.finally(() => { if (queue.get(scope) === work) queue.delete(scope); }).catch(() => {});
      return work;
    }
    return { setSession, setEntries, load, transition, current, selected,
      get authenticated() { return !!uid; }, get entries() { return entries; } };
  }

  const api = { identity, nextEdition, create };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.VaultScreamParkPersonalState = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
