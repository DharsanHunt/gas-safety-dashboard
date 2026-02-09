from flask import Flask, jsonify, render_template, request
from datetime import datetime
import os
import requests

app = Flask(__name__)

# ================= CONFIG =================
GAS_THRESHOLD = 400
RESET_THRESHOLD = 350

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

# ================= STATE =================
latest_cloud_data = {
    "gas": 0,
    "state": "OFF",
    "time": ""
}

email_sent = False

# ================= EMAIL FUNCTION =================
def send_email_alert(gas):
    print("📧 Sending email via Brevo")

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
    print("📨 Brevo response:", response.status_code, response.text)

    return response.status_code == 201

# ================= ROUTES =================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/data")
def data():
    return jsonify(latest_cloud_data)

@app.route("/update", methods=["POST"])
def update():
    global email_sent

    data = request.json
    gas = int(data["gas"])
    state = data.get("state", "OFF")
    time = data.get("time", datetime.now().strftime("%H:%M:%S"))

    latest_cloud_data.update({
        "gas": gas,
        "state": state,
        "time": time
    })

    print("☁️ UPDATE:", latest_cloud_data)
    print("🔍 email_sent:", email_sent)

    if gas > GAS_THRESHOLD and not email_sent:
        print("🚨 GAS ABOVE THRESHOLD → EMAIL")
        success = send_email_alert(gas)
        if success:
            email_sent = True

    elif gas < RESET_THRESHOLD:
        email_sent = False

    return {"status": "ok"}

# -------- FORCE TEST ROUTE --------
@app.route("/force-email")
def force_email():
    print("🔥 FORCE EMAIL ROUTE HIT")
    send_email_alert(999)
    return "Force email triggered"

# ================= START =================
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
