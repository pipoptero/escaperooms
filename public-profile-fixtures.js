(function (root, factory) {
  const api = factory(
    typeof module === 'object' && module.exports ? require('./public-profile.js') : root.VaultPublicProfile
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VaultPublicProfileFixtures = api;
})(typeof self !== 'undefined' ? self : this, function (PublicProfile) {
  'use strict';

  if (!PublicProfile) throw new Error('VaultPublicProfile no está disponible.');

  const isaac = PublicProfile.buildPublicView({
    username: 'isaac',
    displayName: 'Isaac',
    updatedAt: 1789426800000,
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
    appearance: {
      avatarId: 'avatar_vault',
      avatarImage: '/images/brand/icon-round-192.png',
      frameId: 'gold',
      titleId: 'title_legend'
    },
    xp: 1865,
    stats: {
      personalEscapes: 127,
      cities: 28,
      zones: 9,
      terror: 54,
      nonTerror: 68,
      unclassifiedTerror: 5,
      routesCompleted: 12,
      reviews: 34,
      awardedRooms: 41
    },
    mapRoomIds: ['olimpo', 'katrina', 'enterprises', 'bajo-segunda', 'la-purga'],
    achievementIds: ['first_escape', 'enthusiast', 'veteran', 'centurion', 'first_review', 'chronicler', 'without_fear', 'award_hunter', 'explorer', 'traveller'],
    featuredAchievementIds: ['centurion', 'without_fear', 'award_hunter'],
    routes: {
      official: [
        { id: 'pain-route-3', completed: 6, target: 6 },
        { id: 'achoporte', completed: 4, target: 4 },
        { id: 'ruta-666', completed: 4, target: 6 }
      ],
      personal: [
        { name: 'Premiadas de Madrid', completed: 3, target: 3 },
        { name: 'Terror en Barcelona', completed: 2, target: 4, missingRooms: 1 }
      ]
    },
    groupCount: 3
  });

  const laura = PublicProfile.buildPublicView({
    username: 'laura',
    displayName: 'Laura',
    updatedAt: 1789426800000,
    visibility: {
      showAvatar: true,
      showProgress: true,
      showStats: false,
      showMap: false,
      showAchievements: true,
      showRoutes: false,
      showRoutesInProgress: false,
      showGroups: false
    },
    appearance: {
      avatarId: 'avatar_initials',
      frameId: 'silver',
      titleId: 'title_chronicler'
    },
    xp: 780,
    achievementIds: ['first_escape', 'enthusiast', 'first_review', 'chronicler', 'complete_review'],
    featuredAchievementIds: ['chronicler', 'complete_review']
  });

  const fixtures = Object.freeze({
    isaac: Object.freeze(isaac),
    laura: Object.freeze(laura)
  });

  function get(username) {
    const normalized = PublicProfile.normalizeUsername(username);
    return fixtures[normalized] ? JSON.parse(JSON.stringify(fixtures[normalized])) : null;
  }

  function state(username) {
    const normalized = PublicProfile.normalizeUsername(username);
    if (normalized === 'privado') return { status: 'unavailable', view: null };
    const view = get(normalized);
    return view ? { status: 'public', view } : { status: 'unavailable', view: null };
  }

  return Object.freeze({ fixtures, get, state });
});
