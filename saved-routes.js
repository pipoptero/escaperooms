(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VaultSavedRoutes = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const text = value => String(value == null ? '' : value).trim();

  function uniqueRoomIds(values, resolveId) {
    const source = Array.isArray(values) ? values : Object.values(values || {});
    const normalized = source.map(value => {
      const id = text(value);
      return typeof resolveId === 'function' ? text(resolveId(id)) : id;
    }).filter(Boolean);
    return [...new Set(normalized)].slice(0, 20);
  }

  function buildRecord(input, now = Date.now(), resolveId) {
    const scope = input.scope === 'group' ? 'group' : 'personal';
    const roomIds = uniqueRoomIds(input.roomIds, resolveId);
    if (!text(input.name) || !text(input.ownerUid) || !roomIds.length) throw new Error('La ruta necesita nombre, propietario y al menos una sala.');
    if (scope === 'group' && !text(input.groupId)) throw new Error('La ruta grupal necesita un grupo.');
    return {
      name: text(input.name).slice(0, 80),
      description: text(input.description).slice(0, 400),
      scope,
      ownerUid: text(input.ownerUid),
      ...(scope === 'group' ? { groupId: text(input.groupId) } : {}),
      roomIds,
      createdAt: Number(input.createdAt) || now,
      updatedAt: now,
      ...(Number(input.plannedDate) > 0 ? { plannedDate: Number(input.plannedDate) } : {}),
      status: 'active',
      schemaVersion: 1,
      ...(text(input.officialRouteId) ? { officialRouteId: text(input.officialRouteId) } : {})
    };
  }

  function roomState(route, roomId, states = {}) {
    const source = route.scope === 'group' ? states.group : states.personal;
    const state = source?.[roomId] || {};
    return { done: !!state.done, pending: !state.done && !!state.pending };
  }

  function progress(route, states = {}) {
    const roomIds = uniqueRoomIds(route?.roomIds);
    const rooms = roomIds.map(roomId => ({ roomId, ...roomState(route || {}, roomId, states) }));
    const completed = rooms.filter(room => room.done).length;
    const target = rooms.length;
    const percent = target ? Math.round((completed / target) * 100) : 0;
    const phase = target > 0 && completed === target ? 'completed' : completed > 0 ? 'in-progress' : 'upcoming';
    return { rooms, completed, target, percent, phase };
  }

  function moveRoom(roomIds, index, direction) {
    const next = uniqueRoomIds(roomIds);
    const target = index + direction;
    if (index < 0 || index >= next.length || target < 0 || target >= next.length) return next;
    [next[index], next[target]] = [next[target], next[index]];
    return next;
  }

  function addRoom(roomIds, roomId) {
    return uniqueRoomIds([...uniqueRoomIds(roomIds), text(roomId)]);
  }

  function removeRoom(roomIds, roomId) {
    return uniqueRoomIds(roomIds).filter(id => id !== text(roomId));
  }

  return { addRoom, buildRecord, moveRoom, progress, removeRoom, uniqueRoomIds };
});
