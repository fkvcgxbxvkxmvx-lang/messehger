from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

CHAT_FILE = "chat.txt"

def load_messages():
    if not os.path.exists(CHAT_FILE):
        return []
    with open(CHAT_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f.readlines()]

def save_message(msg):
    with open(CHAT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

messages = load_messages()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/send", methods=["POST"])
def send():
    data = request.get_json()
    print("ПОЛУЧЕНО:", data)

    if data and "message" in data:
        msg = data["message"]
        messages.append(msg)
        save_message(msg)

    return jsonify({"status": "ok"})

@app.route("/messages")
def get_messages():
    return jsonify(messages)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)