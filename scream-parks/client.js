/* Shared S3A/S3B preview renderer. No Firebase, room-state, or product writes. */
(function () {
  'use strict';
  const mounted = new WeakMap();
  let activeController = null;

  function mount({ root, endpoint, navigation = 'inline', iconUrl,
    editorialEndpoint = 'scream-parks/editorial-reviews.json' }) {
    if (!root || !endpoint || !iconUrl) throw new Error('Scream Parks preview misconfigured');
    if (mounted.has(root)) return mounted.get(root);
    // S3B prefixes IDs to avoid colliding with the product's detail modal.
    const $ = id => root.querySelector('#sp-' + id) || root.querySelector('#' + id);
    const create = (tag, value, className) => {
      const el = document.createElement(tag);
      if (value !== undefined) el.textContent = String(value);
      if (className) el.className = className;
      return el;
    };
    const fmtDay = value => {
      if (!value) return '';
      const [year, month, day] = value.split('-');
      return `${day}/${month}/${year}`;
    };
    const verified = (entry, field) => !entry.fieldSources || entry.fieldSources[field] === 'VERIFIED_S2';
    const sourceNote = (entry, field) => verified(entry, field) ? 'Verificado' : 'Dato del Excel · pendiente de verificar';
    const s4 = entry => !!entry.fieldSources || model?.scope === 'scream_parks_catalog_v1';
    const safeExternalUrl = value => {
      if (typeof value !== 'string') return null;
      try {
        const url = new URL(value);
        return url.protocol === 'https:' && !url.username && !url.password ? url.href : null;
      } catch { return null; }
    };
    const coverImage = (entry, className = '') => {
      const source = entry.images?.[0];
      const img = create('img');
      img.src = source || iconUrl;
      img.alt = source ? `Portada de ${entry.name}` : '';
      img.loading = 'lazy';
      if (className) img.className = className;
      if (source) img.onerror = () => {
        if (!img.isConnected) return;
        img.onerror = null;
        img.src = iconUrl;
        img.alt = '';
        img.parentElement?.classList.remove('has-cover');
      };
      return img;
    };
    let model = null;
    let selectedId = '';
    let reviewMode = false;
    let editorialReviews = [];

    function editorialFor(entry) {
      return editorialReviews.find(review => review.entityId === entry.id && review.seasonId === entry.seasonId);
    }

    function reviewDocument(entry, review) {
      const section = create('article', undefined, 'sp-editorial-full');
      const back = create('button', `← Volver a ${entry.name}`, 'back');
      back.type = 'button';
      back.onclick = () => {
        reviewMode = false;
        window.location.hash = `scream-park/${entry.id}`;
        route();
      };
      section.append(back, create('div', `${entry.name} · edición ${entry.seasonId.slice(-4)}`, 'eyebrow'),
        create('h1', review.title), create('p', review.status === 'DRAFT' ? 'BORRADOR PRIVADO · NO PUBLICADO' : 'REVIEW THE VAULT', 'sp-review-label'));
      const body = create('div', undefined, 'sp-editorial-body');
      // The shared editorial renderer escapes source text before adding markup.
      body.innerHTML = window.TheVaultEditorialReview.renderEditorialReview(review.body);
      section.append(body);
      return section;
    }

    function editorialBlock(entry) {
      const review = editorialFor(entry);
      if (!review || !window.TheVaultEditorialReview) return null;
      const section = panel('REVIEW THE VAULT');
      section.classList.add('sp-editorial-preview');
      section.append(create('h3', review.title));
      if (review.status === 'DRAFT') section.append(create('p', 'Borrador privado · no publicado', 'sp-review-label'));
      const excerpt = window.TheVaultEditorialReview.excerptEditorialReview(review.body, 720);
      const body = create('div', undefined, 'sp-editorial-body');
      body.innerHTML = window.TheVaultEditorialReview.renderEditorialReview(excerpt.text);
      section.append(body);
      const button = create('button', 'LEER REVIEW COMPLETA');
      button.type = 'button';
      button.onclick = () => openReview(entry.seasonId);
      section.append(button);
      return section;
    }

    function openReview(seasonId) {
      const entry = model?.entries.find(item => item.seasonId === seasonId);
      if (!entry || !editorialFor(entry)) return false;
      selectedId = entry.id;
      if (editorialFor(entry).status === 'PUBLISHED' && window.openScreamEditorialReview) {
        reviewMode = false;
        if (root.closest('#panel-scream-parks')?.style.display !== 'none') route();
        window.openScreamEditorialReview(seasonId);
        return true;
      }
      reviewMode = true;
      window.location.hash = `scream-park-review/${seasonId}`;
      route();
      return true;
    }

    function option(select, value, label) {
      const item = create('option', label);
      item.value = value;
      select.append(item);
    }
    function choices() {
      for (const [id, key] of [['region-filter', 'region'], ['province-filter', 'province']]) {
        const select = $(id);
        select.length = 1;
        const values = [...new Set(model.entries.map(entry => entry[key]).filter(Boolean))]
          .sort((a, b) => a.localeCompare(b, 'es'));
        for (const value of values) option(select, value, value);
        if (model.entries.some(entry => !entry[key])) option(select, 'unverified', 'Sin dato de ubicación');
      }
    }
    function selected(entry, id, key) {
      const value = $(id).value;
      return value === 'all' || (value === 'unverified' && !entry[key]) || value === entry[key];
    }
    function showDetail(id) {
      reviewMode = false;
      if (navigation === 'hash') {
        window.location.hash = id;
      } else {
        selectedId = id;
        route();
      }
    }
    function personalControls(entry, compact = false) {
      const store = window.VaultScreamParkStates;
      const section = create('section', undefined, compact ? 'sp-personal compact' : 'sp-personal');
      if (!store?.authenticated) {
        if (!compact) section.append(create('p', 'Entra con Google para guardar este parque y su edición en tus listas.', 'sp-personal-hint'));
        return section;
      }
      const state = store.current(entry);
      if (!compact) section.append(create('h2', `Mi edición ${entry.seasonId.slice(-4)}`));
      const actions = create('div', undefined, 'sp-personal-actions');
      for (const [action, label, activeLabel] of [
        ['done', 'Hecho', '✓ Hecho'], ['pending', 'Pendiente', '✓ Pendiente'],
        ['favorite', 'Favorito', '♥ Favorito']
      ]) {
        const button = create('button', state[action] ? activeLabel : label, `sp-state-button ${action}${state[action] ? ' active' : ''}`);
        button.type = 'button';
        button.setAttribute('aria-pressed', String(state[action]));
        button.setAttribute('aria-label', `${label}: ${entry.name}${action === 'favorite' ? '' : `, edición ${entry.seasonId.slice(-4)}`}`);
        button.onclick = async () => {
          button.disabled = true;
          status.textContent = 'Guardando…';
          try { await store.transition(entry, action); }
          catch (error) {
            button.disabled = false;
            status.textContent = `No se pudo guardar. ${error.message}`;
          }
        };
        actions.append(button);
      }
      const status = create('span', '', 'sp-personal-status');
      status.setAttribute('role', 'status');
      section.append(actions, status);
      return section;
    }
    function card(entry) {
      const article = create('article', undefined, 'card');
      article.dataset.id = entry.id;
      const art = create('div', undefined, 'card-art');
      if (entry.images?.length) art.classList.add('has-cover');
      art.append(coverImage(entry));
      const body = create('div', undefined, 'card-body');
      body.append(create('div', entry.typeLabel, 'kicker'), create('h3', entry.name));
      const location = [entry.city, entry.province || entry.region, entry.country].filter(Boolean).join(' · ');
      if (location) body.append(create('p', s4(entry) ? location : `${location} · ${sourceNote(entry, 'entity.location.city')}`, 'meta'));
      if (entry.period.start && entry.period.end) body.append(create('p',
        `${s4(entry) ? 'Fechas orientativas' : !entry.fieldSources || entry.period.source === 'VERIFIED_S2' ? 'Periodo verificado' : 'Periodo indicado en Excel · pendiente de verificar'}: ${fmtDay(entry.period.start)} – ${fmtDay(entry.period.end)}. No implica apertura diaria.`, 'meta'));
      if (entry.editorialState === 'BLOCKED' || entry.availabilityNote) body.append(create('p', entry.availabilityNote || 'Temporada por confirmar', 'caution'));
      const bottom = create('div', undefined, 'bottom');
      const button = create('button', s4(entry) ? 'VER FICHA' : 'VER FICHA PRIVADA');
      button.type = 'button';
      button.onclick = () => showDetail(entry.id);
      bottom.append(button);
      if (window.VaultScreamParkStates?.authenticated) bottom.append(personalControls(entry, true));
      body.append(bottom);
      article.append(art, body);
      return article;
    }
    function renderList() {
      const entries = model.entries.filter(entry => selected(entry, 'type-filter', 'type')
        && selected(entry, 'region-filter', 'region')
        && selected(entry, 'province-filter', 'province'));
      $('cards').replaceChildren(...entries.map(card));
      if (!entries.length) $('cards').append(create('p', 'No hay fichas para esta combinación de filtros.', 'empty'));
      $('count').textContent = s4(model.entries[0])
        ? `${entries.length} de ${model.entries.length} fichas`
        : `${entries.length} de ${model.entries.length} fichas · PREVIEW_ONLY`;
    }
    function panel(title) {
      const node = create('section', undefined, 'detail-panel');
      node.append(create('h2', title));
      return node;
    }
    function fact(rootNode, label, value) {
      const row = create('div', undefined, 'fact');
      row.append(create('span', label), create('strong', value));
      rootNode.append(row);
    }
    function detail(entry) {
      const rootNode = $('detail-content');
      rootNode.replaceChildren();
      const grid = create('div', undefined, 'detail-grid');
      const main = create('div');
      const aside = create('aside');
      main.append(create('div', `${entry.typeLabel} · ${entry.seasonId}`, 'eyebrow'),
        create('h1', entry.name),
        create('p', entry.editorialSynopsis || (s4(entry)
          ? `Temporada ${entry.seasonId.slice(-4)}. Consulta la web del evento antes de planificar la visita.`
          : `Temporada ${entry.seasonId.slice(-4)} confirmada según las evidencias editoriales vigentes. Esta ficha sigue en PREVIEW_ONLY.`), 'lead'));
      main.append(personalControls(entry));
      const review = editorialBlock(entry);
      if (review) main.append(review);
      const period = panel('Temporada y sesiones');
      if (entry.period.start && entry.period.end) fact(period,
        s4(entry) ? 'Fechas orientativas' : !entry.fieldSources || entry.period.source === 'VERIFIED_S2' ? 'Periodo verificado' : 'Periodo del Excel · sin verificar',
        `${fmtDay(entry.period.start)} – ${fmtDay(entry.period.end)}`);
      else period.append(create('p', 'No consta un periodo completo.', 'caution'));
      period.append(create('p', s4(entry)
        ? 'Este intervalo no implica apertura diaria. Consulta el calendario del evento.'
        : 'El periodo no significa apertura diaria. Solo las fechas de sesión expresamente verificadas figuran a continuación.', 'caution'));
      if (entry.sessionDates?.length) {
        const list = create('ul', undefined, 'days');
        for (const day of entry.sessionDates) list.append(create('li', fmtDay(day)));
        period.append(list);
      } else {
        period.append(create('p', s4(entry)
          ? 'Consulta los días de apertura en la web del evento antes de planificar la visita.'
          : 'No constan sesiones individuales verificadas. Consulta la web oficial antes de planificar la visita.', 'caution'));
      }
      main.append(period);
      const context = panel('Información de la ficha');
      if (entry.operator) fact(context, s4(entry) ? 'Organiza' : 'Organiza · verificado', entry.operator);
      const place = [entry.city, entry.province || entry.region, entry.country].filter(Boolean).join(' · ');
      if (place) fact(context, s4(entry) ? 'Zona indicada' : `Ubicación · ${sourceNote(entry, 'entity.location.city')}`, place);
      if (entry.seasonStatus) fact(context, s4(entry) ? 'Temporada' : 'Estado de temporada · verificado', entry.seasonStatus === 'confirmed' ? 'Confirmada' : entry.seasonStatus === 'POSTPONED_2026' ? 'Edición 2026 aplazada' : entry.seasonStatus);
      else fact(context, s4(entry) ? 'Temporada' : 'Estado editorial', s4(entry) ? 'Por confirmar' : entry.editorialState === 'BLOCKED' ? 'Bloqueado' : 'Pendiente de verificar');
      if (entry.hours) fact(context, s4(entry) ? 'Horario orientativo' : 'Horario · verificado', entry.hours);
      else if (!s4(entry)) context.append(create('p', 'Horario no verificado; consulta la web oficial.', 'caution'));
      if (entry.attractions?.length) fact(context,
        s4(entry) ? 'Experiencias indicadas' : `Experiencias · ${sourceNote(entry, 'season.attractions')}`,
        Array.isArray(entry.attractions) ? entry.attractions.join(' · ') : entry.attractions);
      if (entry.warnings?.length) fact(context,
        s4(entry) ? 'Información para visitantes' : `Advertencias · ${sourceNote(entry, 'season.warnings')}`,
        Array.isArray(entry.warnings) ? entry.warnings.join(' · ') : entry.warnings);
      main.append(context);
      if (entry.practical && Object.keys(entry.practical).length) {
        const practical = panel('Datos prácticos');
        const labels = {
          food: 'Restauración', openingHours: 'Horario de apertura', parking: 'Aparcamiento',
          ticketOptions: 'Entradas y modalidades', venue: 'Recinto', accessAddress: 'Acceso indicado',
          ageGuidance: 'Edad recomendada', minimumAge: 'Restricción de edad',
          contactEmail: 'Correo de contacto', contactPhone: 'Teléfono',
          sessionDatesPartial: 'Sesiones confirmadas parcialmente', locationApprox: 'Ubicación aproximada'
        };
        for (const [key, value] of Object.entries(entry.practical)) {
          if (!labels[key] || value == null || value === '') continue;
          fact(practical, labels[key], Array.isArray(value) ? value.map(fmtDay).join(' · ') : value);
        }
        main.append(practical);
      }
      const officialUrl = safeExternalUrl(entry.officialUrl);
      const bookingUrl = safeExternalUrl(entry.bookingUrl);
      if (officialUrl || bookingUrl || !s4(entry)) {
        const links = panel(s4(entry) ? 'WEB OFICIAL' : 'Fuente oficial');
        const stack = create('div', undefined, 'link-stack');
        if (officialUrl) {
          const official = create('a', s4(entry) ? 'VISITAR WEB' : verified(entry, 'entity.officialUrl') ? 'ABRIR WEB OFICIAL' : 'ABRIR ENLACE DEL EXCEL', 'secondary');
          official.href = officialUrl;
          official.target = '_blank';
          official.rel = 'noopener noreferrer';
          stack.append(official);
        }
        if (bookingUrl) {
          const booking = create('a', 'RESERVA OFICIAL', 'secondary');
          booking.href = bookingUrl;
          booking.target = '_blank';
          booking.rel = 'noopener noreferrer';
          stack.append(booking);
        }
        links.append(stack);
        if (!s4(entry)) {
          if (!officialUrl) links.append(create('p', 'Sin enlace oficial disponible en la ficha.', 'caution'));
          else if (!verified(entry, 'entity.officialUrl')) links.append(create('p', 'Enlace procedente del Excel, pendiente de verificar.', 'caution'));
          if (!bookingUrl) links.append(create('p', 'No hay enlace de reserva aprobado para esta ficha.', 'caution'));
        }
        main.append(links);
      }
      const fallback = create('div', undefined, 'fallback');
      if (entry.images?.length) fallback.classList.add('has-cover');
      fallback.append(coverImage(entry));
      aside.append(fallback);
      if (entry.images?.length > 1) {
        const gallery = create('div', undefined, 'sp-gallery');
        for (const source of entry.images.slice(1)) {
          const photo = create('img');
          photo.src = source;
          photo.alt = `Imagen adicional de ${entry.name}`;
          photo.loading = 'lazy';
          photo.onerror = () => { if (photo.isConnected) photo.remove(); };
          gallery.append(photo);
        }
        aside.append(gallery);
      }
      const officialVideo = entry.officialVideo?.embedUrl;
      if (entry.officialVideo?.provider === 'tiktok'
          && /^https:\/\/www\.tiktok\.com\/player\/v1\/[0-9]+$/.test(officialVideo || '')) {
        const videoPanel = panel('Vídeo oficial');
        const frame = create('iframe');
        frame.className = 'sp-official-video';
        frame.src = officialVideo;
        frame.title = `Vídeo oficial de ${entry.name}`;
        frame.loading = 'lazy';
        frame.allow = 'fullscreen; picture-in-picture';
        frame.referrerPolicy = 'strict-origin-when-cross-origin';
        videoPanel.append(frame);
        aside.append(videoPanel);
      }
      const sidebar = panel('Antes de ir');
      sidebar.append(create('p', s4(entry)
        ? 'Consulta disponibilidad, precios y condiciones en la web del evento antes de ir.'
        : 'Esta es una vista privada para evaluación. No ofrece disponibilidad ni reserva desde The Vault.'));
      if (!s4(entry)) {
        if (entry.priceOffers?.length) sidebar.append(create('p', 'Hay precios verificados; consulta condiciones y modalidad en la fuente oficial antes de comprar.', 'caution'));
        else sidebar.append(create('p', 'Precio no verificado para esta ficha.', 'caution'));
      }
      aside.append(sidebar);
      grid.append(main, aside);
      rootNode.append(grid);
    }
    function route() {
      if (!model) return;
      let id = selectedId;
      if (navigation === 'hash') {
        try { id = decodeURIComponent(window.location.hash.slice(1)); }
        catch { id = ''; }
      }
      const entry = model.entries.find(item => item.id === id);
      $('landing').hidden = !!entry;
      $('detail').hidden = !entry;
      if (entry) {
        if (reviewMode && editorialFor(entry)) {
          $('detail-content').replaceChildren(reviewDocument(entry, editorialFor(entry)));
        } else {
          reviewMode = false;
          detail(entry);
        }
        window.scrollTo(0, 0);
      } else if (id && navigation === 'hash') {
        window.location.hash = '';
      }
    }
    for (const id of ['type-filter', 'region-filter', 'province-filter']) $(id).onchange = renderList;
    $('back').onclick = () => {
      reviewMode = false;
      if (navigation === 'hash') window.location.hash = '';
      else { selectedId = ''; route(); }
    };
    if (navigation === 'hash') window.addEventListener('hashchange', route);
    function refreshStates() {
      if (!model) return;
      renderList();
      const entry = model.entries.find(item => item.id === selectedId);
      if (entry) detail(entry);
    }
    const controller = { route, renderList, refreshStates, open: showDetail, openReview };
    mounted.set(root, controller);
    activeController = controller;
    Promise.all([fetch(endpoint, { cache: 'no-store' }), fetch(editorialEndpoint, { cache: 'no-store' })
    ]).then(async ([response, reviewsResponse]) => {
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Preview no disponible');
      const staticCatalog = data.scope === 'scream_parks_catalog_v1';
      const privatePreview = ['private_scream_parks_s3a', 'private_scream_parks_s4'].includes(data.scope);
      if ((!staticCatalog && !privatePreview) || (privatePreview && (!data.previewOnly || data.publishable
        || data.publishableApproved || data.productOperations?.length || data.firebaseOperations?.length))
        || !Array.isArray(data.entries)) throw Error('Datos de Scream Parks no disponibles');
      model = data;
      if (reviewsResponse.ok) {
        const registry = await reviewsResponse.json();
        if (registry.schemaVersion !== 1 || !Array.isArray(registry.reviews)) throw Error('Registro editorial no válido');
        editorialReviews = registry.reviews.filter(review =>
          review.status === 'PUBLISHED' || (registry.previewOnly === true && review.status === 'DRAFT'));
      }
      if (staticCatalog && window.VaultScreamParkStates) window.VaultScreamParkStates.setEntries(data.entries);
      if (data.scope === 'private_scream_parks_s4' || staticCatalog) {
        const banner = root.closest('#panel-scream-parks')?.querySelector('.sp-private');
        if (banner) banner.textContent = 'VISTA LOCAL · NO PUBLICADA';
        const title = $('explorar')?.querySelector('.section-top h2');
        if (title) title.textContent = 'Experiencias y temporadas';
      }
      choices();
      renderList();
      const reviewLink = window.location.hash.match(/^#scream-park-review\/([a-z0-9-]+)$/);
      const parkLink = window.location.hash.match(/^#scream-park\/([a-z0-9-]+)$/);
      if (parkLink) selectedId = parkLink[1];
      if (!reviewLink || !openReview(reviewLink[1])) route();
    }).catch(error => {
      $('error').hidden = false;
      $('error').textContent = error.message;
      $('count').textContent = 'No disponible';
    });
    return controller;
  }

  window.TheVaultScreamParksPreview = Object.freeze({ mount, get current() { return activeController; } });
})();
