from flask import Flask, render_template, request, jsonify
import os
import sqlite3

app = Flask(__name__)

DB_FILE = "chat.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            username TEXT,
            text TEXT
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

init_db()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    if data and "room" in data and "username" in data and "message" in data:
        room = data["room"]
        username = data["username"]
        msg = data["message"]
        save_message(room, username, msg)
    return jsonify({"status": "ok"})

@app.route("/messages")
def get_messages():
    room = request.args.get("room", "")
    if not room:
        return jsonify([])
    msgs = load_messages(room)
    return jsonify(msgs)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
