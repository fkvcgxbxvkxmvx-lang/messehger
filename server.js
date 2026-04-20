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
