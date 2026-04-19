from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sqlite3
import secrets
import string

# === НАСТРОЙКИ ===
app = Flask(__name__)
DB_FILE = "chat.db"

# === БАЗА ДАННЫХ ===
def init_db():
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
    # Таблица для мета-данных комнат (создатель, пароль, настройки)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            creator TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def load_messages(room):
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
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (room, username, text) VALUES (?, ?, ?)",
        (room, username, msg)
    )
    conn.commit()
    conn.close()

def clear_room_history(room, username):
    """Очищает историю, если username совпадает с создателем комнаты"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT creator FROM rooms WHERE room_id = ?", (room,))
    row = cur.fetchone()
    if row and row[0] == username:
        cur.execute("DELETE FROM messages WHERE room = ?", (room,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_room_creator(room):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT creator FROM rooms WHERE room_id = ?", (room,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def create_room_if_not_exists(room, creator):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT room_id FROM rooms WHERE room_id = ?", (room,))
    if not cur.fetchone():
        cur.execute("INSERT INTO rooms (room_id, creator) VALUES (?, ?)", (room, creator))
        conn.commit()
    conn.close()

# === ГЕНЕРАЦИЯ СЛУЧАЙНОГО ID (для приватных ссылок) ===
def generate_room_id(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# === ИНИЦИАЛИЗАЦИЯ ===
init_db()

# === МАРШРУТЫ ===
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Нет данных"}), 400
    
    room = data.get("room", "").strip()
    username = data.get("username", "").strip()
    msg = data.get("message", "").strip()
    
    if not room or not username or not msg:
        return jsonify({"status": "error", "message": "Пустые поля"}), 400
    
    if len(msg) > 1000:
        msg = msg[:1000] + "..."
    
    # Автоматически создаём комнату, если её нет (первый вошедший — создатель)
    create_room_if_not_exists(room, username)
    
    save_message(room, username, msg)
    return jsonify({"status": "ok"})

@app.route("/messages")
def get_messages():
    room = request.args.get("room", "").strip()
    if not room:
        return jsonify([])
    msgs = load_messages(room)
    return jsonify(msgs)

@app.route("/clear", methods=["POST"])
def clear_history():
    data = request.get_json()
    room = data.get("room", "").strip()
    username = data.get("username", "").strip()
    
    if clear_room_history(room, username):
        return jsonify({"status": "ok", "message": "История очищена"})
    return jsonify({"status": "error", "message": "Только создатель может очистить историю"}), 403

@app.route("/creator")
def get_creator():
    room = request.args.get("room", "").strip()
    creator = get_room_creator(room)
    return jsonify({"creator": creator})

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# === ЗАПУСК ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
