import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, OperationalError

# -------------------- конфиг --------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

# DATABASE_URL берём из Render PostgreSQL (или локально SQLite для разработки)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.sqlite3")
# Render иногда отдаёт postgres:// — SQLAlchemy тоже понимает, оставляем как есть.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

# -------------------- БД утилиты --------------------
def init_db():
    """Создаёт таблицы, если их нет."""
    schema_sql = """
    CREATE TABLE IF NOT EXISTS users(
      id SERIAL PRIMARY KEY,
      username TEXT UNIQUE NOT NULL,
      passhash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS posts(
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      text TEXT NOT NULL,
      created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """
    with engine.begin() as conn:
        for stmt in schema_sql.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

def get_user_by_id(uid: int):
    with engine.begin() as conn:
        row = conn.execute(text("SELECT id, username FROM users WHERE id=:i"), {"i": uid}).mappings().first()
        return row

@app.before_request
def load_current_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_user_by_id(uid)

# -------------------- маршруты --------------------
@app.get("/")
def index():
    return render_template("index.html", title="Bachatagram")

@app.route("/auth/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        if not username or not password:
            flash("Заполни логин и пароль")
            return redirect(url_for("login"))
        with engine.begin() as conn:
            user = conn.execute(text("SELECT id, username, passhash FROM users WHERE username=:u"),
                                {"u": username}).mappings().first()
        if user and check_password_hash(user["passhash"], password):
            session["uid"] = user["id"]
            return redirect(url_for("feed"))
        flash("Неверный логин или пароль")
    return render_template("auth.html", title="Вход / Регистрация")

@app.post("/auth/register")
def register():
    username = request.form.get("username","").strip()
    password = request.form.get("password","")
    if not username or not password:
        flash("Заполни логин и пароль")
        return redirect(url_for("login"))
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO users(username, passhash) VALUES(:u, :p)"
            ), {"u": username, "p": generate_password_hash(password)})
        flash("Готово! Теперь войди.")
    except Exception:
        # дубликат логина/ошибка
        flash("Такой логин уже есть")
    return redirect(url_for("login"))

@app.route("/feed", methods=["GET","POST"])
def feed():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        text_val = request.form.get("text","").strip()
        if text_val:
            with engine.begin() as conn:
                conn.execute(text(
                    "INSERT INTO posts(user_id, text) VALUES(:uid, :t)"
                ), {"uid": g.user["id"], "t": text_val})
        return redirect(url_for("feed"))

    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT p.id, p.text, p.created_at, u.username
            FROM posts p JOIN users u ON u.id = p.user_id
            ORDER BY p.id DESC
        """)).mappings().all()
    return render_template("feed.html", title="Лента — Bachatagram", posts=rows, user=g.user)

@app.get("/me")
def me():
    if not g.user: 
        return redirect(url_for("login"))
    with engine.begin() as conn:
        my_posts = conn.execute(text("""
            SELECT id, text, created_at FROM posts
            WHERE user_id=:uid ORDER BY id DESC
        """), {"uid": g.user["id"]}).mappings().all()
    return render_template("profile.html", title="Мой профиль", user=g.user, posts=my_posts)

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.get("/health")
def health():
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT 1"))
        return "ok", 200
    except Exception as e:
        return f"db error: {e}", 500

# -------------------- запуск / инициализация --------------------
def _ensure_db():
    try:
        init_db()
    except (ProgrammingError, OperationalError):
        # при холодном старте подождём, если БД ещё поднимается
        pass

_ensure_db()

if __name__ == "__main__":
    # локальный запуск (dev)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
