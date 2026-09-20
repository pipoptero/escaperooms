const test = require('node:test');
const assert = require('node:assert/strict');
const profile = require('../public-profile.js');
const fixtures = require('../public-profile-fixtures.js');

const fullInput = (overrides = {}) => ({
  username: 'Isaac',
  displayName: 'Isaac',
  updatedAt: 100,
  visibility: {
    showAvatar: true,
    showProgress: true,
    showStats: true,
    showMap: true,
    showAchievements: true,
    showRoutes: true,
    showRoutesInProgress: true,
    showGroups: true
  },
  appearance: { avatarId: 'avatar_vault', avatarImage: '/images/brand/icon-round-192.png', frameId: 'gold', titleId: 'title_legend' },
  xp: 1560,
  stats: { personalEscapes: 12, cities: 3, zones: 2, terror: 4, nonTerror: 7, unclassifiedTerror: 1, routesCompleted: 2, reviews: 6, awardedRooms: 5 },
  mapRoomIds: ['olimpo', 'katrina'],
  achievementIds: ['first_escape', 'enthusiast'],
  featuredAchievementIds: ['enthusiast'],
  routes: {
    official: [{ id: 'achoporte', completed: 4, target: 4 }],
    personal: [{ name: 'Ruta segura', completed: 2, target: 3 }]
  },
  groupCount: 3,
  ...overrides
});

test('username es case-insensitive, elimina espacios y normaliza diacríticos', () => {
  assert.equal(profile.normalizeUsername(' Isaac '), 'isaac');
  assert.equal(profile.normalizeUsername('ISAAC'), 'isaac');
  assert.equal(profile.normalizeUsername('isaac'), 'isaac');
  assert.equal(profile.normalizeUsername('Álex Vault'), 'alex-vault');
  assert.equal(profile.normalizeUsername('alex__vault'), 'alex-vault');
});

test('username rechaza formato, longitud y palabras reservadas', () => {
  for (const value of ['ab', 'a'.repeat(31), 'isaac!', 'admin', 'administrador', 'profiles', 'escapistas', 'thevaultescape', 'codex-smoke-user']) {
    assert.equal(profile.validateUsername(value).valid, false, value);
  }
  assert.equal(profile.validateUsername('isaac-vault').valid, true);
});

test('el harness usa usernames normales y conserva bloqueado codex-smoke', () => {
  for (const value of ['v48test-20260917-a', 'v48test-20260917-b']) {
    assert.deepEqual(profile.validateUsername(value), { valid: true, normalized: value, error: '' });
  }
  assert.equal(profile.validateUsername('codex-smoke-prueba').valid, false);
});

test('la proyección completa solo contiene el contrato público', () => {
  const view = profile.buildPublicView(fullInput({
    uid: 'secret-uid',
    email: 'secret@example.test',
    groupPendingRooms: { g1: { olimpo: true } },
    groupRooms: { g1: { katrina: true } }
  }));
  assert.equal(view.username, 'isaac');
  assert.equal(view.published, true);
  assert.equal(view.indexable, false);
  assert.equal(JSON.stringify(view).includes('secret-uid'), false);
  assert.equal(JSON.stringify(view).includes('secret@example.test'), false);
  assert.equal(Object.hasOwn(view, 'groupPendingRooms'), false);
  assert.equal(Object.hasOwn(view, 'groupRooms'), false);
  assert.deepEqual(profile.forbiddenPublicData(view, ['secret-uid', 'secret@example.test']), []);
});

test('cada sección desactivada está ausente del payload, no solo oculta', () => {
  const view = profile.buildPublicView(fullInput({
    visibility: {
      showAvatar: false,
      showProgress: false,
      showStats: false,
      showMap: false,
      showAchievements: false,
      showRoutes: false,
      showRoutesInProgress: true,
      showGroups: false
    }
  }));
  for (const key of ['appearance', 'xp', 'stats', 'map', 'achievements', 'routes', 'groupCount']) {
    assert.equal(Object.hasOwn(view, key), false, key);
  }
  assert.equal(view.visibility.showRoutesInProgress, false);
});

test('desactivar logros elimina el bloque en una proyección republicada', () => {
  const complete = profile.buildPublicView(fullInput());
  assert.ok(complete.achievements);
  const hidden = profile.buildPublicView(fullInput({
    visibility: { ...fullInput().visibility, showAchievements: false }
  }));
  assert.equal(Object.hasOwn(hidden, 'achievements'), false);
});

