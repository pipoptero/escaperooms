/* Shared by the browser and regression tests. No network or storage side effects. */
(function(root) {
  'use strict';
  const slug = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  function canonical(value, aliases = {}) {
    let key = slug(value);
    const seen = new Set();
    while (aliases[key] && !seen.has(key)) {
      seen.add(key);
      key = slug(aliases[key]);
    }
    return key;
  }
  function identity(key, record = {}, aliases = {}) {
    if (aliases[slug(key)]) return canonical(key, aliases);
    const candidates = [key, record.id, record.nombre, record.roomName].map(slug).filter(Boolean);
    const explicit = candidates.find(value => aliases[value] && slug(aliases[value]) !== value);
    // A display name alone cannot prove that two different persisted IDs are aliases.
    return canonical(explicit || key, aliases);
  }
  function timestamp(record) {
    const value = record.updatedAt || record.addedAt || 0;
    if (typeof value === 'number' || /^\d+$/.test(String(value))) return Number(value) || 0;
    return Date.parse(value) || 0;
  }
  function normalize(records = {}, aliases = {}, personal = false) {
    const data = {}, origins = {};
    const entries = Object.entries(records || {}).filter(([, value]) => value && typeof value === 'object')
      .sort(([ka, a], [kb, b]) => timestamp(a) - timestamp(b) || Number(!!a.done) - Number(!!b.done) || ka.localeCompare(kb));
    for (const [oldKey, record] of entries) {
      const key = identity(oldKey, record, aliases);
      if (!key) continue;
      (origins[key] ||= []).push(oldKey);
      // Latest explicit state wins; older metadata is retained where it is missing.
      data[key] = { ...data[key], ...record };
      if (personal) {
        data[key].done = !!record.done;
        data[key].pending = !record.done && !!record.pending;
        if (!data[key].done) delete data[key].completedMinutes;
      }
    }
    return { data, origins };
  }
  function groups(done, pending, aliases) {
    const completed = normalize(done, aliases), planned = normalize(pending, aliases);
    // Both branches cannot represent the same room in the same group.
    for (const key of Object.keys(completed.data)) delete planned.data[key];
    return { done: completed, pending: planned };
  }
  function patchFor(path, key, value, origins = {}) {
    const patch = {};
    for (const oldKey of new Set([...(origins[key] || []), key])) patch[`${path}/${oldKey}`] = null;
    patch[`${path}/${key}`] = value;
    return patch;
  }
  const api = { slug, canonical, identity, normalize, groups, patchFor };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.VaultRoomState = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
