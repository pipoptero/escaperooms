/* Shared S3A/S3B preview renderer. No Firebase, room-state, or product writes. */
(function () {
  'use strict';
  const mounted = new WeakMap();

  function mount({ root, endpoint, navigation = 'inline', iconUrl }) {
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
      if (navigation === 'hash') {
        window.location.hash = id;
      } else {
        selectedId = id;
        route();
      }
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
        create('p', s4(entry)
          ? `Temporada ${entry.seasonId.slice(-4)}. Consulta la web del evento antes de planificar la visita.`
          : `Temporada ${entry.seasonId.slice(-4)} confirmada según las evidencias editoriales vigentes. Esta ficha sigue en PREVIEW_ONLY.`, 'lead'));
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
      if (entry.seasonStatus) fact(context, s4(entry) ? 'Temporada' : 'Estado de temporada · verificado', entry.seasonStatus === 'confirmed' ? 'Confirmada' : entry.seasonStatus);
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
        detail(entry);
        window.scrollTo(0, 0);
      } else if (id && navigation === 'hash') {
        window.location.hash = '';
      }
    }
    for (const id of ['type-filter', 'region-filter', 'province-filter']) $(id).onchange = renderList;
    $('back').onclick = () => {
      if (navigation === 'hash') window.location.hash = '';
      else { selectedId = ''; route(); }
    };
    if (navigation === 'hash') window.addEventListener('hashchange', route);
    const controller = { route, renderList };
    mounted.set(root, controller);
    fetch(endpoint, { cache: 'no-store' }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Preview no disponible');
      const staticCatalog = data.scope === 'scream_parks_catalog_v1';
      const privatePreview = ['private_scream_parks_s3a', 'private_scream_parks_s4'].includes(data.scope);
      if ((!staticCatalog && !privatePreview) || (privatePreview && (!data.previewOnly || data.publishable
        || data.publishableApproved || data.productOperations?.length || data.firebaseOperations?.length))
        || !Array.isArray(data.entries)) throw Error('Datos de Scream Parks no disponibles');
      model = data;
      if (data.scope === 'private_scream_parks_s4' || staticCatalog) {
        const banner = root.closest('#panel-scream-parks')?.querySelector('.sp-private');
        if (banner) banner.textContent = 'VISTA LOCAL · NO PUBLICADA';
        const title = $('explorar')?.querySelector('.section-top h2');
        if (title) title.textContent = 'Experiencias y temporadas';
      }
      choices();
      renderList();
      route();
    }).catch(error => {
      $('error').hidden = false;
      $('error').textContent = error.message;
      $('count').textContent = 'No disponible';
    });
    return controller;
  }

  window.TheVaultScreamParksPreview = Object.freeze({ mount });
})();
