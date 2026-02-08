import serial
import sqlite3
from flask import Flask, jsonify, render_template, request
from threading import Thread
from datetime import datetime
import os
import requests

# ---------- ENV DETECTION ----------
IS_CLOUD = "PORT" in os.environ

SERIAL_PORT = "COM8"
BAUD_RATE = 9600
CLOUD_URL = "https://gas-safety-dashboard.onrender.com/update"

app = Flask(__name__)

# ---------- DATABASE ----------
conn = sqlite3.connect("gas_data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS gas_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gas INTEGER,
    state TEXT,
    time TEXT
)
""")
conn.commit()

# ---------- SERIAL READER ----------
def read_serial():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("✅ Connected to", SERIAL_PORT)
    except Exception as e:
        print("❌ Serial error:", e)
        return

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        print("RAW:", line)

        if line.startswith("GAS="):
            try:
                parts = line.split(",")
                gas = int(parts[0].split("=")[1])
                state = parts[1].split("=")[1]
                time_now = datetime.now().strftime("%H:%M:%S")

                # Local DB
                cur.execute(
                    "INSERT INTO gas_log (gas, state, time) VALUES (?, ?, ?)",
                    (gas, state, time_now)
                )
                conn.commit()

                # 🔥 Push to cloud
                requests.post(CLOUD_URL, json={
                    "gas": gas,
                    "state": state,
                    "time": time_now
                }, timeout=2)

            except Exception as e:
                print("❌ Parse error:", e)

# ---------- ROUTES ----------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data")
def data():
    cur.execute(
        "SELECT gas, state, time FROM gas_log ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()

    if row:
        return jsonify({
            "gas": row[0],
            "state": row[1],
            "time": row[2]
        })
    else:
        return jsonify({
            "gas": 0,
            "state": "OFF",
            "time": ""
        })

@app.route("/update", methods=["POST"])
def update():
    data = request.json
    cur.execute(
        "INSERT INTO gas_log (gas, state, time) VALUES (?, ?, ?)",
        (data["gas"], data["state"], data["time"])
    )
    conn.commit()
    return {"status": "ok"}

# ---------- START ----------
if not IS_CLOUD:
    Thread(target=read_serial, daemon=True).start()
else:
    print("☁️ Cloud mode: Serial disabled")

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
