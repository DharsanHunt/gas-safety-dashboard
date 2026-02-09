from flask import Flask, jsonify, render_template, request
from datetime import datetime
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__)

GAS_THRESHOLD = 400
RESET_THRESHOLD = 350

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER")

latest_cloud_data = {"gas": 0, "state": "OFF", "time": ""}
email_sent = False

def send_email_alert(gas):
    print("📧 Sending email via SendGrid")

    message = Mail(
        from_email=EMAIL_SENDER,
        to_emails=EMAIL_RECEIVER,
        subject="🚨 Gas Leak Alert",
        html_content=f"""
        <h2>🚨 GAS LEAK ALERT 🚨</h2>
        <p><b>Gas Level:</b> {gas}</p>
        <p><b>Threshold:</b> {GAS_THRESHOLD}</p>
        <p><b>Time:</b> {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
        """
    )

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(message)
    print("✅ Email sent")

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

    latest_cloud_data.update(data)

    if gas > GAS_THRESHOLD and not email_sent:
        send_email_alert(gas)
        email_sent = True
    elif gas < RESET_THRESHOLD:
        email_sent = False

    return {"status": "ok"}

port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
