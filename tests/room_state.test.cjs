const { test } = require('node:test');
const assert = require('node:assert/strict');
const state = require('../room-state.js');
const aliases = require('../room_aliases.json').aliases;

test('legacy pending and newer done collapse for every account, regardless of order', () => {
  const old = { nombre: 'Parasomnia Bajo Segunda', pending: true, done: false, updatedAt: 100 };
  const done = { nombre: 'Parasomnia Bajo 2ª', pending: false, done: true, updatedAt: 200, completedMinutes: 70 };
  for (const entries of [[['parasomnia_bajo_segunda', old], ['parasomnia_bajo_2', done]], [['parasomnia_bajo_2', done], ['parasomnia_bajo_segunda', old]]]) {
    const result = state.normalize(Object.fromEntries(entries), aliases, true);
    assert.deepEqual(Object.keys(result.data), ['bajo_segunda']);
    assert.equal(result.data.bajo_segunda.pending, false);
    assert.equal(result.data.bajo_segunda.done, true);
    assert.equal(result.data.bajo_segunda.completedMinutes, 70);
    assert.equal(result.origins.bajo_segunda.length, 2);
  }
});

test('general alias chains, accents and separators work beyond Parasomnia', () => {
  const map = { old_name: 'intermediate', intermediate: 'new_name' };
  const result = state.normalize({ 'Óld-name': { done: true }, new_name: { pending: true, updatedAt: 10 } }, map, true);
  assert.equal(Object.keys(result.data).length, 1);
  assert.equal(result.data.new_name.pending, true);
  assert.equal(result.data.new_name.done, false);
});

test('latest explicit personal state wins without resurrecting removed completion time', () => {
  const result = state.normalize({ old: { done: true, completedMinutes: 60, updatedAt: 1 }, room: { pending: true, updatedAt: 2 } }, { old: 'room' }, true);
  assert.equal(result.data.room.pending, true);
  assert.equal(result.data.room.completedMinutes, undefined);
});

test('done wins an undated tie; metadata and unknown rooms survive', () => {
  const result = state.normalize({ old: { pending: true, web: 'https://example.test' }, room: { done: true }, unknown: { done: true, nombre: 'Unknown' } }, { old: 'room' }, true);
  assert.equal(result.data.room.done, true);
  assert.equal(result.data.room.pending, false);
  assert.equal(result.data.room.web, 'https://example.test');
  assert.equal(result.data.unknown.done, true);
});

test('group done suppresses alias pending only within that group', () => {
  const one = state.groups({ room: { roomName: 'Room' } }, { old: { roomName: 'Old' } }, { old: 'room' });
  const two = state.groups({}, { old: { roomName: 'Old' } }, { old: 'room' });
  assert.equal(Object.keys(one.pending.data).length, 0);
  assert.equal(Object.keys(two.pending.data).length, 1);
  assert.deepEqual(one.pending.origins.room, ['old']);
});

test('sparse atomic patch removes all known aliases and leaves other users/groups untouched', () => {
  const patch = state.patchFor('users/a/roomStates', 'room', { done: true }, { room: ['old', 'room'] });
  assert.deepEqual(patch, { 'users/a/roomStates/old': null, 'users/a/roomStates/room': { done: true } });
  assert.deepEqual(state.patchFor('groupPendingRooms/g', 'room', null, { room: ['old'] }), {
    'groupPendingRooms/g/old': null, 'groupPendingRooms/g/room': null
  });
});

test('reading and normalization never mutate source snapshots', () => {
  const source = { old: { pending: true, done: true } }, before = JSON.stringify(source);
  state.normalize(source, { old: 'room' }, true);
  assert.equal(JSON.stringify(source), before);
});

test('normalization is idempotent', () => {
  const first = state.normalize({ parasomnia_bajo_segunda: { pending: true }, parasomnia_bajo_2: { done: true } }, aliases, true).data;
  assert.deepEqual(state.normalize(first, aliases, true).data, first);
});

test('equal display names do not merge different persisted room keys', () => {
  const result = state.normalize({
    company_one_room: { nombre: 'Room', empresa: 'One', done: true },
    company_two_room: { nombre: 'Room', empresa: 'Two', pending: true }
  }, { room: 'room' }, true);
  assert.deepEqual(Object.keys(result.data).sort(), ['company_one_room', 'company_two_room']);
});
