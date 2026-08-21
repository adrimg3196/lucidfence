const CACHE='lucidfence-web-v2';
const ASSETS=['./web.html','./web-core.js','./web-store.js','./web-app.js','./web-worker.js','./manifest.webmanifest','./lucidfence-icon.svg',
  './design.css',
  './fonts/IBMPlexSans-Regular-Latin1.woff2','./fonts/IBMPlexSans-Medium-Latin1.woff2',
  './fonts/IBMPlexSans-SemiBold-Latin1.woff2','./fonts/IBMPlexSans-Bold-Latin1.woff2'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET'||new URL(event.request.url).origin!==location.origin)return;
  event.respondWith(fetch(event.request).then(response=>{const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(event.request,copy));return response;}).catch(()=>caches.match(event.request).then(hit=>hit||(event.request.mode==='navigate'?caches.match('./web.html'):undefined))));
});
