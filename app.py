import sqlite3, os
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-change-me')
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.sqlite')

# ---------- DB helpers ----------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    db = get_db()
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r', encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()

@app.before_request
def load_user():
    uid = session.get('uid')
    if uid:
        g.user = get_db().execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    else:
        g.user = None

# ---------- Auth ----------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        if len(username) < 3: 
            flash('Имя слишком короткое'); return redirect(url_for('register'))
        db = get_db()
        try:
            db.execute('INSERT INTO users(username,email,password_hash) VALUES(?,?,?)',
                       (username, email, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            flash('Такой логин или email уже занят'); return redirect(url_for('register'))
        flash('Готово! Войдите.')
        return redirect(url_for('login'))
    return render_template('auth.html', title='Регистрация', btn='Создать аккаунт', register=True)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = get_db().execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Неверный email или пароль'); return redirect(url_for('login'))
        session['uid'] = user['id']
        return redirect(url_for('feed'))
    return render_template('auth.html', title='Вход', btn='Войти', register=False)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- Feed ----------
@app.route('/', methods=['GET'])
def feed():
    db = get_db()
    rows = db.execute('''
    SELECT p.*, u.username, u.avatar_url,
      (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id) AS likes_count
    FROM posts p JOIN users u ON u.id=p.user_id
    ORDER BY p.created_at DESC
    LIMIT 100
    ''').fetchall()

    posts = []
    uid = g.user['id'] if g.user else None
    for r in rows:
        liked = False
        comments = db.execute('''
            SELECT c.*, u.username FROM comments c
            JOIN users u ON u.id=c.user_id WHERE c.post_id=? ORDER BY c.created_at ASC
        ''', (r['id'],)).fetchall()
        if uid:
            liked = db.execute('SELECT 1 FROM likes WHERE user_id=? AND post_id=?', (uid, r['id'])).fetchone() is not None
        posts.append({**dict(r), 'liked': liked, 'comments': comments})
    return render_template('feed.html', posts=posts)

@app.post('/post')
def create_post():
    if not g.user: abort(403)
    content = request.form['content'].strip()
    image_url = request.form.get('image_url','').strip() or None
    if not content: return redirect(url_for('feed'))
    db = get_db()
    db.execute('INSERT INTO posts(user_id,content,image_url) VALUES(?,?,?)',
               (g.user['id'], content, image_url))
    db.commit()
    return redirect(url_for('feed'))

@app.post('/like/<int:post_id>')
def toggle_like(post_id):
    if not g.user: abort(403)
    db = get_db()
    exists = db.execute('SELECT 1 FROM likes WHERE user_id=? AND post_id=?',
                        (g.user['id'], post_id)).fetchone()
    if exists:
        db.execute('DELETE FROM likes WHERE user_id=? AND post_id=?', (g.user['id'], post_id))
    else:
        db.execute('INSERT INTO likes(user_id, post_id) VALUES(?,?)',(g.user['id'], post_id))
    db.commit()
    return redirect(url_for('feed'))

@app.post('/comment/<int:post_id>')
def add_comment(post_id):
    if not g.user: abort(403)
    content = request.form['content'].strip()
    if content:
        db = get_db()
        db.execute('INSERT INTO comments(user_id,post_id,content) VALUES(?,?,?)',
                   (g.user['id'], post_id, content))
        db.commit()
    return redirect(url_for('feed'))

# ---------- Profile ----------
@app.get('/u/<username>')
def profile(username):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if not user: abort(404)
    posts = db.execute('SELECT * FROM posts WHERE user_id=? ORDER BY created_at DESC', (user['id'],)).fetchall()
    return render_template('profile.html', user=user, posts=posts)

@app.post('/profile/update')
def update_profile():
    if not g.user: abort(403)
    avatar_url = request.form.get('avatar_url','').strip()
    bio = request.form.get('bio','').strip()
    db = get_db()
    db.execute('UPDATE users SET avatar_url=?, bio=? WHERE id=?', (avatar_url, bio, g.user['id']))
    db.commit()
    flash('Сохранено')
    return redirect(url_for('profile', username=g.user['username']))

# ---------- CLI ----------
@app.cli.command('init-db')
def _init():
    '''flask init-db'''
    init_db()
    print('DB initialized')

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(DB_PATH):
        with app.app_context():
            init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
