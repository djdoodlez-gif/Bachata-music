
import os, sqlite3, uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data.sqlite3")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    sql = """
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        display_name TEXT,
        passhash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        media_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """
    db = get_db()
    db.executescript(sql)
    db.commit()
    admin_u = os.environ.get("ADMIN_USER")
    admin_p = os.environ.get("ADMIN_PASS")
    if admin_u and admin_p:
        row = db.execute("SELECT id FROM users WHERE username=?", (admin_u,)).fetchone()
        if not row:
            db.execute("INSERT INTO users(username, email, display_name, passhash) VALUES (?,?,?,?)",
                       (admin_u, f"{admin_u}@example.com", "Administrator", generate_password_hash(admin_p)))
            db.commit()

def current_user():
    if "uid" not in session:
        return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()

@app.before_request
def attach_user():
    g.user = current_user()

def save_uploaded(fs, allowed_ext={".jpg",".jpeg",".png",".gif",".webp",".mp4",".mov",".mp3",".wav"}):
    if not fs or not getattr(fs, "filename", ""):
        return None
    from os.path import splitext, join
    name = secure_filename(fs.filename or "file")
    ext = splitext(name)[1].lower()
    if ext not in allowed_ext:
        return None
    new = f"{uuid.uuid4().hex}{ext}"
    path = join(UPLOAD_DIR, new)
    fs.save(path)
    return url_for('static', filename=f'uploads/{new}', _external=False)

@app.route("/")
def index():
    return render_template("index.html", title="Bachatagram+")

@app.route("/auth/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        row = get_db().execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if row and check_password_hash(row["passhash"], p):
            session["uid"] = row["id"]
            return redirect(url_for("feed"))
        flash("Неверный логин или пароль", "err")
    return render_template("auth.html", title="Вход / Регистрация")

@app.route("/auth/register", methods=["POST"])
def register():
    u = request.form.get("username","").strip()
    e = request.form.get("email","").strip()
    d = request.form.get("display_name","").strip() or u
    p = request.form.get("password","")
    if not u or not p:
        flash("Заполни логин и пароль", "err")
        return redirect(url_for("login"))
    try:
        get_db().execute("INSERT INTO users(username,email,display_name,passhash) VALUES (?,?,?,?)",
                         (u,e,d,generate_password_hash(p)))
        get_db().commit()
        flash("Готово! Войдите своим логином и паролем.", "ok")
    except sqlite3.IntegrityError:
        flash("Такой логин уже есть", "err")
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/feed", methods=["GET","POST"])
def feed():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        text = request.form.get("text","").strip()
        media = save_uploaded(request.files.get("media"))
        if text or media:
            get_db().execute("INSERT INTO posts(user_id,text,media_url) VALUES (?,?,?)",
                             (g.user["id"], text, media))
            get_db().commit()
        return redirect(url_for("feed"))
    posts = get_db().execute(
        """SELECT p.*, u.username, u.display_name
           FROM posts p JOIN users u ON u.id=p.user_id
           ORDER BY p.id DESC"""
    ).fetchall()
    return render_template("feed.html", title="Лента", posts=posts)

@app.route("/me", methods=["GET","POST"])
def profile():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        display = request.form.get("display_name","").strip()
        email = request.form.get("email","").strip()
        get_db().execute("UPDATE users SET display_name=?, email=? WHERE id=?",
                         (display, email, g.user["id"]))
        get_db().commit()
        flash("Профиль обновлён", "ok")
        return redirect(url_for("profile"))
    my_posts = get_db().execute(
        "SELECT * FROM posts WHERE user_id=? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()
    return render_template("profile.html", title="Профиль", posts=my_posts)

DEMO_TRACKS = [
    {"id":1,"title":"Bachata Intro","artist":"Bachatagram","cover":"https://images.unsplash.com/photo-1511379938547-c1f69419868d?q=80&w=600&auto=format&fit=crop","url":"https://cdn.pixabay.com/audio/2022/03/15/audio_9b4f1d2b12.mp3"},
    {"id":2,"title":"Dance With Me","artist":"Bachatagram","cover":"https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?q=80&w=600&auto=format&fit=crop","url":"https://cdn.pixabay.com/audio/2021/11/01/audio_3a1b3b4ddd.mp3"},
    {"id":3,"title":"Mi Corazón","artist":"Bachatagram","cover":"https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?q=80&w=600&auto=format&fit=crop","url":"https://cdn.pixabay.com/audio/2022/06/01/audio_3f1fd05628.mp3"},
]

@app.route("/music")
def music():
    if not g.user:
        return redirect(url_for("login"))
    return render_template("music.html", title="Музыка")

@app.route("/api/tracks")
def api_tracks():
    return jsonify(DEMO_TRACKS)

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(os.path.join(BASE_DIR, "static", "uploads"), filename)


# ---------- bootstrap ----------
def _ensure_init():
    # запускаем инициализацию БД внутри application context
    with app.app_context():
        init_db()

# при запуске через gunicorn (import app:app) — выполнится сразу
_ensure_init()

# при локальном запуске — тоже всё ок
if name == "__main__":
    _ensure_init()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