test('10 personales y 20 grupales publican exactamente 10 escapes personales', () => {
  const personalRooms = Array.from({ length: 10 }, (_, index) => ({
    id: `personal-${index}`, ciudad: `Ciudad ${index}`, comunidad: 'Catalunya', terror: false
  }));
  const groupRooms = Array.from({ length: 20 }, (_, index) => ({
    id: `group-${index}`, ciudad: `Grupo ${index}`, comunidad: 'Madrid', terror: true
  }));
  const stats = profile.personalStats(personalRooms, { groupRooms });
  assert.equal(stats.personalEscapes, 10);
  assert.equal(stats.terror, 0);
  assert.equal(stats.nonTerror, 10);
  assert.equal(stats.cities, 10);
  assert.equal(groupRooms.length, 20);
});

test('un alias y su ID canónico cuentan como una sola sala personal', () => {
  const stats = profile.personalStats([
    { id: 'abduction_enterprises', canonicalId: 'enterprises', terror: false },
    { id: 'enterprises', canonicalId: 'enterprises', terror: false }
  ]);
  assert.equal(stats.personalEscapes, 1);
  assert.equal(stats.nonTerror, 1);
});

test('terror desconocido no se cuenta como no terror', () => {
  const stats = profile.personalStats([{ id: 'olimpo', terror: null }, { id: 'katrina', terror: false }]);
  assert.equal(stats.unclassifiedTerror, 1);
  assert.equal(stats.nonTerror, 1);
});

test('una ruta con sala retirada conserva un estado degradado', () => {
  const view = profile.buildPublicView(fullInput({
    routes: { official: [], personal: [{ name: 'Ruta histórica', completed: 2, target: 4, missingRooms: 1 }] }
  }));
  assert.equal(view.routes.personal[0].state, 'degraded');
  assert.equal(view.routes.personal[0].missingRooms, 1);
});

test('la fixture parcial de Laura no contiene stats, mapa ni rutas', () => {
  const laura = fixtures.get('LAURA');
  assert.ok(laura.appearance);
  assert.equal(typeof laura.xp, 'number');
  assert.ok(laura.achievements);
  assert.equal(Object.hasOwn(laura, 'stats'), false);
  assert.equal(Object.hasOwn(laura, 'map'), false);
  assert.equal(Object.hasOwn(laura, 'routes'), false);
});

test('privado e inexistente producen el mismo estado público', () => {
  assert.deepEqual(fixtures.state('privado'), { status: 'unavailable', view: null });
  assert.deepEqual(fixtures.state('inexistente'), { status: 'unavailable', view: null });
});

test('el cambio de username reserva y prepara antes de cambiar la lectura activa', () => {
  const steps = profile.usernameChangeSteps('isaac', 'ISAAC Vault');
  assert.deepEqual(steps.map(step => step.action), [
    'set-control-pending', 'reserve-owner', 'stage-view', 'activate-owner',
    'switch-control', 'remove-old-view', 'retire-old-owner', 'clear-control-pending'
  ]);
  assert.equal(steps.find(step => step.action === 'reserve-owner').raceSafe, true);
  assert.equal(steps.find(step => step.action === 'stage-view').publiclyReadable, false);
  assert.equal(steps.find(step => step.action === 'switch-control').to, 'isaac-vault');
});

test('la URL pública usa query parameter normalizado', () => {
  assert.equal(profile.profileUrl('ISAAC'), 'https://thevaultescape.com/escapista/?u=isaac');
});

test('los límites públicos fallan explícitamente y nunca truncan en silencio', () => {
  assert.throws(() => profile.buildPublicProfileProjection(fullInput({
    mapRoomIds: Array.from({ length: profile.PUBLIC_LIMITS.mapRooms + 1 }, (_, i) => `room-${i}`)
  })), /límite de 500 salas/);
  assert.throws(() => profile.buildPublicProfileProjection(fullInput({
    achievementIds: Array.from({ length: profile.PUBLIC_LIMITS.achievements + 1 }, (_, i) => `achievement-${i}`)
  })), /límite de 50 logros/);
  assert.throws(() => profile.buildPublicProfileProjection(fullInput({
    featuredAchievementIds: Array.from({ length: profile.PUBLIC_LIMITS.featuredAchievements + 1 }, (_, i) => `featured-${i}`)
  })), /límite de 3 logros destacados/);
  assert.throws(() => profile.buildPublicProfileProjection(fullInput({
    routes: { official: Array.from({ length: profile.PUBLIC_LIMITS.officialRoutes + 1 }, (_, i) => ({ id: `route-${i}`, completed: 1, target: 1 })), personal: [] }
  })), /límite de 30 rutas oficiales/);
  assert.throws(() => profile.buildPublicProfileProjection(fullInput({
    routes: { official: [], personal: Array.from({ length: profile.PUBLIC_LIMITS.personalRoutes + 1 }, (_, i) => ({ name: `Ruta ${i}`, completed: 1, target: 1 })) }
  })), /límite de 30 rutas personales/);
});
