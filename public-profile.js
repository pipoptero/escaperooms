(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VaultPublicProfile = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const SCHEMA_VERSION = 1;
  const USERNAME_MIN = 3;
  const USERNAME_MAX = 30;
  const PUBLIC_LIMITS = Object.freeze({ mapRooms: 500, achievements: 50, featuredAchievements: 3, officialRoutes: 30, personalRoutes: 30 });
  const USERNAME_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const SAFE_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,159}$/;
  const RESERVED_USERNAMES = new Set([
    'admin', 'administrador', 'api', 'app', 'assets', 'auth', 'cuenta',
    'escapista', 'escapistas', 'escape-rooms', 'firebase', 'grupo', 'grupos',
    'images', 'login', 'logout', 'manifest', 'null', 'perfil', 'profiles',
    'privacidad', 'ranking', 'review', 'reviews', 'robots', 'root', 'route',
    'routes', 'rutas', 'salas', 'scripts', 'service-worker', 'sitemap',
    'soporte', 'support', 'system', 'the-vault', 'thevault',
    'thevaultescape', 'undefined', 'vault', 'www'
  ]);
  const VISIBILITY_KEYS = [
    'showAvatar', 'showProgress', 'showStats', 'showMap',
    'showAchievements', 'showRoutes', 'showRoutesInProgress', 'showGroups'
  ];
  const LEVELS = [
    { min: 0, name: 'Recién encerrado' },
    { min: 100, name: 'Buscador de pistas' },
    { min: 250, name: 'Cerrajero' },
    { min: 500, name: 'Maestro de enigmas' },
    { min: 900, name: 'Guardián de The Vault' },
    { min: 1500, name: 'Escapista legendario' }
  ];
  const FORBIDDEN_PUBLIC_KEYS = /^(uid|owneruid|email|provider|providerid|auth|firebase|invite|inviteid|groupid|groupids|memberids)$/i;

  function normalizeUsername(value) {
    return String(value || '')
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .trim()
      .toLowerCase()
      .replace(/[\s_]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  function validateUsername(value) {
    const normalized = normalizeUsername(value);
    if (normalized.length < USERNAME_MIN || normalized.length > USERNAME_MAX) {
      return { valid: false, normalized, error: `Usa entre ${USERNAME_MIN} y ${USERNAME_MAX} caracteres.` };
    }
    if (!USERNAME_PATTERN.test(normalized)) {
      return { valid: false, normalized, error: 'Usa letras, números y guiones, sin espacios ni símbolos.' };
    }
    if (RESERVED_USERNAMES.has(normalized) || normalized.startsWith('codex-smoke-')) {
      return { valid: false, normalized, error: 'Este username está reservado.' };
    }
    return { valid: true, normalized, error: '' };
  }

  function visibility(input) {
    const source = input || {};
    const result = {};
    VISIBILITY_KEYS.forEach(key => { result[key] = source[key] === true; });
    if (!result.showRoutes) result.showRoutesInProgress = false;
    return result;
  }

  function boundedInteger(value, max = 100000) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    return Math.max(0, Math.min(max, Math.round(number)));
  }

  function safeText(value, maxLength) {
    return String(value || '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, maxLength);
  }

  function safeId(value) {
    const id = String(value || '').trim().toLowerCase();
    return SAFE_ID_PATTERN.test(id) ? id : '';
  }

  function uniqueIds(values, limit = 100, label = 'elementos') {
    const found = [];
    const seen = new Set();
    for (const value of Array.isArray(values) ? values : []) {
      const id = safeId(value);
      if (!id || seen.has(id)) continue;
      seen.add(id);
      if (found.length >= limit) throw new Error(`La proyección supera el límite de ${limit} ${label}.`);
      found.push(id);
    }
    return found;
  }

  function safeAvatarImage(value) {
    const image = String(value || '').trim();
    if (/^\/?images\/[a-z0-9_./-]+$/i.test(image)) return image.startsWith('/') ? image : `/${image}`;
    if (/^https:\/\/(?:[a-z0-9-]+\.)*googleusercontent\.com\/[a-z0-9_?&=./%-]+$/i.test(image)) return image;
    return '';
  }

  function levelForXp(value) {
    const xp = boundedInteger(value, 10000000);
    let index = 0;
    LEVELS.forEach((level, candidate) => { if (xp >= level.min) index = candidate; });
    return { index: index + 1, name: LEVELS[index].name, xp };
  }

  function terrorState(room) {
    if (room && room.terror === true) return 'terror';
    if (room && room.terror === false) return 'nonTerror';
    const value = String(room?.terror ?? '').trim().toLowerCase();
    if (['true', 'si', 'sí', 'yes', '1'].includes(value)) return 'terror';
    if (['false', 'no', '0'].includes(value)) return 'nonTerror';
    const theme = String(room?.tematica || room?.theme || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    return theme.includes('terror') || theme.includes('horror') ? 'terror' : 'unclassified';
  }

  function personalStats(rooms, extras = {}) {
    const unique = new Map();
    for (const room of Array.isArray(rooms) ? rooms : []) {
      // Callers that still carry a historical alias may provide canonicalId.
      // Prefer it so one physical room contributes only once to public stats.
      const id = safeId(room?.canonicalId || room?.id || room?.roomId);
      if (id && !unique.has(id)) unique.set(id, room);
    }
    const cities = new Set();
    const zones = new Set();
    let terror = 0;
    let nonTerror = 0;
    let unclassifiedTerror = 0;
    let awardedRooms = 0;
    unique.forEach(room => {
      const city = safeText(room.ciudad || room.city, 80).toLowerCase();
      const zone = safeText(room.comunidad || room.provincia || room.region || room.zone, 80).toLowerCase();
      if (city) cities.add(city);
      if (zone) zones.add(zone);
      const state = terrorState(room);
      if (state === 'terror') terror += 1;
      else if (state === 'nonTerror') nonTerror += 1;
      else unclassifiedTerror += 1;
      if (room.awarded === true || boundedInteger(room.awardCount, 100) > 0) awardedRooms += 1;
    });
    return {
      personalEscapes: unique.size,
      cities: cities.size,
      zones: zones.size,
      terror,
      nonTerror,
      unclassifiedTerror,
      routesCompleted: boundedInteger(extras.routesCompleted),
      reviews: boundedInteger(extras.reviews),
      awardedRooms
    };
  }

  function summarizeOfficialRoutes(routes, includeInProgress) {
    const result = (Array.isArray(routes) ? routes : []).map(route => {
      const id = safeId(route?.id);
      const target = Math.max(1, boundedInteger(route?.target, 100));
      const completed = Math.min(target, boundedInteger(route?.completed, target));
      if (!id || (!includeInProgress && completed < target)) return null;
      return {
        id,
        completed,
        target,
        state: boundedInteger(route?.missingRooms, target) > 0 ? 'degraded' : (completed >= target ? 'completed' : 'in-progress'),
        missingRooms: Math.min(target, boundedInteger(route?.missingRooms, target))
      };
    }).filter(Boolean);
    if (result.length > PUBLIC_LIMITS.officialRoutes) throw new Error(`La proyección supera el límite de ${PUBLIC_LIMITS.officialRoutes} rutas oficiales.`);
    return result;
  }

  function summarizePersonalRoutes(routes, includeInProgress) {
    const result = (Array.isArray(routes) ? routes : []).map(route => {
      const name = safeText(route?.name, 80);
      const target = Math.max(1, boundedInteger(route?.target, 20));
      const completed = Math.min(target, boundedInteger(route?.completed, target));
      const missingRooms = Math.min(target, boundedInteger(route?.missingRooms, target));
      if (!name || (!includeInProgress && completed < target)) return null;
      return {
        name,
        completed,
        target,
        state: missingRooms > 0 ? 'degraded' : (completed >= target ? 'completed' : 'in-progress'),
        missingRooms
      };
    }).filter(Boolean);
    if (result.length > PUBLIC_LIMITS.personalRoutes) throw new Error(`La proyección supera el límite de ${PUBLIC_LIMITS.personalRoutes} rutas personales.`);
    return result;
  }

  function buildPublicView(input) {
    const source = input || {};
    const usernameResult = validateUsername(source.username);
    if (!usernameResult.valid) throw new Error(usernameResult.error);
    const displayName = safeText(source.displayName, 40);
    if (!displayName || displayName.includes('@')) throw new Error('El nombre público no es válido.');
    const flags = visibility(source.visibility);
    const view = {
      schemaVersion: SCHEMA_VERSION,
      published: true,
      indexable: false,
      username: usernameResult.normalized,
      displayName,
      visibility: flags,
      updatedAt: Math.max(1, boundedInteger(source.updatedAt || Date.now(), Number.MAX_SAFE_INTEGER))
    };

    if (flags.showAvatar) {
      view.appearance = {
        avatarId: safeId(source.appearance?.avatarId) || 'avatar_vault',
        frameId: safeId(source.appearance?.frameId) || 'frame_none',
        titleId: safeId(source.appearance?.titleId) || 'title_none'
      };
      const avatarImage = safeAvatarImage(source.appearance?.avatarImage);
      if (avatarImage) view.appearance.avatarImage = avatarImage;
    }
    if (flags.showProgress) view.xp = boundedInteger(source.xp, 10000000);
    if (flags.showStats) {
      const stats = source.stats || {};
      view.stats = {
        personalEscapes: boundedInteger(stats.personalEscapes),
        cities: boundedInteger(stats.cities),
        zones: boundedInteger(stats.zones),
        terror: boundedInteger(stats.terror),
        nonTerror: boundedInteger(stats.nonTerror),
        unclassifiedTerror: boundedInteger(stats.unclassifiedTerror),
        routesCompleted: boundedInteger(stats.routesCompleted),
        reviews: boundedInteger(stats.reviews),
        awardedRooms: boundedInteger(stats.awardedRooms)
      };
    }
    if (flags.showMap) {
      const roomIds = uniqueIds(source.mapRoomIds, PUBLIC_LIMITS.mapRooms, 'salas del mapa');
      view.map = { count: roomIds.length, roomIds };
    }
    if (flags.showAchievements) {
      const unlocked = uniqueIds(source.achievementIds, PUBLIC_LIMITS.achievements, 'logros');
      const unlockedSet = new Set(unlocked);
      view.achievements = {
        count: unlocked.length,
        unlocked,
        featured: uniqueIds(source.featuredAchievementIds, PUBLIC_LIMITS.featuredAchievements, 'logros destacados').filter(id => unlockedSet.has(id))
      };
    }
    if (flags.showRoutes) {
      const official = summarizeOfficialRoutes(source.routes?.official, flags.showRoutesInProgress);
      const personal = summarizePersonalRoutes(source.routes?.personal, flags.showRoutesInProgress);
      view.routes = {
        completedCount: new Set([
          ...official.filter(route => route.state === 'completed').map(route => `official:${route.id}`),
          ...personal.filter(route => route.state === 'completed').map(route => `personal:${route.name.toLowerCase()}`)
        ]).size,
        official,
        personal
      };
    }
    if (flags.showGroups) view.groupCount = boundedInteger(source.groupCount, 1000);
    return view;
  }

  function forbiddenPublicData(value, forbiddenValues = []) {
    const problems = [];
    const secrets = (Array.isArray(forbiddenValues) ? forbiddenValues : [])
      .map(item => String(item || '').trim()).filter(Boolean);
    function inspect(current, path) {
      if (Array.isArray(current)) return current.forEach((item, index) => inspect(item, `${path}[${index}]`));
      if (current && typeof current === 'object') {
        Object.entries(current).forEach(([key, child]) => {
          if (FORBIDDEN_PUBLIC_KEYS.test(key)) problems.push(`${path}.${key}: clave prohibida`);
          inspect(child, `${path}.${key}`);
        });
        return;
      }
      if (typeof current === 'string') {
        secrets.forEach(secret => { if (current.includes(secret)) problems.push(`${path}: contiene un valor privado`); });
      }
    }
    inspect(value, '$');
    return problems;
  }

  function isPublicView(value) {
    return !!value && value.schemaVersion === SCHEMA_VERSION && value.published === true &&
      validateUsername(value.username).valid && safeText(value.displayName, 40) === value.displayName &&
      forbiddenPublicData(value).length === 0;
  }

  function profileUrl(username, origin = 'https://thevaultescape.com') {
    const result = validateUsername(username);
    if (!result.valid) throw new Error(result.error);
    return `${String(origin || '').replace(/\/$/, '')}/escapista/?u=${encodeURIComponent(result.normalized)}`;
  }

  function usernameChangeSteps(currentUsername, nextUsername) {
    const current = currentUsername ? validateUsername(currentUsername) : { valid: true, normalized: '' };
    const next = validateUsername(nextUsername);
    if (!current.valid || !next.valid) throw new Error(next.error || current.error);
    if (current.normalized === next.normalized) return [];
    return [
      { action: 'set-control-pending', username: next.normalized },
      { action: 'reserve-owner', username: next.normalized, raceSafe: true },
      { action: 'stage-view', username: next.normalized, publiclyReadable: false },
      { action: 'activate-owner', username: next.normalized },
      { action: 'switch-control', from: current.normalized, to: next.normalized },
      ...(current.normalized ? [
        { action: 'remove-old-view', username: current.normalized },
        { action: 'retire-old-owner', username: current.normalized }
      ] : []),
      { action: 'clear-control-pending', username: next.normalized }
    ];
  }

  return Object.freeze({
    SCHEMA_VERSION,
    USERNAME_MIN,
    USERNAME_MAX,
    PUBLIC_LIMITS,
    RESERVED_USERNAMES: Object.freeze([...RESERVED_USERNAMES]),
    VISIBILITY_KEYS: Object.freeze([...VISIBILITY_KEYS]),
    LEVELS: Object.freeze(LEVELS.map(level => Object.freeze({ ...level }))),
    normalizeUsername,
    validateUsername,
    visibility,
    levelForXp,
    personalStats,
    buildPublicView,
    buildPublicProfileProjection: buildPublicView,
    forbiddenPublicData,
    isPublicView,
    profileUrl,
    usernameChangeSteps,
    summarizeOfficialRoutes,
    summarizePersonalRoutes
  });
});
