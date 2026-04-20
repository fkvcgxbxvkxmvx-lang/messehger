self.addEventListener('install', (event) => {
  console.log('Service Worker установлен');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker активирован');
});

self.addEventListener('fetch', (event) => {
  // Не кешируем, просто пропускаем
});

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'Новое сообщение', body: 'Кто-то написал в чат' };
  const options = {
    body: data.body,
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    tag: data.tag || 'chat'
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});
