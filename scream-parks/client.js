/* Shared S3A/S3B preview renderer. No Firebase, room-state, or product writes. */
(function () {
  'use strict';
  const mounted = new WeakMap();
  let activeController = null;

  function mount({ root, endpoint, navigation = 'inline', iconUrl, reviewStore = null,
    editorialEndpoint = 'scream-parks/editorial-reviews.json',
    reviewSeasonsEndpoint = 'scream-parks/review-seasons.json' }) {
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
    let historicalReviewSeasons = [];
    let communitySeasonId = '';
    let communityError = '';
    let communityFormOpen = false;
    let communityVisible = 3;
    const detailMediaQuery = window.matchMedia('(max-width:900px)');
    let detailMediaHandler = null;

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

    function renderCommunity() {
      const target = $('community');
      if (!target || !reviewStore) return;
      const state = reviewStore.snapshot();
      if (!state.entry || state.entry.id !== selectedId) return;
      target.replaceChildren(create('h2', 'OPINIONES DE LA COMUNIDAD'));
      const currentSeason = model.entries.find(item => item.id === selectedId)?.seasonId;
      const seasons = [currentSeason, ...historicalReviewSeasons
        .filter(item => item.entityId === selectedId).map(item => item.seasonId)];
      const choices = [...new Set(seasons)].sort().reverse();
      if (choices.length > 1) {
        const label = create('label', 'Edición que quieres consultar');
        const select = create('select');
        for (const season of choices) option(select, season, season.slice(-4));
        select.value = communitySeasonId || currentSeason;
        select.onchange = () => {
          communitySeasonId = select.value;
          communityVisible = 3;
          communityFormOpen = false;
          reviewStore.load({ ...state.entry, seasonId: communitySeasonId }).catch(error => {
            communityError = error.message; renderCommunity();
          });
        };
        label.append(select);
        target.append(label);
      }
      if (state.pending) { target.append(create('p', 'Cargando opiniones…')); return; }
      if (communityError) target.append(create('p', communityError, 'caution'));
      const stats = create('div', undefined, 'sp-community-stats');
      stats.append(create('p', state.count
        ? `Nota global: ${state.global.toFixed(1).replace('.', ',')}/10 · ${state.count} ${state.count === 1 ? 'valoración' : 'valoraciones'}`
        : 'Aún no hay valoraciones para esta edición.', 'sp-community-average'));
      if (state.count) {
        const grid = create('div', undefined, 'sp-community-score-grid');
        for (const [key, label] of window.VaultScreamParkReviews.CATEGORIES)
          grid.append(create('span', `${label}: ${state.categories[key].toFixed(1).replace('.', ',')}/10`));
        stats.append(grid);
      }
      target.append(stats);
      const uid = reviewStore.currentUid?.();
      const own = state.own;
      if (uid && state.writable) {
        const writeButton = create('button', own ? 'EDITAR MI OPINIÓN' : 'ESCRIBIR MI OPINIÓN', 'sp-community-write');
        writeButton.type = 'button';
        writeButton.setAttribute('aria-expanded', String(communityFormOpen));
        writeButton.onclick = () => { communityFormOpen = !communityFormOpen; renderCommunity(); };
        target.append(writeButton);
      }
      if (uid && state.writable && communityFormOpen) {
        const form = create('form', undefined, 'sp-community-form');
        const nameLabel = create('label', 'Nombre público');
        const userName = create('input'); userName.maxLength = 40;
        userName.value = own?.userName === 'Visitante' ? '' : own?.userName || '';
        userName.placeholder = 'Visitante'; nameLabel.append(userName);
        form.append(nameLabel);
        const widgetId = `sp_${state.entry.seasonId}_${uid}`;
        for (const [key, label] of window.VaultScreamParkReviews.CATEGORIES) {
          const row = create('div', undefined, 'sp-community-score-row');
          row.append(create('span', label, 'sp-community-score-label'));
          const control = create('div');
          if (typeof window.reviewStarsHtml === 'function') {
            control.innerHTML = window.reviewStarsHtml(widgetId, key, own?.scores?.[key] || 0, true);
            const stars = control.querySelector('.review-stars');
            stars.tabIndex = 0;
            stars.setAttribute('role', 'slider');
            stars.setAttribute('aria-label', label);
            stars.setAttribute('aria-valuemin', '0.5');
            stars.setAttribute('aria-valuemax', '5');
            stars.setAttribute('aria-valuenow', String(own?.scores?.[key] || 0.5));
            stars.onkeydown = event => {
              if (!['ArrowLeft', 'ArrowDown', 'ArrowRight', 'ArrowUp'].includes(event.key)) return;
              event.preventDefault();
              const next = Math.max(0.5, Math.min(5, (Number(stars.dataset.value) || 0.5)
                + (['ArrowRight', 'ArrowUp'].includes(event.key) ? 0.5 : -0.5)));
              window.setReviewCategoryScore(widgetId, key, next);
              stars.setAttribute('aria-valuenow', String(next));
            };
          } else {
            const select = create('select'); select.dataset.category = key;
            option(select, '', 'Selecciona una puntuación');
            for (let score = 0.5; score <= 5; score += 0.5) option(select, String(score), `${score * 2}/10`);
            select.value = String(own?.scores?.[key] || '');
            control.append(select);
          }
          row.append(control); form.append(row);
        }
        const textLabel = create('label', 'Tu experiencia, sin spoilers');
        const opinion = create('textarea'); opinion.maxLength = 10000; opinion.minLength = 10;
        opinion.required = true; opinion.value = own?.text || ''; textLabel.append(opinion);
        const send = create('button', own ? 'ACTUALIZAR OPINIÓN' : 'PUBLICAR OPINIÓN'); send.type = 'submit';
        const status = create('p', 'Tu opinión aparecerá al guardarse.', 'sp-community-status');
        form.append(textLabel, send, status);
        form.onsubmit = async event => {
          event.preventDefault();
          const scores = Object.fromEntries(window.VaultScreamParkReviews.CATEGORIES.map(([key]) => [key,
            Number(form.querySelector(`[data-category="${key}"]`)?.dataset.value
              || form.querySelector(`select[data-category="${key}"]`)?.value || 0)]));
          send.disabled = true;
          try {
            await reviewStore.save({ scores, userName: userName.value, text: opinion.value });
            communityError = '';
            communityFormOpen = false;
            renderCommunity();
          } catch (error) { status.textContent = error.message; send.disabled = false; }
        };
        target.append(form);
      } else if (!uid || !state.writable) {
        target.append(create('p', uid
          ? 'El envío de opiniones no está disponible en este entorno.'
          : 'Entra con Google para compartir tu opinión. Se publicará al guardarla.'));
        if (!uid && state.writable) {
          const login = create('button', 'ENTRAR CON GOOGLE', 'sp-community-write');
          login.type = 'button'; login.onclick = () => window.signInGoogle?.();
          target.append(login);
        }
      }
      if (own) {
        const remove = create('button', 'ELIMINAR MI OPINIÓN', 'sp-review-delete');
        remove.type = 'button';
        remove.onclick = async () => {
          if (!window.confirm('¿Eliminar tu opinión de esta edición?')) return;
          remove.disabled = true;
          try { await reviewStore.deleteOwn(); communityFormOpen = false; renderCommunity(); }
          catch (error) { communityError = error.message; renderCommunity(); }
        };
        target.append(remove);
      }
      const list = create('div', undefined, 'sp-community-list');
      const rows = Object.entries(state.rows).filter(([, item]) =>
        item && window.VaultScreamParkReviews.aggregate({ one: item }).count === 1).sort((a, b) =>
        Number(b[1].updatedAt || 0) - Number(a[1].updatedAt || 0));
      for (const [authorUid, item] of rows.slice(0, communityVisible)) {
        const article = create('article', undefined, 'sp-community-opinion');
        const date = item.updatedAt ? new Date(item.updatedAt).toLocaleDateString('es-ES') : '';
        const score = window.VaultScreamParkReviews.aggregate({ one: item }).global;
        article.append(create('strong', `${item.userName || 'Visitante'} · ${score.toFixed(1).replace('.', ',')}/10 · ${date}`),
          create('p', item.text));
        const detail = create('p', undefined, 'sp-community-score-details');
        detail.textContent = window.VaultScreamParkReviews.CATEGORIES.map(([key, label]) =>
          `${label}: ${Number(item.scores[key] * 2).toFixed(1).replace('.', ',')}/10`).join(' · ');
        article.append(detail);
        if (state.admin && authorUid !== uid) {
          const remove = create('button', 'RETIRAR OPINIÓN', 'sp-review-delete');
          remove.type = 'button';
          remove.onclick = async () => {
            if (!window.confirm('¿Retirar esta opinión pública?')) return;
            remove.disabled = true;
            try { await reviewStore.removeAsAdmin(authorUid); communityError = ''; }
            catch (error) { communityError = error.message; renderCommunity(); }
          };
          article.append(remove);
        }
        list.append(article);
      }
      target.append(list);
      if (rows.length > communityVisible) {
        const more = create('button', 'VER MÁS', 'sp-community-more');
        more.type = 'button';
        more.onclick = () => { communityVisible += 5; renderCommunity(); };
        target.append(more);
      }
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
      if (selectedId !== id) { communitySeasonId = ''; communityFormOpen = false; communityVisible = 3; }
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
    function visitMediaPanel(entry) {
      const review = editorialFor(entry);
      const photos = Array.isArray(review?.images) ? review.images : [];
      const videos = Array.isArray(review?.videos) ? review.videos : [];
      if (!photos.length && !videos.length) return null;
      const gallery = panel('NUESTRA VISITA EN FOTOS Y VÍDEOS');
      gallery.classList.add('sp-visit-gallery');
      const mediaGrid = create('div', undefined, 'sp-visit-grid');
      const key = `scream-editorial-${entry.seasonId}`;
      window.registerEditorialPhotoGallery?.(key, photos);
      photos.forEach((photo, index) => {
        if (!photo?.src || !photo?.thumbnail) return;
        const link = create('a');
        link.href = photo.src;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.setAttribute('aria-label', `Ampliar foto ${index + 1} de nuestra visita`);
        link.onclick = event => window.openPhotoLightbox?.(event, key, index);
        const image = create('img');
        image.src = photo.thumbnail;
        image.alt = photo.alt || 'Foto de nuestra visita a Horrorland';
        image.loading = 'lazy';
        image.decoding = 'async';
        image.width = 450;
        image.height = 600;
        link.append(image);
        mediaGrid.append(link);
      });
      videos.forEach((item, index) => {
        if (!item?.src || !item?.poster) return;
        const figure = create('figure', undefined, 'sp-visit-video-card');
        const video = create('video', undefined, 'sp-visit-video');
        video.controls = true;
        video.playsInline = true;
        video.preload = 'none';
        video.poster = item.poster;
        video.width = item.width || 464;
        video.height = item.height || 832;
        video.setAttribute('aria-label', item.title || `Vídeo ${index + 1} de nuestra visita`);
        const source = create('source');
        source.src = item.src;
        source.type = 'video/mp4';
        video.append(source);
        figure.append(video, create('figcaption', `▶ ${item.title || `Vídeo ${index + 1} de nuestra visita`}`));
        mediaGrid.append(figure);
      });
      gallery.append(mediaGrid);
      return gallery;
    }
    function detail(entry) {
      const rootNode = $('detail-content');
      rootNode.querySelectorAll('video').forEach(video => video.pause());
      rootNode.replaceChildren();
      const grid = create('div', undefined, 'detail-grid');
      const main = create('div');
      const aside = create('aside');
      const intro = create('div', undefined, 'sp-detail-intro');
      const rest = create('div', undefined, 'sp-detail-rest');
      intro.append(create('div', `${entry.typeLabel} · ${entry.seasonId}`, 'eyebrow'),
        create('h1', entry.name),
        create('p', entry.editorialSynopsis || (s4(entry)
          ? `Temporada ${entry.seasonId.slice(-4)}. Consulta la web del evento antes de planificar la visita.`
          : `Temporada ${entry.seasonId.slice(-4)} confirmada según las evidencias editoriales vigentes. Esta ficha sigue en PREVIEW_ONLY.`), 'lead'));
      main.append(intro);
      const review = editorialBlock(entry);
      if (review) main.append(review);
      rest.append(personalControls(entry));
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
      rest.append(period);
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
      rest.append(context);
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
        rest.append(practical);
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
        rest.append(links);
      }
      main.append(rest);
      const fallback = create('div', undefined, 'fallback');
      if (entry.images?.length) fallback.classList.add('has-cover');
      fallback.append(coverImage(entry));
      aside.append(fallback);
      const visitGallery = visitMediaPanel(entry);
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
      grid.append(main, aside);
      rootNode.append(grid);
      if (visitGallery) rootNode.append(visitGallery);
      if (reviewStore) {
        const community = panel('OPINIONES DE LA COMUNIDAD');
        community.id = 'sp-community';
        rootNode.append(community);
      }
      if (detailMediaHandler) detailMediaQuery.removeEventListener('change', detailMediaHandler);
      detailMediaHandler = () => {
        if (detailMediaQuery.matches) {
          if (visitGallery) main.insertBefore(visitGallery, rest);
          main.insertBefore(fallback, rest);
        } else {
          aside.insertBefore(fallback, aside.firstChild);
          if (visitGallery) rootNode.insertBefore(visitGallery, rootNode.querySelector('#sp-community'));
        }
        aside.hidden = !aside.children.length;
      };
      detailMediaQuery.addEventListener('change', detailMediaHandler);
      detailMediaHandler();
      renderCommunity();
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
          if (reviewStore) reviewStore.load({ ...entry, seasonId: communitySeasonId || entry.seasonId })
            .catch(error => { communityError = error.message; renderCommunity(); });
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
    const controller = { route, renderList, refreshStates, refreshReviews: renderCommunity,
      reloadReviews: () => { const entry = model?.entries.find(item => item.id === selectedId); if (entry) return reviewStore?.load({ ...entry, seasonId: communitySeasonId || entry.seasonId }); },
      open: showDetail, openReview };
    mounted.set(root, controller);
    activeController = controller;
    Promise.all([fetch(endpoint, { cache: 'no-store' }), fetch(editorialEndpoint, { cache: 'no-store' }),
      fetch(reviewSeasonsEndpoint, { cache: 'no-store' })]).then(async ([response, reviewsResponse, seasonsResponse]) => {
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
      if (seasonsResponse.ok) {
        const seasons = await seasonsResponse.json();
        if (seasons.schemaVersion !== 1 || !Array.isArray(seasons.historicalSeasons))
          throw Error('Temporadas históricas no válidas');
        historicalReviewSeasons = seasons.historicalSeasons.filter(item =>
          model.entries.some(entry => entry.id === item.entityId));
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
