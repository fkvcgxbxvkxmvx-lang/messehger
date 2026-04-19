self.addEventListener('install', (event) => {
  console.log('Service Worker установлен');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker активирован');
});

self.addEventListener('fetch', (event) => {
  // Пропускаем все запросы, не кешируем
});

self.addEventListener('push', (event) => {
  // Место для будущих уведомлений
  const title = 'Новое сообщение';
  const options = {
    body: 'Кто-то написал в чат',
    icon: '/static/icon-192.png'
  };
  event.waitUntil(self.registration.showNotification(title, options));
});