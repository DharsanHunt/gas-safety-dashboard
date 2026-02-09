from flask import Flask, jsonify, render_template, request
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

# ---------------- CONFIG ----------------
GAS_THRESHOLD = 400
RESET_THRESHOLD = 350   # hysteresis (important)

EMAIL_SENDER = "yourgmail@gmail.com"
EMAIL_PASSWORD = "YOUR_NEW_APP_PASSWORD"
EMAIL_RECEIVER = "receiver@gmail.com"

# ---------------- LIVE STATE ----------------
latest_cloud_data = {
    "gas": 0,
    "state": "OFF",
    "time": ""
}

email_sent = False

# ---------------- EMAIL FUNCTION ----------------
def send_email_alert(gas):
    print("📧 send_email_alert() called")

    body = f"""
🚨 GAS LEAK ALERT 🚨

Gas level detected: {gas}
Threshold exceeded: {GAS_THRESHOLD}

Time: {datetime.now().strftime("%d-%m-%Y %H:%M:%S")}

Please take immediate action.
"""

    msg = MIMEText(body)
    msg["Subject"] = "🚨 Gas Leak Alert"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent successfully")
    except Exception as e:
        print("❌ Email failed:", e)

# ---------------- ROUTES ----------------
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
    state = data["state"]
    time = data["time"]

    latest_cloud_data["gas"] = gas
    latest_cloud_data["state"] = state
    latest_cloud_data["time"] = time

    print("☁️ UPDATE:", latest_cloud_data)
    print("🔍 email_sent:", email_sent)

    # -------- EMAIL LOGIC (GUARANTEED) --------
    if gas > GAS_THRESHOLD and not email_sent:
        print("🚨 GAS ABOVE THRESHOLD — SENDING EMAIL")
        send_email_alert(gas)
        email_sent = True

    elif gas < RESET_THRESHOLD:
        email_sent = False

    return {"status": "ok"}

# ---------------- START SERVER ----------------
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
