const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const Database = require('better-sqlite3');
const path = require('path');
const bcrypt = require('bcrypt');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);
const db = new Database('chat.db');

// Админ-пароль (из переменной Railway, по умолчанию 'admin123')
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin123';
const ADMIN_PASSWORD_HASH = bcrypt.hashSync(ADMIN_PASSWORD, 10);

// Раздаём статику из папки public
app.use(express.static('public'));
app.use(express.json());

// ========== БАЗА ДАННЫХ ==========
db.exec(`
  CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,
    username TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS rooms (
    room_id TEXT PRIMARY KEY,
    creator TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS user_rooms (
    username TEXT NOT NULL,
    room TEXT NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (username, room)
  );

  CREATE TABLE IF NOT EXISTS last_read (
    username TEXT NOT NULL,
    room TEXT NOT NULL,
    last_read_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (username, room)
  );
`);

console.log('✅ База данных готова');
// ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
function createRoomIfNotExists(room, creator) {
  const stmt = db.prepare('SELECT room_id FROM rooms WHERE room_id = ?');
  if (!stmt.get(room)) {
    db.prepare('INSERT INTO rooms (room_id, creator) VALUES (?, ?)').run(room, creator);
  }
  db.prepare('INSERT OR IGNORE INTO user_rooms (username, room) VALUES (?, ?)').run(creator, room);
}

function addUserToRoom(username, room) {
  db.prepare('INSERT OR IGNORE INTO user_rooms (username, room) VALUES (?, ?)').run(username, room);
}

function updateLastRead(username, room) {
  db.prepare(`
    INSERT INTO last_read (username, room, last_read_time)
    VALUES (?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(username, room) DO UPDATE SET last_read_time = CURRENT_TIMESTAMP
  `).run(username, room);
}

function getUnreadCounts(username, rooms) {
  const counts = {};
  for (const room of rooms) {
    const row = db.prepare('SELECT last_read_time FROM last_read WHERE username = ? AND room = ?').get(username, room);
    const lastRead = row ? row.last_read_time : '1970-01-01 00:00:00';
    const count = db.prepare(`
      SELECT COUNT(*) as cnt FROM messages
      WHERE room = ? AND timestamp > ?
    `).get(room, lastRead);
    counts[room] = count.cnt;
  }
  return counts;
}

// ========== API МАРШРУТЫ ==========

// Главная страница
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Получить список комнат пользователя
app.get('/my_rooms', (req, res) => {
  const username = req.query.username;
  if (!username) return res.json([]);
  
  const rooms = db.prepare(`
    SELECT room FROM user_rooms WHERE username = ? ORDER BY joined_at DESC
  `).all(username).map(r => r.room);
  
  const counts = getUnreadCounts(username, rooms);
  const result = rooms.map(room => ({ name: room, unread: counts[room] || 0 }));
  res.json(result);
});

// Создатель комнаты
app.get('/creator', (req, res) => {
  const room = req.query.room;
  const row = db.prepare('SELECT creator FROM rooms WHERE room_id = ?').get(room);
  res.json({ creator: row ? row.creator : null });
});

// Отправить сообщение
app.post('/send', (req, res) => {
  const { room, username, message } = req.body;
  if (!room || !username || !message) return res.status(400).json({ error: 'Нет данных' });
  
  const msg = message.length > 1000 ? message.slice(0, 1000) + '...' : message;
  createRoomIfNotExists(room, username);
  db.prepare('INSERT INTO messages (room, username, text) VALUES (?, ?, ?)').run(room, username, msg);
  
  // Отправляем через сокеты
  io.to(room).emit('new_message', { username, text: msg, room });
  
  res.json({ status: 'ok' });
});

// Получить сообщения комнаты
app.get('/messages', (req, res) => {
  const room = req.query.room;
  if (!room) return res.json([]);
  
  const messages = db.prepare(`
    SELECT username, text FROM messages WHERE room = ? ORDER BY id
  `).all(room);
  res.json(messages);
});

