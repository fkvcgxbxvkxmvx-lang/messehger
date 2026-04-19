from flask import Flask, render_template, request, jsonify
import os
import psycopg2

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            username TEXT,
            text TEXT
        );
    """)
    conn.commit()
    conn.close()

def load_messages():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("SELECT username, text FROM messages ORDER BY id;")
    rows = cur.fetchall()
    conn.close()
    return [{"username": row[0], "text": row[1]} for row in rows]

def save_message(username, msg):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (username, text) VALUES (%s, %s);", (username, msg))
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
