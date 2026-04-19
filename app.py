from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sqlite3
import secrets
import string
import json
from pywebpush import webpush, WebPushException

app = Flask(__name__)
DB_FILE = "chat.db"

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            creator TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_rooms (
            username TEXT NOT NULL,
            room TEXT NOT NULL,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, room)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            username TEXT NOT NULL,
            subscription_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    send_notifications(room, username, msg)

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
    # Если комната пуста и пользователь — создатель, удаляем комнату
    cur.execute("SELECT COUNT(*) FROM user_rooms WHERE room = ?", (room,))
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute("SELECT creator FROM rooms WHERE room_id = ?", (room,))
        row = cur.fetchone()
        if row and row[0] == username:
            cur.execute("DELETE FROM messages WHERE room = ?", (room,))
            cur.execute("DELETE FROM rooms WHERE room_id = ?", (room,))
    conn.commit()
    conn.close()

def get_user_rooms(username):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT room FROM user_rooms WHERE username = ? ORDER BY joined_at DESC", (username,))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def save_subscription(room, username, subscription_json):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO subscriptions (room, username, subscription_json) VALUES (?, ?, ?)",
                (room, username, json.dumps(subscription_json)))
    conn.commit()
    conn.close()

def send_notifications(room, sender, message):
    if not VAPID_PRIVATE_KEY:
        return
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT username, subscription_json FROM subscriptions WHERE room = ? AND username != ?", (room, sender))
    rows = cur.fetchall()
    conn.close()
    for username, sub_json in rows:
        try:
            subscription = json.loads(sub_json)
            data = json.dumps({
                "title": f"💬 {room}",
                "body": f"{sender}: {message[:100]}",
                "icon": "/static/icon-192.png",
                "badge": "/static/icon-192.png",
                "tag": room
            })
            webpush(
                subscription_info=subscription,
                data=data,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:admin@example.com"}
            )
        except Exception as e:
            print(f"Notify error: {e}")

init_db()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/vapid_public_key")
def vapid_public_key():
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})

@app.route("/subscribe", methods=["POST"])
def subscribe():
    data = request.get_json()
    room = data.get("room", "").strip()
    username = data.get("username", "").strip()
    subscription = data.get("subscription")
    if room and username and subscription:
        save_subscription(room, username, subscription)
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 400

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
    return jsonify(get_user_rooms(username))

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

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
