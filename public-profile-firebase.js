(function (root, factory) {
  const api = factory(
    typeof module === 'object' && module.exports ? require('./public-profile.js') : root.VaultPublicProfile
  );
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VaultPublicProfileFirebase = api;
})(typeof self !== 'undefined' ? self : this, function (PublicProfile) {
  'use strict';

  if (!PublicProfile) throw new Error('VaultPublicProfile no está disponible.');

  const EMPTY_VISIBILITY = Object.freeze(Object.fromEntries(
    PublicProfile.VISIBILITY_KEYS.map(key => [key, false])
  ));

  function timestamp(api) {
    return Math.max(1, Number(api?.now?.() || Date.now()));
  }

  function normalizeControl(value, uid = '') {
    const source = value && typeof value === 'object' ? value : {};
    return {
      schemaVersion: 1,
      published: source.published === true,
      indexable: false,
      currentUsername: PublicProfile.validateUsername(source.currentUsername || '').valid
        ? PublicProfile.normalizeUsername(source.currentUsername) : '',
      pendingUsername: PublicProfile.validateUsername(source.pendingUsername || '').valid
        ? PublicProfile.normalizeUsername(source.pendingUsername) : '',
      previousUsername: PublicProfile.validateUsername(source.previousUsername || '').valid
        ? PublicProfile.normalizeUsername(source.previousUsername) : '',
      visibility: PublicProfile.visibility(source.visibility || EMPTY_VISIBILITY),
      updatedAt: Math.max(1, Number(source.updatedAt || 1)),
      ...(uid ? { _localOwner: uid } : {})
    };
  }

  function persistedControl(control, overrides = {}, api) {
    const merged = normalizeControl({ ...control, ...overrides });
    delete merged._localOwner;
    merged.updatedAt = timestamp(api);
    return merged;
  }

  async function afterStep(options, step, details = {}) {
    if (typeof options?.afterStep === 'function') await options.afterStep(step, details);
  }

  async function readControl(api, uid) {
    return normalizeControl(await api.get(`publicProfileControls/${uid}`), uid);
  }

  async function ownedReservation(api, uid, username) {
    try {
      const value = await api.get(`publicProfileOwners/${username}`);
      return value?.ownerUid === uid ? value : null;
    } catch {
      return null;
    }
  }

  async function reserveUsername(api, uid, username) {
    const existing = await ownedReservation(api, uid, username);
    if (existing) return existing;
    const now = timestamp(api);
    const candidate = { ownerUid: uid, state: 'reserved', createdAt: now, updatedAt: now };
    try {
      await api.put(`publicProfileOwners/${username}`, candidate);
      return candidate;
    } catch (error) {
      const retryExisting = await ownedReservation(api, uid, username);
      if (retryExisting) return retryExisting;
      const conflict = new Error('Este username ya no está disponible.');
      conflict.code = 'USERNAME_TAKEN';
      conflict.cause = error;
      throw conflict;
    }
  }

  async function setReservationState(api, uid, username, state) {
    const reservation = await ownedReservation(api, uid, username);
    if (!reservation) throw new Error(`No existe una reserva propia para ${username}.`);
    if (reservation.state === state) return reservation;
    const next = { ...reservation, ownerUid: uid, state, updatedAt: timestamp(api) };
    await api.put(`publicProfileOwners/${username}`, next);
    return next;
  }

  async function projection(buildProjection, username, visibility) {
    const view = await buildProjection({ username, visibility: PublicProfile.visibility(visibility) });
    if (!PublicProfile.isPublicView(view) || view.username !== username) {
      throw new Error('La proyección pública generada no es válida.');
    }
    return view;
  }

  async function publishCurrent(api, input, control, options = {}) {
    const checked = PublicProfile.validateUsername(input.username);
    if (!checked.valid) throw new Error(checked.error);
    const username = checked.normalized;
    const visibility = PublicProfile.visibility(input.visibility);
    const shouldPublish = input.published !== false;
    const intent = persistedControl(control, {
      pendingUsername: username,
      visibility,
      published: shouldPublish && control.currentUsername ? control.published : false
    }, api);
    await api.put(`publicProfileControls/${input.uid}`, intent);
    await afterStep(options, 'control-intent', { username });

    await reserveUsername(api, input.uid, username);
    await afterStep(options, 'owner-reserved', { username });

    let view = null;
    if (shouldPublish) {
      view = await projection(input.buildProjection, username, visibility);
      await api.put(`publicProfiles/${username}/view`, view);
      await afterStep(options, 'view-staged', { username });
    } else {
      await api.remove(`publicProfiles/${username}/view`);
      await afterStep(options, 'private-view-removed', { username });
    }

    await setReservationState(api, input.uid, username, 'active');
    await afterStep(options, 'owner-activated', { username });

    const active = persistedControl(intent, {
      published: shouldPublish,
      currentUsername: username,
      pendingUsername: '',
      previousUsername: '',
      visibility
    }, api);
    await api.put(`publicProfileControls/${input.uid}`, active);
    await afterStep(options, 'control-activated', { username });
    if (typeof api.publicReadable === 'function') {
      const readable = await api.publicReadable(username);
      if (readable !== shouldPublish) throw new Error(shouldPublish
        ? 'El perfil no quedó disponible tras publicarlo.'
        : 'El perfil privado seguía siendo legible.');
    }
    await afterStep(options, 'publish-verified', { username, published: shouldPublish });
    return { control: active, view, username };
  }

  async function rename(api, input, control, options = {}) {
    const nextResult = PublicProfile.validateUsername(input.username);
    if (!nextResult.valid) throw new Error(nextResult.error);
    const nextUsername = nextResult.normalized;
    const oldUsername = control.currentUsername === nextUsername
      ? control.previousUsername
      : control.currentUsername;
    if (!oldUsername) return publishCurrent(api, input, control, options);
    const visibility = PublicProfile.visibility(input.visibility);
    const shouldPublish = input.published !== false;

    const intent = persistedControl(control, {
      pendingUsername: nextUsername,
      previousUsername: oldUsername,
      visibility,
      published: shouldPublish ? control.published : false
    }, api);
    await api.put(`publicProfileControls/${input.uid}`, intent);
    await afterStep(options, 'rename-control-intent', { oldUsername, nextUsername });

    await reserveUsername(api, input.uid, nextUsername);
    await afterStep(options, 'rename-owner-reserved', { oldUsername, nextUsername });

    let view = null;
    if (shouldPublish) {
      view = await projection(input.buildProjection, nextUsername, visibility);
      await api.put(`publicProfiles/${nextUsername}/view`, view);
      await afterStep(options, 'rename-view-staged', { oldUsername, nextUsername });
    } else {
      await api.remove(`publicProfiles/${nextUsername}/view`);
      await afterStep(options, 'rename-private-view-removed', { oldUsername, nextUsername });
    }

    await setReservationState(api, input.uid, nextUsername, 'active');
    await afterStep(options, 'rename-owner-activated', { oldUsername, nextUsername });

    const switched = persistedControl(intent, {
      published: shouldPublish,
      currentUsername: nextUsername,
      pendingUsername: nextUsername,
      previousUsername: oldUsername,
      visibility
    }, api);
    await api.put(`publicProfileControls/${input.uid}`, switched);
    await afterStep(options, 'rename-control-switched', { oldUsername, nextUsername });

    if (typeof api.publicReadable === 'function') {
      const [oldReadable, nextReadable] = await Promise.all([
        api.publicReadable(oldUsername), api.publicReadable(nextUsername)
      ]);
      if (oldReadable || nextReadable !== shouldPublish) {
        throw new Error('El cambio de username no dejó una única URL pública coherente.');
      }
    }
    await afterStep(options, 'rename-public-verified', { oldUsername, nextUsername, published: shouldPublish });

    await api.remove(`publicProfiles/${oldUsername}/view`);
    await afterStep(options, 'rename-old-view-removed', { oldUsername, nextUsername });

    await setReservationState(api, input.uid, oldUsername, 'retired');
    await afterStep(options, 'rename-old-owner-retired', { oldUsername, nextUsername });

    const clean = persistedControl(switched, {
      pendingUsername: '',
      previousUsername: ''
    }, api);
    await api.put(`publicProfileControls/${input.uid}`, clean);
    await afterStep(options, 'rename-control-cleaned', { oldUsername, nextUsername });
    return { control: clean, view, username: nextUsername, previousUsername: oldUsername };
  }

  async function save(api, input, options = {}) {
    if (!input?.uid || typeof input.buildProjection !== 'function') throw new Error('Falta el propietario o constructor de proyección.');
    const checked = PublicProfile.validateUsername(input.username);
    if (!checked.valid) throw new Error(checked.error);
    const control = await readControl(api, input.uid);
    const recoveringRename = control.currentUsername === checked.normalized && !!control.previousUsername;
    if ((control.currentUsername && control.currentUsername !== checked.normalized) || recoveringRename) {
      return rename(api, { ...input, username: checked.normalized }, control, options);
    }
    return publishCurrent(api, { ...input, username: checked.normalized }, control, options);
  }

  async function unpublish(api, uid, options = {}) {
    const control = await readControl(api, uid);
    if (!control.currentUsername) return { control, username: '' };
    const disabled = persistedControl(control, { published: false }, api);
    await api.put(`publicProfileControls/${uid}`, disabled);
    await afterStep(options, 'unpublish-control-disabled', { username: control.currentUsername });
    if (typeof api.publicReadable === 'function' && await api.publicReadable(control.currentUsername)) {
      throw new Error('La lectura pública seguía activa tras despublicar.');
    }
    await afterStep(options, 'unpublish-verified-private', { username: control.currentUsername });
    await api.remove(`publicProfiles/${control.currentUsername}/view`);
    await afterStep(options, 'unpublish-view-removed', { username: control.currentUsername });
    return { control: disabled, username: control.currentUsername };
  }

  async function refresh(api, input, options = {}) {
    const control = await readControl(api, input.uid);
    if (!control.published || !control.currentUsername) return { skipped: true, control };
    const view = await projection(input.buildProjection, control.currentUsername, control.visibility);
    await api.put(`publicProfiles/${control.currentUsername}/view`, view);
    await afterStep(options, 'refresh-view-written', { username: control.currentUsername });
    return { skipped: false, control, view, username: control.currentUsername };
  }

  return Object.freeze({
    EMPTY_VISIBILITY,
    normalizeControl,
    readControl,
    reserveUsername,
    save,
    rename,
    unpublish,
    refresh
  });
});
