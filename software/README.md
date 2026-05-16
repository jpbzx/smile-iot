# Software

Python application layer for telemetry ingestion and data visualization.

## Architecture
This directory contains two decoupled services communicating via a local data store:
1. **`listener.py`:** Background MQTT client. Subscribes to the broker and writes incoming telemetry payloads to local storage (`data.json`).
2. **`dashboard.py`:** Streamlit web interface. Polls the local storage and renders real-time time-series charts and KPIs.

## Setup

### 1. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

**Critical for password reset via email:**
- **SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD:** Configure a valid SMTP server (e.g., Gmail, SendGrid, corporate mail server)
- **RESET_URL_BASE:** Set to your Streamlit app URL (localhost for dev, production domain for live)

**Example Gmail setup:**
1. Enable 2-Step Verification on your Google Account
2. Generate an [App Password](https://myaccount.google.com/apppasswords) for "Mail" and "Windows Computer"
3. Use that App Password as `SMTP_PASSWORD`
4. Set `SMTP_USER` to your full Gmail address

**Example for other SMTP servers (e.g., corporate Exchange, SendGrid):**
- Contact your IT team or hosting provider for SMTP credentials
- Update `SMTP_HOST` and `SMTP_PORT` accordingly

## Execution

Run both services concurrently in separate terminal sessions.

**Prerequisites:** Make sure `.env` is configured and SMTP variables are set for password reset to work.

Terminal 1 - Start the ingestion deamon
```bash
python listener.py
```

Terminal 2 - Boot the web UI 
```bash
streamlit run dashboard.py
```

## Features

### Password Reset Flow
Users can reset forgotten passwords via email:
1. On the login page, enter **username** and **email** (must match user's registered email or admin email)
2. System generates a secure token and sends it to the user's registered email
3. User pastes token back on the login form to set a new password

**Note:** For email delivery to work, valid SMTP credentials must be configured in `.env`


