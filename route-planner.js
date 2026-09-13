(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.VaultRoutePlanner = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function text(value) {
    return String(value ?? '').trim();
  }

  function fold(value) {
    return text(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function number(value) {
    const match = text(value).replace(',', '.').match(/\d+(?:\.\d+)?/);
    const parsed = match ? Number(match[0]) : NaN;
    return Number.isFinite(parsed) ? parsed : null;
  }

  function difficulty(value) {
    const raw = fold(value);
    if (!raw) return '';
    const numeric = number(raw);
    if (/baja|facil|iniciacion/.test(raw) || (numeric !== null && numeric <= 4)) return 'easy';
    if (/alta|dificil|experta|muy alta/.test(raw) || (numeric !== null && numeric >= 7)) return 'hard';
    if (/media|medio|moderada|estandar/.test(raw) || numeric !== null) return 'medium';
    return '';
  }

  function roomValue(room, spanish, english) {
    return room?.[spanish] ?? room?.[english];
  }

  function matchesZone(room, zone) {
    if (!zone?.value) return true;
    const field = { city: 'ciudad', province: 'provincia', community: 'comunidad' }[zone.level] || 'ciudad';
    return fold(roomValue(room, field, zone.level)) === fold(zone.value);
  }

  function playerCompatibility(room, players) {
    const min = number(roomValue(room, 'min_personas', 'minPlayers'));
    const max = number(roomValue(room, 'max_personas', 'maxPlayers'));
    if (min !== null && players < min) return { eligible: false, known: true, min, max };
    if (max !== null && players > max) return { eligible: false, known: true, min, max };
    return { eligible: true, known: min !== null || max !== null, min, max };
  }

  function matchesExperience(room, experience) {
    if (!experience || experience === 'any') return true;
    const terror = roomValue(room, 'terror', 'terror');
    if (typeof terror !== 'boolean') return false;
    return experience === 'terror' ? terror : !terror;
  }

  function matchesDifficulty(room, wanted) {
    return !wanted || wanted === 'any' || difficulty(roomValue(room, 'dificultad', 'difficulty')) === wanted;
  }

  function candidate(room, config) {
    if (!matchesZone(room, config.zone)) return null;
    const players = playerCompatibility(room, config.players);
    if (!players.eligible || !matchesExperience(room, config.experience) || !matchesDifficulty(room, config.difficulty)) return null;
    const state = room.plannerState || {};
    if (state.scopeDone) return null;
    if (config.onlyNobody && state.personalDone) return null;
    const rating = Math.max(0, Math.min(10, Number(room.plannerRating) || 0));
    const awards = Math.max(0, Number(room.plannerAwardCount) || 0);
    const commonScore = rating * 6 + (players.known ? 5 : 1) + Math.min(5, awards);
    return { room, rating, awards, commonScore, state, players, coord: room.plannerCoord || null };
  }

  function scoreFor(item, priority) {
    if (priority === 'pending') return item.commonScore + (item.state.scopePending ? 20 : 0);
    if (priority === 'recommended') return item.commonScore + (item.state.scopePending ? 10 : 0) + (!item.state.scopeDone ? 4 : 0);
    return item.commonScore;
  }

  function orderCandidates(items, priority) {
    const result = items.map(item => ({ ...item, plannerScore: scoreFor(item, priority) }));
    result.sort((a, b) => {
      if (priority === 'rated' && b.rating !== a.rating) return b.rating - a.rating;
      return b.plannerScore - a.plannerScore || b.rating - a.rating || text(a.room.nombre || a.room.name).localeCompare(text(b.room.nombre || b.room.name));
    });
    return result;
  }

  function radians(value) { return value * Math.PI / 180; }
  function distanceKm(a, b) {
    if (!a || !b) return null;
    const lat1 = Number(a.lat), lon1 = Number(a.lon), lat2 = Number(b.lat), lon2 = Number(b.lon);
    if (![lat1, lon1, lat2, lon2].every(Number.isFinite)) return null;
    const dLat = radians(lat2 - lat1), dLon = radians(lon2 - lon1);
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(radians(lat1)) * Math.cos(radians(lat2)) * Math.sin(dLon / 2) ** 2;
    return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  }

  function compactRoute(items, count) {
    const located = items.filter(item => item.coord && Number.isFinite(Number(item.coord.lat)) && Number.isFinite(Number(item.coord.lon)));
    if (located.length < count) return null;
    // Keep the compact alternative useful: proximity is optimized among the
    // strongest eligible candidates, rather than recommending any low-signal
    // room merely because it shares an address.
    const pool = located.slice(0, Math.max(count * 6, 30));
    let best = null;
    pool.forEach(start => {
      const route = [start];
      const rest = pool.filter(item => item !== start);
      while (route.length < count && rest.length) {
        rest.sort((a, b) => distanceKm(route.at(-1).coord, a.coord) - distanceKm(route.at(-1).coord, b.coord));
        route.push(rest.shift());
      }
      const km = route.slice(1).reduce((sum, item, i) => sum + distanceKm(route[i].coord, item.coord), 0);
      if (!best || km < best.km) best = { items: route, km };
    });
    return best;
  }

  function signature(items) {
    return items.map(item => text(item.room.id || item.room.nombre || item.room.name)).sort().join('|');
  }

  function build(rooms, config) {
    const count = Math.max(1, Math.min(5, Number(config.count) || 1));
    const candidates = rooms.map(room => candidate(room, config)).filter(Boolean);
    const proposals = [];
    const add = (id, title, items, extra = {}) => {
      if (!items?.length) return;
      const key = signature(items);
      if (proposals.some(route => route.signature === key)) return;
      proposals.push({ id, title, items, signature: key, ...extra });
    };
    const recommended = orderCandidates(candidates, config.priority || 'recommended').slice(0, count);
    add('recommended', 'Ruta recomendada', recommended);
    add('rated', 'Mejor valoradas', orderCandidates(candidates, 'rated').slice(0, count));
    const compact = compactRoute(orderCandidates(candidates, 'recommended'), count);
    if (compact) add('compact', 'Ruta compacta', compact.items, { distanceKm: compact.km });
    return { candidates, proposals, requested: count, available: candidates.length };
  }

  return { build, candidate, compactRoute, difficulty, distanceKm, matchesZone, playerCompatibility, scoreFor };
});
