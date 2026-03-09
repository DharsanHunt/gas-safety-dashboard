from flask import Flask, jsonify, render_template, request
from datetime import datetime
import os
import requests

app = Flask(__name__)

# ================= CONFIG =================

GAS_THRESHOLD = 2000
RESET_THRESHOLD = 1800

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

if not BREVO_API_KEY:
    print("⚠ WARNING: BREVO_API_KEY not set")

# ================= STATE =================

latest_cloud_data = {
    "gas": 0,
    "state": "SAFE",
    "buzzer": False,
    "time": ""
}

email_sent = False
mute_requested = False

# ================= EMAIL FUNCTION =================

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
        print(response.text)

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

        print("☁ UPDATE RECEIVED:", latest_cloud_data)
        print("📩 Email sent flag:", email_sent)

        # ===== EMAIL LOGIC =====

        if gas > GAS_THRESHOLD and not email_sent:
            print("🚨 GAS ABOVE THRESHOLD → Sending Email")
            success = send_email_alert(gas)
            if success:
                email_sent = True

        elif gas < RESET_THRESHOLD:
            print("✅ Gas normal → Reset email flag")
            email_sent = False

        response = {"status": "ok", "mute": mute_requested}
        if mute_requested:
            mute_requested = False  # Reset after sending to ESP32
        return jsonify(response)

    except Exception as e:
        print("❌ Update error:", e)
        return jsonify({"error": str(e)}), 400


# -------- MUTE BUZZER ROUTE --------

@app.route("/mute", methods=["POST"])
def mute():
    global mute_requested
    mute_requested = True
    print("🔇 MUTE REQUESTED from dashboard")
    return jsonify({"status": "mute_sent"})


# -------- FORCE TEST ROUTE --------

@app.route("/force-email")
def force_email():
    print("🔥 FORCE EMAIL ROUTE HIT")
    send_email_alert(999)
    return "Force email triggered"


# -------- HEALTH CHECK (Good for Render) --------

@app.route("/health")
def health():
    return "Server Running", 200


# ================= START =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

