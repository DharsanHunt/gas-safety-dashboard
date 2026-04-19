from flask import Flask, jsonify, render_template, request
from datetime import datetime
import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# ================= CONFIG =================

GAS_THRESHOLD = 2000
RESET_THRESHOLD = 1800

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

DATABASE_URL = os.environ.get("DATABASE_URL")

if not BREVO_API_KEY:
    print("⚠ WARNING: BREVO_API_KEY not set")

if not DATABASE_URL:
    print("⚠ WARNING: DATABASE_URL not set — database features disabled")

# ================= DATABASE =================

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    if not DATABASE_URL:
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gas_readings (
                id SERIAL PRIMARY KEY,
                gas INTEGER NOT NULL,
                state VARCHAR(20) NOT NULL,
                buzzer BOOLEAN NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized")
    except Exception as e:
        print("❌ DB Init Error:", e)

def save_reading(gas, state, buzzer):
    if not DATABASE_URL:
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO gas_readings (gas, state, buzzer) VALUES (%s, %s, %s)",
            (gas, state, buzzer)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("❌ DB Save Error:", e)

def get_latest_readings(limit=50):
    if not DATABASE_URL:
        return []
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT * FROM gas_readings ORDER BY timestamp DESC LIMIT %s",
            (limit,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "gas": row["gas"],
                "state": row["state"],
                "buzzer": row["buzzer"],
                "timestamp": row["timestamp"].strftime("%d-%m-%Y %H:%M:%S")
            })
        return result
    except Exception as e:
        print("❌ DB Fetch Error:", e)
        return []

def get_stats():
    if not DATABASE_URL:
        return {}
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                COUNT(*) AS total_readings,
                MAX(gas) AS max_gas,
                MIN(gas) AS min_gas,
                ROUND(AVG(gas)) AS avg_gas,
                COUNT(*) FILTER (WHERE state = 'ACTIVE') AS danger_count,
                MIN(timestamp) AS first_reading,
                MAX(timestamp) AS last_reading
            FROM gas_readings
        """)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return {
            "total_readings": row["total_readings"],
            "max_gas": row["max_gas"],
            "min_gas": row["min_gas"],
            "avg_gas": int(row["avg_gas"]) if row["avg_gas"] else 0,
            "danger_count": row["danger_count"],
            "first_reading": row["first_reading"].strftime("%d-%m-%Y %H:%M:%S") if row["first_reading"] else None,
            "last_reading": row["last_reading"].strftime("%d-%m-%Y %H:%M:%S") if row["last_reading"] else None,
        }
    except Exception as e:
        print("❌ DB Stats Error:", e)
        return {}

# ================= STATE =================

latest_cloud_data = {
    "gas": 0,
    "state": "SAFE",
    "buzzer": False,
    "time": ""
}

email_sent = False
mute_requested = False

# ================= EMAIL =================

def send_email_alert(gas):
    try:
        print("📧 Sending email via Brevo...")
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        payload = {
            "sender": {"email": EMAIL_SENDER, "name": "Gas Safety System"},
            "to": [{"email": EMAIL_RECEIVER}],
            "subject": "🚨 Gas Leak Alert",
            "htmlContent": f"""
            <h2>🚨 GAS LEAK ALERT 🚨</h2>
            <p><b>Gas Level:</b> {gas}</p>
            <p><b>Threshold:</b> {GAS_THRESHOLD}</p>
            <p><b>Time:</b> {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
            <p>Please take immediate action.</p>
            """
        }
        response = requests.post(url, json=payload, headers=headers)
        print("📨 Brevo response:", response.status_code)
        return response.status_code == 201
    except Exception as e:
        print("❌ Email Error:", e)
        return False

# ================= ROUTES =================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data")
def data():
    return jsonify(latest_cloud_data)

@app.route("/update", methods=["POST"])
def update():
    global email_sent, mute_requested
    try:
        data = request.get_json()
        gas = int(data.get("gas", 0))
        state = data.get("state", "SAFE")
        buzzer = data.get("buzzer", False)
        now_time = datetime.now().strftime("%H:%M:%S")
        latest_cloud_data.update({
            "gas": gas,
            "state": state,
            "buzzer": buzzer,
            "time": now_time
        })
        save_reading(gas, state, buzzer)
        print("☁ UPDATE RECEIVED:", latest_cloud_data)
        if gas > GAS_THRESHOLD and not email_sent:
            print("🚨 GAS ABOVE THRESHOLD → Sending Email")
            success = send_email_alert(gas)
            if success:
                email_sent = True
        elif gas < RESET_THRESHOLD:
            email_sent = False
        response = {"status": "ok", "mute": mute_requested}
        if mute_requested:
            mute_requested = False
        return jsonify(response)
    except Exception as e:
        print("❌ Update error:", e)
        return jsonify({"error": str(e)}), 400

@app.route("/history")
def history():
    limit = request.args.get("limit", 50, type=int)
    readings = get_latest_readings(limit)
    return jsonify(readings)

@app.route("/stats")
def stats():
    return jsonify(get_stats())

@app.route("/mute", methods=["POST"])
def mute():
    global mute_requested
    mute_requested = True
    print("🔇 MUTE REQUESTED from dashboard")
    return jsonify({"status": "mute_sent"})

@app.route("/force-email")
def force_email():
    print("🔥 FORCE EMAIL ROUTE HIT")
    send_email_alert(999)
    return "Force email triggered"

@app.route("/health")
def health():
    return "Server Running", 200

# ================= START =================

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
