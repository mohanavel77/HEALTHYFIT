Health & Fitness Tracker (Flask)
--------------------------------
How to run (local):
1. Python 3.8+ recommended.
2. Create a virtualenv: python -m venv venv
3. Activate it and install: pip install -r requirements.txt
4. Copy .env.example to .env and fill secrets if using OpenAI/Twilio.
5. Run: python app.py
6. Open http://127.0.0.1:5000 in your browser.

Notes:
- The chatbox is rule-based by default and will respond to basic food queries.
- For production WhatsApp reminders, sign up for Twilio, set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM and uncomment the Twilio code in app.py.
- The SQLite DB (data.db) is created automatically on first run.
- This project is scaffolded for extension: you can plug an AI API (OpenAI) in /chat for richer responses.
