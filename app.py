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
            username TEXT,
            text TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_messages():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT username, text FROM messages ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [{"username": row[0], "text": row[1]} for row in rows]

def save_message(username, msg):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (username, text) VALUES (?, ?)", (username, msg))
    conn.commit()
    conn.close()

init_db()
messages = load_messages()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    if data and "username" in data and "message" in data:
        username = data["username"]
        msg = data["message"]
        messages.append({"username": username, "text": msg})
        save_message(username, msg)
    return jsonify({"status": "ok"})

@app.route("/messages")
def get_messages():
    return jsonify(messages)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
