const CACHE_VERSION = 'the-vault-v8';
const APP_SHELL_CACHE = `${CACHE_VERSION}-shell`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;

const APP_SHELL = [
  './',
  './index.html',
  './site.webmanifest',
  './images/brand/favicon-round-32.png',
  './images/brand/apple-touch-icon-round.png',
  './images/brand/icon-round-192.png',
  './images/brand/icon-round-512.png',
  './images/brand/the-vault-round-logo.jpg',
  './images/brand/the-vault-wordmark.jpg',
  './images/brand/the-vault-wordmark-transparent.png',
  './images/brand/social-card.png'
];

const DATA_FILES = [
  'data.json',
  'catalog.json',
  'terpeca_awards.json',
  'extra_awards.json',
  'external_ratings.json',
  'review_photos.json',
  'official_videos.json',
  'room_aliases.json',
  'room_locations.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => ![APP_SHELL_CACHE, RUNTIME_CACHE].includes(key))
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

async function networkFirst(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) {
    const cache = await caches.open(RUNTIME_CACHE);
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const path = url.pathname.split('/').pop();
  if (DATA_FILES.includes(path)) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  if (url.pathname.includes('/images/brand/')) {
    event.respondWith(cacheFirst(request));
  }
});
