# app.py
import os, sqlite3
from flask import Flask, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from auth import bp_auth, init_login

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret')
UPLOAD_DIR = 'uploads'
os.makedirs('data', exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# init db
def init_db():
    import sqlite3
    con = sqlite3.connect('data/app.db')
    with open('schema.sql','r',encoding='utf-8') as f:
        con.executescript(f.read())
    con.commit(); con.close()

# login manager
login_manager = init_login(app)

# blueprints
app.register_blueprint(bp_auth)

@app.route('/')
def index():
    return render_template('index.html', title='Bachatagram')

@app.route('/feed')
@login_required
def feed():
    # заглушка: отдаём пустую ленту
    posts = []
    return render_template('feed.html', title='Лента — Bachatagram', posts=posts)

@app.route('/me')
@login_required
def profile():
    return render_template('profile.html', title='Мой профиль', user=current_user)

if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