// Войти в комнату
app.post('/join_room', (req, res) => {
  const { username, room } = req.body;
  if (!username || !room) return res.status(400).json({ error: 'Нет данных' });
  addUserToRoom(username, room);
  res.json({ status: 'ok' });
});

// Отметить как прочитанное
app.post('/mark_read', (req, res) => {
  const { username, room } = req.body;
  if (!username || !room) return res.status(400).json({ error: 'Нет данных' });
  updateLastRead(username, room);
  res.json({ status: 'ok' });
});

// Покинуть комнату
app.post('/leave_room', (req, res) => {
  const { username, room } = req.body;
  db.prepare('DELETE FROM user_rooms WHERE username = ? AND room = ?').run(username, room);
  res.json({ status: 'ok' });
});

// Очистить историю (только создатель)
app.post('/clear', (req, res) => {
  const { room, username } = req.body;
  const creator = db.prepare('SELECT creator FROM rooms WHERE room_id = ?').get(room);
  if (!creator || creator.creator !== username) {
    return res.status(403).json({ error: 'Только создатель' });
  }
  db.prepare('DELETE FROM messages WHERE room = ?').run(room);
  res.json({ status: 'ok' });
});

// Удалить комнату (создатель или админ)
app.post('/delete_room', (req, res) => {
  const { room, username, isAdmin } = req.body;
  const creator = db.prepare('SELECT creator FROM rooms WHERE room_id = ?').get(room);
  
  if (!isAdmin && (!creator || creator.creator !== username)) {
    return res.status(403).json({ error: 'Нет прав' });
  }
  
  db.prepare('DELETE FROM messages WHERE room = ?').run(room);
  db.prepare('DELETE FROM user_rooms WHERE room = ?').run(room);
  db.prepare('DELETE FROM last_read WHERE room = ?').run(room);
  db.prepare('DELETE FROM rooms WHERE room_id = ?').run(room);
  res.json({ status: 'ok' });
});

// ========== АДМИН-ПАНЕЛЬ ==========
app.get('/admin', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

app.post('/admin/login', (req, res) => {
  const { password } = req.body;
  if (bcrypt.compareSync(password, ADMIN_PASSWORD_HASH)) {
    res.json({ success: true });
  } else {
    res.status(401).json({ error: 'Неверный пароль' });
  }
});

app.get('/admin/stats', (req, res) => {
  const userCount = db.prepare('SELECT COUNT(DISTINCT username) as cnt FROM user_rooms').get().cnt;
  const roomCount = db.prepare('SELECT COUNT(*) as cnt FROM rooms').get().cnt;
  const msgCount = db.prepare('SELECT COUNT(*) as cnt FROM messages').get().cnt;
  res.json({ users: userCount, rooms: roomCount, messages: msgCount });
});

app.get('/admin/rooms', (req, res) => {
  const rooms = db.prepare(`
    SELECT r.room_id, r.creator, COUNT(DISTINCT u.username) as participants
    FROM rooms r
    LEFT JOIN user_rooms u ON r.room_id = u.room
    GROUP BY r.room_id
    ORDER BY r.created_at DESC
  `).all();
  res.json(rooms);
});

app.get('/admin/users', (req, res) => {
  const users = db.prepare(`
    SELECT username, COUNT(DISTINCT room) as rooms, MAX(joined_at) as last_active
    FROM user_rooms
    GROUP BY username
    ORDER BY last_active DESC
  `).all();
  res.json(users);
});

// ========== SOCKET.IO ==========
io.on('connection', (socket) => {
  console.log('🔌 Пользователь подключился');
  
  socket.on('join_room', (room) => {
    socket.join(room);
    console.log(`📌 Вошёл в комнату: ${room}`);
  });
  
  socket.on('leave_room', (room) => {
    socket.leave(room);
  });
});

// ========== ЗАПУСК ==========
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`🚀 Сервер запущен на порту ${PORT}`);
});
