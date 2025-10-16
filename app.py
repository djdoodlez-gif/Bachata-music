import os
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, OperationalError, IntegrityError

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

# Cookie-настройки: делаем безопасно на проде с https, но не ломаем локально/на http
is_render = os.environ.get("RENDER", "").lower() == "true"
app.config.update(
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=is_render,   # на *.onrender.com есть https → True; на http будет False
)

# ---- DB ----
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.sqlite3")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users(
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  passhash TEXT NOT NULL,
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS posts(
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

def init_db():
    with engine.begin() as conn:
        for stmt in SCHEMA_SQL.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

def ensure_admin_user():
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_username or not admin_password:
        return
    admin_email = os.environ.get("ADMIN_EMAIL", f"{admin_username}@example.com")
    admin_display = os.environ.get("ADMIN_DISPLAY_NAME", "Administrator")
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id FROM users WHERE username=:u"), {"u": admin_username}).first()
        if row:
            conn.execute(text("UPDATE users SET is_admin=TRUE WHERE username=:u"), {"u": admin_username})
            return
        conn.execute(
            text("""INSERT INTO users(username,email,display_name,passhash,is_admin)
                    VALUES(:u,:e,:d,:p,TRUE)"""),
            {"u": admin_username, "e": admin_email, "d": admin_display, "p": generate_password_hash(admin_password)}
        )

def get_user_by_id(uid: int):
    with engine.begin() as conn:
        return conn.execute(
            text("SELECT id, username, email, display_name, is_admin FROM users WHERE id=:i"),
            {"i": uid}
        ).mappings().first()

@app.before_request
def load_current_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_user_by_id(uid)

def login_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return _wrap

def admin_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        if not g.user["is_admin"]:
            abort(403)
        return f(*args, **kwargs)
    return _wrap

# ---- routes ----
@app.get("/")
def index():
    return render_template("index.html", title="Bachatagram")

@app.get("/health")
def health():
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return "ok", 200
    except Exception as e:
        return f"db error: {e}", 500

# Диагностика (временная, можно оставить)
@app.get("/_diag")
def diag():
    uid = session.get("uid")
    db_ok = True
    users_cnt = None
    try:
        with engine.begin() as conn:
            users_cnt = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    except Exception as e:
        db_ok = False
        users_cnt = f"DB ERROR: {e}"
    return {
        "session_uid": uid,
        "db_ok": db_ok,
        "users_count": users_cnt,
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
        "render_env": is_render,
        "secure_cookie": app.config["SESSION_COOKIE_SECURE"],
    }, 200

# ---- auth ----
@app.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if not username or not password:
            flash("Заполни логин и пароль")
            return redirect(url_for("login"))

        with engine.begin() as conn:
            user = conn.execute(
                text("SELECT id, passhash FROM users WHERE username=:u"),
                {"u": username}
            ).mappings().first()

        if user and check_password_hash(user["passhash"], password):
            session["uid"] = user["id"]
            return redirect(url_for("feed"))

        flash("Неверный логин или пароль")
        return redirect(url_for("login"))

    return render_template("auth.html", title="Вход / Регистрация")

@app.post("/auth/register")
def register():
    username     = request.form.get("username","").strip()
    email        = request.form.get("email","").strip().lower()
    display_name = request.form.get("display_name","").strip()
    password     = request.form.get("password","")

    if not username or not email or not display_name or not password:
        flash("Заполни все поля")
        return redirect(url_for("login"))

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("""INSERT INTO users(username,email,display_name,passhash)
                        VALUES(:u,:e,:d,:p) RETURNING id"""),
                {"u": username, "e": email, "d": display_name, "p": generate_password_hash(password)}
            ).first()
            new_id = row[0] if row else None
        if new_id:
            session["uid"] = new_id
            return redirect(url_for("feed"))
        flash("Не удалось создать пользователя")
    except IntegrityError:
        flash("Логин или e-mail уже заняты")
    except Exception as e:
        flash(f"Ошибка регистрации: {e}")
    return redirect(url_for("login"))

@app.route("/feed", methods=["GET","POST"])
@login_required
def feed():
    if request.method == "POST":
        text_val = request.form.get("text","").strip()
        if text_val:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO posts(user_id, text) VALUES(:uid, :t)"),
                             {"uid": g.user["id"], "t": text_val})
        return redirect(url_for("feed"))

    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT p.id, p.text, p.created_at, u.username
            FROM posts p JOIN users u ON u.id = p.user_id
            ORDER BY p.id DESC
        """)).mappings().all()
    return render_template("feed.html", title="Лента — Bachatagram", posts=rows, user=g.user)

@app.get("/me")
@login_required
def me():
    with engine.begin() as conn:
        my_posts = conn.execute(
            text("SELECT id, text, created_at FROM posts WHERE user_id=:uid ORDER BY id DESC"),
            {"uid": g.user["id"]}
        ).mappings().all()
    return render_template("profile.html", title="Мой профиль", user=g.user, posts=my_posts)

# ---- admin ----
@app.get("/admin")
@admin_required
def admin_panel():
    with engine.begin() as conn:
        users = conn.execute(text("""
            SELECT id, username, email, display_name, is_admin, created_at
            FROM users ORDER BY id DESC
        """)).mappings().all()
    return render_template("admin.html", title="Админка", users=users)

@app.post("/admin/make_admin")
@admin_required
def make_admin():
    username = request.form.get("username","").strip()
    if not username:
        flash("Укажи логин")
        return redirect(url_for("admin_panel"))
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_admin=TRUE WHERE username=:u"), {"u": username})
    flash(f"Пользователь @{username} теперь админ")
    return redirect(url_for("admin_panel"))

# ---- bootstrap ----
def _bootstrap():
    init_db()
    ensure_admin_user()

try:
    _bootstrap()
except (ProgrammingError, OperationalError):
    pass

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
