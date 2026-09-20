(function () {
  'use strict';

  const PublicProfile = window.VaultPublicProfile;
  const Fixtures = window.VaultPublicProfileFixtures;
  const ACHIEVEMENTS = {
    first_escape: ['Primera fuga', 'Tu primera cámara superada'],
    enthusiast: ['Escapista habitual', 'Diez escapes personales'],
    veteran: ['Veterano de cámara', 'Cincuenta escapes personales'],
    centurion: ['Centurión escapista', 'Cien escapes personales'],
    first_review: ['La crítica', 'Primera reseña publicada'],
    chronicler: ['Cronista', 'Diez reseñas publicadas'],
    community_voice: ['Voz de la comunidad', 'Veinticinco reseñas'],
    complete_review: ['Análisis completo', 'Una reseña en profundidad'],
    perfectionist: ['Crítico meticuloso', 'Diez análisis completos'],
    timekeeper: ['Contra el reloj', 'Diez tiempos registrados'],
    without_fear: ['Sin miedo', 'Diez experiencias de terror'],
    award_hunter: ['Cazapremios', 'Diez salas premiadas'],
    explorer: ['Explorador', 'Cinco ciudades'],
    traveller: ['Viajero', 'Tres zonas distintas']
  };
  const TITLES = {
    title_none: '',
    title_clue: 'Buscador de pistas',
    title_terror: 'Especialista en terror',
    title_awards: 'Cazapremios',
    title_chronicler: 'Cronista de The Vault',
    title_legend: 'Escapista legendario'
  };
  const OFFICIAL_ROUTES = {
    'pain-route-3': 'Pain Route 3',
    achoporte: 'Achoporte',
    'hells-route': "Hell's Route",
    'ruta-unreal': 'Ruta Unreal',
    'pasaporte-colors': 'Pasaporte Colors',
    'candado-infinito': 'Candado Infinito',
    'pasaporte-elements': 'Pasaporte Elements',
    'ruta-666': 'Ruta 666',
    'movie-route': 'Movie Route',
    'panic-tour': 'Panic Tour'
  };
  let currentView = null;
  let currentUrl = '';

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function hideStates() {
    ['profile-loading', 'profile-unavailable', 'profile-invalid', 'profile-error', 'profile-public'].forEach(id => {
      const element = document.getElementById(id);
      if (element) element.hidden = true;
    });
  }

  function showState(id) {
    hideStates();
    const element = document.getElementById(id);
    if (element) element.hidden = false;
  }

  async function fetchPublicView(username, demo) {
    if (demo) return Fixtures?.state(username)?.view || null;
    const base = String(window.THE_VAULT_FIREBASE_CONFIG?.databaseURL || '').trim();
    if (!base) throw new Error('firebase-unavailable');
    const endpoint = new URL(base);
    endpoint.pathname = `${endpoint.pathname.replace(/\/$/, '')}/publicProfiles/${encodeURIComponent(username)}/view.json`;
    const response = await fetch(endpoint.toString(), {
      cache: 'no-store',
      headers: { Accept: 'application/json' }
    });
    if (response.status === 401 || response.status === 403 || response.status === 404) return null;
    if (!response.ok) throw new Error(`public-profile-http-${response.status}`);
    return response.json();
  }

  function avatarElement(view) {
    const appearance = view.appearance;
    const shell = node('div', `avatar-shell frame-${appearance?.frameId || 'none'}`);
    if (appearance?.avatarImage) {
      const image = node('img');
      image.src = appearance.avatarImage;
      image.alt = `Avatar de ${view.displayName}`;
      image.referrerPolicy = 'no-referrer';
      image.addEventListener('error', () => {
        shell.replaceChildren(node('span', 'avatar-initials', initials(view.displayName)));
      }, { once: true });
      shell.append(image);
    } else {
      shell.append(node('span', 'avatar-initials', initials(view.displayName)));
    }
    return shell;
  }

  function initials(value) {
    return String(value || 'TV').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'TV';
  }

  function makeButton(label, className, handler) {
    const button = node('button', className || 'vault-button', label);
    button.type = 'button';
    button.addEventListener('click', handler);
    return button;
  }

  function renderHero(view) {
    const hero = node('section', 'profile-hero');
    hero.append(avatarElement(view));
    const copy = node('div', 'hero-copy');
    copy.append(node('p', 'eyebrow', 'The Vault Escapist'));
    copy.append(node('h1', '', view.displayName));
    copy.append(node('p', 'username', `@${view.username}`));
    const title = TITLES[view.appearance?.titleId] || '';
    if (title) copy.append(node('span', 'escapist-title', title));
    hero.append(copy);
    if (view.visibility.showProgress && Number.isFinite(view.xp)) {
      const level = PublicProfile.levelForXp(view.xp);
      const card = node('div', 'level-card');
      card.append(node('strong', '', `Nivel ${level.index}`));
      card.append(node('span', '', level.name));
      card.append(node('small', '', `${level.xp.toLocaleString('es-ES')} XP The Vault`));
      hero.append(card);
    }
    return hero;
  }

  function renderStats(stats) {
    const block = node('section', 'profile-block wide');
    const head = node('div', 'block-head');
    head.append(node('h2', '', 'Estadísticas personales'));
    head.append(node('span', '', 'Solo estados personales'));
    block.append(head);
    const grid = node('div', 'stats-grid');
    const items = [
      [stats.personalEscapes, 'Escapes realizados'],
      [stats.cities, 'Ciudades'],
      [stats.zones, 'Zonas'],
      [stats.routesCompleted, 'Rutas completadas'],
      [stats.terror, 'Terror'],
      [stats.nonTerror, 'Sin terror'],
      [stats.unclassifiedTerror, 'Sin clasificar'],
      [stats.awardedRooms, 'Salas premiadas']
    ];
    items.forEach(([value, label]) => {
      const item = node('div', 'stat');
      item.append(node('strong', '', Number(value || 0).toLocaleString('es-ES')));
      item.append(node('span', '', label));
      grid.append(item);
    });
    block.append(grid);
    return block;
  }

  function achievementCard(id, featured) {
    const info = ACHIEVEMENTS[id] || [id.replace(/[_-]/g, ' '), 'Logro The Vault'];
    const card = node('article', `achievement${featured ? ' featured' : ''}`);
    if (featured) card.append(node('span', 'achievement-mark', 'Destacado'));
    const image = node('img');
    image.src = `/images/progress/achievements/badges/${id}.webp`;
    image.alt = '';
    image.loading = 'lazy';
    image.addEventListener('error', () => image.remove(), { once: true });
    card.append(image);
    const copy = node('div');
    copy.append(node('strong', '', info[0]));
    copy.append(node('small', '', info[1]));
    card.append(copy);
    return card;
  }

  function renderAchievements(data) {
    const block = node('section', 'profile-block');
    const head = node('div', 'block-head');
    head.append(node('h2', '', 'Logros'));
    head.append(node('span', '', `${data.count} obtenidos`));
    block.append(head);
    const featured = new Set(data.featured || []);
    const grid = node('div', 'achievement-grid');
    (data.unlocked || []).forEach(id => grid.append(achievementCard(id, featured.has(id))));
    if (!(data.unlocked || []).length) grid.append(node('p', 'map-empty', 'Todavía no hay logros públicos.'));
    block.append(grid);
    return block;
  }

  function routeRow(name, route, official) {
    const row = node('article', 'route-row');
    const copy = node('div');
    copy.append(node('strong', '', name));
    const description = route.state === 'degraded'
      ? `${route.missingRooms} sala${route.missingRooms === 1 ? '' : 's'} ya no ${route.missingRooms === 1 ? 'está' : 'están'} disponible${route.missingRooms === 1 ? '' : 's'}.`
      : official ? 'Ruta oficial personal' : 'Ruta personal';
    copy.append(node('p', '', description));
    row.append(copy);
    row.append(node('div', `route-progress${route.state === 'degraded' ? ' degraded' : ''}`, `${route.completed}/${route.target}`));
    return row;
  }

  function renderRoutes(data) {
    const block = node('section', 'profile-block');
    const head = node('div', 'block-head');
    head.append(node('h2', '', 'Rutas'));
    head.append(node('span', '', `${data.completedCount} completadas`));
    block.append(head);
    const list = node('div', 'routes-list');
    (data.official || []).forEach(route => list.append(routeRow(OFFICIAL_ROUTES[route.id] || route.id, route, true)));
    (data.personal || []).forEach(route => list.append(routeRow(route.name, route, false)));
    if (!list.children.length) list.append(node('p', 'map-empty', 'Todavía no hay rutas públicas.'));
    block.append(list);
    return block;
  }

  async function renderMap(block, data) {
    const stage = node('div', 'map-stage');
    stage.append(node('div', 'map-empty', 'Situando las salas públicas…'));
    block.append(stage);
    try {
      const [catalogResponse, locationsResponse] = await Promise.all([
        fetch('/catalog.json', { cache: 'force-cache' }),
        fetch('/room_locations.json', { cache: 'force-cache' })
      ]);
      if (!catalogResponse.ok || !locationsResponse.ok) throw new Error('map-data');
      const catalogJson = await catalogResponse.json();
      const locationJson = await locationsResponse.json();
      const rooms = new Map((catalogJson.catalogo || []).map(room => [String(room.id), room]));
      const locations = locationJson.locations || {};
      const points = (data.roomIds || []).map(id => {
        const location = locations[id];
        const room = rooms.get(id);
        const confidence = Number(location?.confidence);
        return location && Number.isFinite(Number(location.lat)) && Number.isFinite(Number(location.lon)) &&
          Number.isFinite(confidence) && confidence >= 65
          ? { id, lat: Number(location.lat), lon: Number(location.lon), room }
          : null;
      }).filter(Boolean);
      stage.replaceChildren();
      if (!points.length) {
        stage.append(node('div', 'map-empty', 'Las salas públicas todavía no tienen ubicaciones suficientemente fiables.'));
        return;
      }
      points.forEach(point => {
        const pin = node('span', 'map-pin');
        pin.style.left = `${Math.max(3, Math.min(97, ((point.lon + 10.5) / 15.5) * 100))}%`;
        pin.style.top = `${Math.max(5, Math.min(95, ((44.5 - point.lat) / 9.5) * 100))}%`;
        pin.title = point.room?.nombre || point.id;
        pin.setAttribute('aria-label', point.room?.nombre || point.id);
        stage.append(pin);
      });
      const legend = node('div', 'map-legend');
      points.slice(0, 8).forEach(point => legend.append(node('span', 'map-room', point.room?.nombre || point.id)));
      stage.append(legend);
    } catch {
      stage.replaceChildren(node('div', 'map-empty', 'No se pudo cargar el mapa en este momento.'));
    }
  }

  function renderMapBlock(data) {
    const block = node('section', 'profile-block wide');
    const head = node('div', 'block-head');
    head.append(node('h2', '', 'Mapa escapista'));
    head.append(node('span', '', `${data.count} ubicaciones de salas`));
    block.append(head);
    renderMap(block, data);
    return block;
  }

  function renderGroups(count) {
    const block = node('section', 'profile-block');
    const head = node('div', 'block-head');
    head.append(node('h2', '', 'Grupos'));
    head.append(node('span', '', 'Sin nombres ni miembros'));
    block.append(head);
    const content = node('div', 'group-count');
    content.append(node('strong', '', count));
    content.append(node('span', '', `${count === 1 ? 'grupo' : 'grupos'} escapistas`));
    block.append(content);
    return block;
  }

  function configureShare(view) {
    currentUrl = PublicProfile.profileUrl(view.username);
    const whatsapp = document.getElementById('share-whatsapp');
    if (whatsapp) whatsapp.href = `https://wa.me/?text=${encodeURIComponent(`Mi perfil escapista en The Vault: ${currentUrl}`)}`;
  }

  function renderPublic(view) {
    currentView = view;
    configureShare(view);
    const root = document.getElementById('profile-public');
    root.replaceChildren(renderHero(view));
    const actions = node('div', 'profile-actions');
    actions.append(makeButton('Compartir perfil', 'vault-button', openShareDialog));
    actions.append(makeButton('Copiar enlace', 'vault-button secondary', copyProfileLink));
    const whatsapp = node('a', 'vault-button secondary', 'WhatsApp');
    whatsapp.href = `https://wa.me/?text=${encodeURIComponent(`Mi perfil escapista en The Vault: ${currentUrl}`)}`;
    whatsapp.target = '_blank';
    whatsapp.rel = 'noopener';
    actions.append(whatsapp);
    root.append(actions);
    const grid = node('div', 'profile-grid');
    if (view.visibility.showStats && view.stats) grid.append(renderStats(view.stats));
    if (view.visibility.showMap && view.map) grid.append(renderMapBlock(view.map));
    if (view.visibility.showAchievements && view.achievements) grid.append(renderAchievements(view.achievements));
    if (view.visibility.showRoutes && view.routes) grid.append(renderRoutes(view.routes));
    if (view.visibility.showGroups && Number.isFinite(view.groupCount)) grid.append(renderGroups(view.groupCount));
    grid.append(node('p', 'footer-note', 'Este perfil contiene únicamente la información que su propietario decidió publicar.'));
    root.append(grid);
    showState('profile-public');
    document.title = `${view.displayName} · The Vault Escapist`;
  }

  async function copyText(value) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
    const input = node('textarea');
    input.value = value;
    input.style.position = 'fixed';
    input.style.opacity = '0';
    document.body.append(input);
    input.select();
    document.execCommand('copy');
    input.remove();
  }

  async function copyProfileLink() {
    try {
      await copyText(currentUrl);
      const status = document.getElementById('share-status');
      if (status) status.textContent = 'Enlace copiado.';
    } catch {
      const status = document.getElementById('share-status');
      if (status) status.textContent = 'No se pudo copiar el enlace.';
    }
  }

  function cardStats(view) {
    const items = [];
    if (view.visibility.showStats && view.stats) {
      items.push([view.stats.personalEscapes, 'ESCAPES']);
      items.push([view.stats.routesCompleted, 'RUTAS']);
    }
    if (view.visibility.showAchievements && view.achievements) items.push([view.achievements.count, 'LOGROS']);
    if (view.visibility.showGroups && Number.isFinite(view.groupCount)) items.push([view.groupCount, 'GRUPOS']);
    return items.slice(0, 4);
  }

  async function loadCanvasImage(source) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.crossOrigin = 'anonymous';
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = source;
    });
  }

  async function drawShareCard(view) {
    const canvas = document.getElementById('share-card');
    const context = canvas.getContext('2d');
    const gradient = context.createLinearGradient(0, 0, 1080, 1350);
    gradient.addColorStop(0, '#10170d');
    gradient.addColorStop(.55, '#080b08');
    gradient.addColorStop(1, '#12100a');
    context.fillStyle = gradient;
    context.fillRect(0, 0, 1080, 1350);
    context.strokeStyle = '#6da43a';
    context.lineWidth = 4;
    context.strokeRect(44, 44, 992, 1262);
    context.fillStyle = '#8bd04c';
    context.font = '700 28px monospace';
    context.fillText('THE VAULT ESCAPIST', 84, 112);
    context.fillStyle = '#6f7668';
    context.font = '21px monospace';
    context.fillText(`@${view.username}`, 84, 154);
    const avatarX = 84;
    const avatarY = 214;
    const size = 220;
    context.save();
    context.beginPath();
    context.arc(avatarX + size / 2, avatarY + size / 2, size / 2, 0, Math.PI * 2);
    context.clip();
    context.fillStyle = '#050705';
    context.fillRect(avatarX, avatarY, size, size);
    if (view.visibility.showAvatar && view.appearance?.avatarImage) {
      try {
        const image = await loadCanvasImage(view.appearance.avatarImage);
        context.drawImage(image, avatarX, avatarY, size, size);
      } catch {
        context.fillStyle = '#8bd04c';
        context.font = '800 72px Georgia';
        context.textAlign = 'center';
        context.fillText(initials(view.displayName), avatarX + size / 2, avatarY + 140);
        context.textAlign = 'left';
      }
    } else {
      context.fillStyle = '#8bd04c';
      context.font = '800 72px Georgia';
      context.textAlign = 'center';
      context.fillText(initials(view.displayName), avatarX + size / 2, avatarY + 140);
      context.textAlign = 'left';
    }
    context.restore();
    context.strokeStyle = view.appearance?.frameId === 'gold' ? '#efb94f' : view.appearance?.frameId === 'silver' ? '#d3d9d0' : '#8bd04c';
    context.lineWidth = 10;
    context.beginPath();
    context.arc(avatarX + size / 2, avatarY + size / 2, size / 2 + 4, 0, Math.PI * 2);
    context.stroke();
    context.fillStyle = '#f2f1e9';
    context.font = '800 54px Georgia';
    context.fillText(view.displayName, 350, 282, 620);
    const title = TITLES[view.appearance?.titleId] || '';
    if (title) {
      context.fillStyle = '#efb94f';
      context.font = '28px Georgia';
      context.fillText(title, 350, 342, 620);
    }
    if (view.visibility.showProgress) {
      const level = PublicProfile.levelForXp(view.xp);
      context.fillStyle = '#8bd04c';
      context.font = '24px monospace';
      context.fillText(`NIVEL ${level.index} · ${level.xp} XP`, 350, 400, 620);
    }
    const items = cardStats(view);
    const width = items.length ? Math.min(220, 900 / items.length) : 0;
    items.forEach(([value, label], index) => {
      const x = 84 + index * (width + 10);
      context.fillStyle = '#12180f';
      context.fillRect(x, 520, width, 132);
      context.strokeStyle = '#2c3b25';
      context.strokeRect(x, 520, width, 132);
      context.fillStyle = '#8bd04c';
      context.font = '800 42px Georgia';
      context.fillText(String(value), x + 16, 574, width - 32);
      context.fillStyle = '#767d70';
      context.font = '18px monospace';
      context.fillText(label, x + 16, 620, width - 32);
    });
    if (view.visibility.showAchievements && view.achievements?.featured?.length) {
      context.fillStyle = '#efb94f';
      context.font = '22px monospace';
      context.fillText('LOGROS DESTACADOS', 84, 744);
      view.achievements.featured.slice(0, 3).forEach((id, index) => {
        const info = ACHIEVEMENTS[id] || [id, 'Logro The Vault'];
        const y = 795 + index * 96;
        context.fillStyle = '#11160f';
        context.fillRect(84, y, 912, 72);
        context.strokeStyle = '#34462a';
        context.strokeRect(84, y, 912, 72);
        context.fillStyle = '#f2f1e9';
        context.font = '700 25px Georgia';
        context.fillText(info[0], 110, y + 44, 840);
      });
    }
    context.fillStyle = '#767d70';
    context.font = '20px monospace';
    context.fillText('PERFIL COMPARTIDO · PRIVACIDAD ELEGIDA POR EL ESCAPISTA', 84, 1186, 912);
    context.fillStyle = '#8bd04c';
    context.font = '800 30px Arial';
    context.fillText('THEVAULTESCAPE.COM', 84, 1244);
    return canvas;
  }

  async function openShareDialog() {
    if (!currentView) return;
    const dialog = document.getElementById('share-dialog');
    document.getElementById('share-status').textContent = '';
    dialog.showModal();
    await drawShareCard(currentView);
  }

  async function nativeShare() {
    if (!currentView) return;
    if (navigator.share) {
      try {
        await navigator.share({ title: `${currentView.displayName} · The Vault Escapist`, text: 'Mi perfil escapista en The Vault', url: currentUrl });
        document.getElementById('share-status').textContent = 'Perfil compartido.';
        return;
      } catch (error) {
        if (error?.name === 'AbortError') return;
      }
    }
    await copyProfileLink();
  }

  function downloadCard() {
    const canvas = document.getElementById('share-card');
    const link = node('a');
    link.href = canvas.toDataURL('image/png');
    link.download = `the-vault-${currentView?.username || 'escapista'}.png`;
    link.click();
    document.getElementById('share-status').textContent = 'Tarjeta descargada en formato 4:5.';
  }

  async function load() {
    currentView = null;
    showState('profile-loading');
    const params = new URLSearchParams(location.search);
    const rawUsername = params.get('u') || '';
    const checked = PublicProfile.validateUsername(rawUsername);
    if (!checked.valid) {
      showState('profile-invalid');
      return;
    }
    try {
      const view = await fetchPublicView(checked.normalized, params.get('demo') === '1');
      if (!PublicProfile.isPublicView(view) || view.username !== checked.normalized) {
        showState('profile-unavailable');
        return;
      }
      if (PublicProfile.forbiddenPublicData(view).length) {
        showState('profile-unavailable');
        return;
      }
      renderPublic(view);
    } catch {
      showState('profile-error');
    }
  }

  document.getElementById('profile-retry')?.addEventListener('click', load);
  document.getElementById('share-close')?.addEventListener('click', () => document.getElementById('share-dialog').close());
  document.getElementById('share-native')?.addEventListener('click', nativeShare);
  document.getElementById('share-copy')?.addEventListener('click', copyProfileLink);
  document.getElementById('share-download')?.addEventListener('click', downloadCard);
  document.getElementById('share-dialog')?.addEventListener('click', event => {
    if (event.target === event.currentTarget) event.currentTarget.close();
  });
  window.VaultPublicProfilePage = Object.freeze({ load, renderPublic, drawShareCard, get currentView() { return currentView; } });
  load();
  if ('serviceWorker' in navigator && location.protocol !== 'file:') navigator.serviceWorker.register('/service-worker.js').catch(() => {});
})();
