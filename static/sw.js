/* SchoolMind AI — Service Worker
 * Strategy:
 *   - Static assets (CSS/JS/fonts/icons): cache-first (long cache)
 *   - Everything else: network-first with offline fallback
 *   - Never caches authenticated pages aggressively
 */
const CACHE_NAME = 'schoolmind-v1';
const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg',
  '/static/offline.html'
];

// Install: pre-cache static assets
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(STATIC_ASSETS).catch(function(){
        // Don't fail install if one asset is missing
      });
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(names) {
      return Promise.all(
        names.filter(function(n) { return n !== CACHE_NAME; })
             .map(function(n) { return caches.delete(n); })
      );
    })
  );
  self.clients.claim();
});

// Fetch: different strategies for different URL types
self.addEventListener('fetch', function(event) {
  var req = event.request;

  // Only handle GET
  if (req.method !== 'GET') return;

  var url = new URL(req.url);

  // Same-origin only
  if (url.origin !== location.origin) return;

  // Never cache API or authenticated routes
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/counselor') ||
      url.pathname.startsWith('/student') ||
      url.pathname.startsWith('/journal') ||
      url.pathname.startsWith('/companion') ||
      url.pathname.startsWith('/survey') ||
      url.pathname.startsWith('/set-theme') ||
      url.pathname === '/logout' ||
      url.pathname === '/login' ||
      url.pathname === '/register') {
    return; // let browser handle normally
  }

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then(function(cached) {
        if (cached) return cached;
        return fetch(req).then(function(resp) {
          if (resp && resp.status === 200) {
            var clone = resp.clone();
            caches.open(CACHE_NAME).then(function(c) { c.put(req, clone); });
          }
          return resp;
        }).catch(function() {
          // Offline and not in cache — nothing we can do
        });
      })
    );
    return;
  }

  // Everything else: network-first with offline fallback
  event.respondWith(
    fetch(req).catch(function() {
      return caches.match(req).then(function(cached) {
        if (cached) return cached;
        return caches.match('/static/offline.html');
      });
    })
  );
});
