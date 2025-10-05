import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from flask_session import Session
from datetime import datetime, date
from apscheduler.schedulers.background import BackgroundScheduler
import json
from openai import OpenAI
from dotenv import load_dotenv
OpenAI.api_key ="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"
# Load environment variables from .env file
load_dotenv()

# ✅ Initialize OpenAI client using environment variable
print("Loaded key:", os.getenv("OPENAI_API_KEY"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'data.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript(open(os.path.join(BASE_DIR, 'schema.sql')).read())
    conn.commit()
    conn.close()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

scheduler = BackgroundScheduler()
scheduler.start()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# ---------- Helpers ----------
def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    return cur.lastrowid

def schedule_whatsapp_reminder(user_id, phone, times):
    def job_send():
        print(f"[Reminder] Would send WhatsApp reminder to {phone} for user {user_id} at {datetime.now()}")
    job_id = f"reminder_{user_id}"
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    for i, t in enumerate(times):
        hour, minute = map(int, t.split(':'))
        scheduler.add_job(job_send, 'cron', hour=hour, minute=minute, id=f'{job_id}_{i}')

# ---------- Routes ----------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email') or ''
        age = request.form.get('age') or '0'
        gender = request.form.get('gender') or ''
        times = request.form.get('reminder_times') or ''
        user_id = execute_db('INSERT INTO users (name, phone, email, age, gender, created_at) VALUES (?,?,?,?,?,?)',
                             (name, phone, email, age, gender, datetime.now()))
        if times.strip():
            schedule_whatsapp_reminder(user_id, phone, [t.strip() for t in times.split(',') if t.strip()])
        session['user_id'] = user_id
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        user = query_db('SELECT * FROM users WHERE phone=?', (phone,), one=True)
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
        return "User not found. Please register."
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('register'))
    user = query_db('SELECT * FROM users WHERE id=?', (session['user_id'],), one=True)
    workouts = query_db('SELECT * FROM workouts WHERE user_id=? ORDER BY created_at DESC LIMIT 30', (session['user_id'],))
    foods = query_db('SELECT * FROM foods WHERE user_id=? ORDER BY created_at DESC LIMIT 30', (session['user_id'],))
    total_workouts = query_db('SELECT COUNT(*) as cnt FROM workouts WHERE user_id=?', (session['user_id'],), one=True)['cnt']
    total_foods = query_db('SELECT COUNT(*) as cnt FROM foods WHERE user_id=?', (session['user_id'],), one=True)['cnt']
    return render_template('dashboard.html', user=user, workouts=workouts, foods=foods,
                           total_workouts=total_workouts, total_foods=total_foods)

@app.route('/health')
def health():
    if 'user_id' not in session:
        return redirect(url_for('register'))
    return render_template('health.html')

@app.route('/fitness')
def fitness():
    if 'user_id' not in session:
        return redirect(url_for('register'))
    return render_template('fitness.html')

@app.route('/add_workout', methods=['POST'])
def add_workout():
    if 'user_id' not in session:
        return jsonify({'error': 'not_logged_in'}), 401
    title = request.form.get('title')
    notes = request.form.get('notes')
    execute_db('INSERT INTO workouts (user_id, title, notes, created_at) VALUES (?,?,?,?)',
               (session['user_id'], title, notes, datetime.now()))
    return redirect(url_for('dashboard'))

@app.route('/add_food', methods=['POST'])
def add_food():
    if 'user_id' not in session:
        return jsonify({'error': 'not_logged_in'}), 401
    name = request.form.get('name')
    calories = float(request.form.get('calories') or 0)
    unit = request.form.get('unit') or ''
    execute_db('INSERT INTO foods (user_id, name, calories, unit, created_at) VALUES (?,?,?,?,?)',
               (session['user_id'], name, calories, unit, datetime.now()))
    return redirect(url_for('dashboard'))

@app.route('/daily_task')
def daily_task():
    tasks = json.load(open(os.path.join(BASE_DIR, 'daily_tasks.json')))
    idx = date.today().toordinal() % len(tasks)
    return jsonify(tasks[idx])

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    text = (data.get('message') or '').lower()

    calories_db = {
        'apple': 52, 'banana': 96, 'egg': 78, 'bread slice': 80,
        'rice (100g)': 130, 'chicken (100g)': 239, 'potato (100g)': 77
    }

    for key, cal in calories_db.items():
        if key in text:
            reply = f"{key.title()} has about {cal} kcal per typical serving. "
            if cal > 300:
                reply += "This is relatively high in calories — consider portion control."
            else:
                reply += "This is fine as part of a balanced diet."
            return jsonify({'reply': reply})

    #if any(w in text for w in ['calorie', 'calories', 'how many']):
     #   return jsonify({'reply': "Tell me the food name and amount (e.g. '100g rice' or '1 banana') and I'll estimate calories."})

   # if 'help' in text or 'advice' in text:
       # return jsonify({'reply': "I can estimate calories for common foods, help plan reminders, and track your workouts. Ask me about a food or type 'daily tips'."})

    #if 'daily tips' in text:
       # return jsonify({'reply': "Today's tip: Stay hydrated and include a protein source in every meal."})

    # ✅ OpenAI Integration for richer replies
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful nutrition and fitness assistant."},
                {"role": "user", "content": text}
            ]
        )
        ai_reply = response.choices[0].message.content
        return jsonify({'reply': ai_reply})
    except Exception as e:
        return jsonify({'reply': f"Sorry, something went wrong: {str(e)}"})

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
