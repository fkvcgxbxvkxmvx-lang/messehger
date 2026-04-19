from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sqlite3

app = Flask(__name__)
DB_FILE = "chat.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    # Таблица сообщений
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            username TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица комнат
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            creator TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица участников комнат
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_rooms (
            username TEXT NOT NULL,
            room TEXT NOT NULL,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, room)
        )
    """)
    
    # Таблица времени последнего прочтения
    cur.execute("""
        CREATE TABLE IF NOT EXISTS last_read (
            username TEXT NOT NULL,
            room TEXT NOT NULL,
            last_read_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, room)
        )
    """)
    
    conn.commit()
    conn.close()

def load_messages(room):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT username, text FROM messages WHERE room = ? ORDER BY id", (room,))
    rows = cur.fetchall()
    conn.close()
    return [{"username": row[0], "text": row[1]} for row in rows]

def save_message(room, username, msg):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (room, username, text) VALUES (?, ?, ?)", (room, username, msg))
    conn.commit()
    conn.close()

def clear_room_history(room, username):
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
    cur.execute("INSERT OR IGNORE INTO user_rooms (username, room) VALUES (?, ?)", (creator, room))
    conn.commit()
    conn.close()

def add_user_to_room(username, room):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO user_rooms (username, room) VALUES (?, ?)", (username, room))
    conn.commit()
    conn.close()

def leave_room(username, room):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM user_rooms WHERE username = ? AND room = ?", (username, room))
    conn.commit()
    conn.close()

def delete_room(room, username):
    """Удаляет комнату, если пользователь — создатель"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT creator FROM rooms WHERE room_id = ?", (room,))
    row = cur.fetchone()
    if not row or row[0] != username:
        conn.close()
        return False
    
    cur.execute("DELETE FROM messages WHERE room = ?", (room,))
    cur.execute("DELETE FROM user_rooms WHERE room = ?", (room,))
    cur.execute("DELETE FROM last_read WHERE room = ?", (room,))
    cur.execute("DELETE FROM rooms WHERE room_id = ?", (room,))
    conn.commit()
    conn.close()
    return True

def get_user_rooms(username):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT room FROM user_rooms WHERE username = ? ORDER BY joined_at DESC", (username,))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def update_last_read(username, room):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO last_read (username, room, last_read_time)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(username, room) DO UPDATE SET last_read_time = CURRENT_TIMESTAMP
    """, (username, room))
    conn.commit()
    conn.close()

def get_unread_counts(username, rooms):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    counts = {}
    for room in rooms:
        cur.execute("SELECT last_read_time FROM last_read WHERE username = ? AND room = ?", (username, room))
        row = cur.fetchone()
        last_read = row[0] if row else "1970-01-01 00:00:00"
        
        cur.execute("SELECT COUNT(*) FROM messages WHERE room = ? AND timestamp > ?", (room, last_read))
        count = cur.fetchone()[0]
        counts[room] = count
    conn.close()
    return counts

# Инициализация БД
init_db()

# ========== МАРШРУТЫ ==========
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error"}), 400
    room = data.get("room", "").strip()
    username = data.get("username", "").strip()
    msg = data.get("message", "").strip()
    if not room or not username or not msg:
        return jsonify({"status": "error"}), 400
    if len(msg) > 1000:
        msg = msg[:1000] + "..."
    create_room_if_not_exists(room, username)
    save_message(room, username, msg)
    return jsonify({"status": "ok"})

@app.route("/messages")
def get_messages():
    room = request.args.get("room", "").strip()
    if not room:
        return jsonify([])
    return jsonify(load_messages(room))

@app.route("/clear", methods=["POST"])
def clear_history():
    data = request.get_json()
    room = data.get("room", "").strip()
    username = data.get("username", "").strip()
    if clear_room_history(room, username):
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 403

@app.route("/creator")
def get_creator():
    room = request.args.get("room", "").strip()
    creator = get_room_creator(room)
    return jsonify({"creator": creator})

@app.route("/my_rooms")
def my_rooms():
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify([])
    rooms = get_user_rooms(username)
    counts = get_unread_counts(username, rooms)
    result = [{"name": room, "unread": counts.get(room, 0)} for room in rooms]
    return jsonify(result)

@app.route("/join_room", methods=["POST"])
def join_room():
    data = request.get_json()
    username = data.get("username", "").strip()
    room = data.get("room", "").strip()
    if not username or not room:
        return jsonify({"status": "error"}), 400
    add_user_to_room(username, room)
    return jsonify({"status": "ok"})

@app.route("/leave_room", methods=["POST"])
def leave_room_route():
    data = request.get_json()
    username = data.get("username", "").strip()
    room = data.get("room", "").strip()
    if not username or not room:
        return jsonify({"status": "error"}), 400
    leave_room(username, room)
    return jsonify({"status": "ok"})

@app.route("/delete_room", methods=["POST"])
def delete_room_route():
    data = request.get_json()
    username = data.get("username", "").strip()
    room = data.get("room", "").strip()
    if not username or not room:
        return jsonify({"status": "error"}), 400
    if delete_room(room, username):
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Только создатель может удалить комнату"}), 403

@app.route("/mark_read", methods=["POST"])
def mark_read():
    data = request.get_json()
    username = data.get("username", "").strip()
    room = data.get("room", "").strip()
    if not username or not room:
        return jsonify({"status": "error"}), 400
    update_last_read(username, room)
    return jsonify({"status": "ok"})

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
