from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sqlite3

# === НАСТРОЙКИ ===
app = Flask(__name__)
DB_FILE = "chat.db"

# === БАЗА ДАННЫХ ===
def init_db():
    """Создаёт таблицу, если её нет"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def load_messages(room):
    """Загружает сообщения комнаты"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, text FROM messages WHERE room = ? ORDER BY id",
        (room,)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"username": row[0], "text": row[1]} for row in rows]

def save_message(room, username, msg):
    """Сохраняет сообщение в базу"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (room, username, text) VALUES (?, ?, ?)",
        (room, username, msg)
    )
    conn.commit()
    conn.close()

# === ИНИЦИАЛИЗАЦИЯ ===
init_db()

# === МАРШРУТЫ ===
@app.route("/")
def home():
    """Главная страница (чат)"""
    return render_template("index.html")

@app.route("/send", methods=["POST"])
def send():
    """Отправка сообщения"""
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Нет данных"}), 400
    
    room = data.get("room", "").strip()
    username = data.get("username", "").strip()
    msg = data.get("message", "").strip()
    
    if not room or not username or not msg:
        return jsonify({"status": "error", "message": "Пустые поля"}), 400
    
    # Ограничение длины (защита от спама)
    if len(msg) > 1000:
        msg = msg[:1000] + "..."
    
    save_message(room, username, msg)
    return jsonify({"status": "ok"})

@app.route("/messages")
def get_messages():
    """Получение сообщений комнаты"""
    room = request.args.get("room", "").strip()
    if not room:
        return jsonify([])
    
    msgs = load_messages(room)
    return jsonify(msgs)

@app.route('/static/<path:filename>')
def static_files(filename):
    """Отдача статических файлов (PWA)"""
    return send_from_directory('static', filename)

# === ЗАПУСК ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
