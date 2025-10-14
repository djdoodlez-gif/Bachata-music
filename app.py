import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, OperationalError

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

# База: обязательно проверь, что в Render задана переменная окружения DATABASE_URL (Internal Database URL)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local.sqlite3")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

# ---------- DB ----------
def init_db():
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
        return conn.execute(
            text("SELECT id, username FROM users WHERE id=:i"),
            {"i": uid}
        ).mappings().first()

@app.before_request
def load_current_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_user_by_id(uid)

# ---------- ROUTES ----------
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

        # логин регистрозависимый, при желании можно привести к lower()
        with engine.begin() as conn:
            user = conn.execute(
                text("SELECT id, username, passhash FROM users WHERE username=:u"),
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
    username = request.form.get("username","").strip()
    password = request.form.get("password","")
    if not username or not password:
        flash("Заполни логин и пароль")
        return redirect(url_for("login"))

    try:
        # создаём пользователя и СРАЗУ логиним (берём id через RETURNING)
        with engine.begin() as conn:
            row = conn.execute(
                text("INSERT INTO users(username, passhash) VALUES(:u,:p) RETURNING id"),
                {"u": username, "p": generate_password_hash(password)}
            ).first()
            new_id = row[0] if row else None
        if new_id:
            session["uid"] = new_id
            return redirect(url_for("feed"))
        else:
            flash("Не удалось создать пользователя")
    except Exception:
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
                conn.execute(
                    text("INSERT INTO posts(user_id, text) VALUES(:uid, :t)"),
                    {"uid": g.user["id"], "t": text_val}
                )
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
        my_posts = conn.execute(
            text("SELECT id, text, created_at FROM posts WHERE user_id=:uid ORDER BY id DESC"),
            {"uid": g.user["id"]}
        ).mappings().all()
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

# ---------- bootstrap ----------
def _ensure_db():
    try:
        init_db()
    except (ProgrammingError, OperationalError):
        pass

_ensure_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
    from sqlalchemy import text

@app.get("/_diag")
def diag():
    # 1) Сессия
    uid = session.get("uid")

    # 2) Подключение к БД
    db_ok = True
    users_cnt = None
    try:
        with engine.begin() as conn:
            users_cnt = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    except Exception as e:
        db_ok = False
        users_cnt = f"DB ERROR: {e}"

    # 3) Итог
    return {
        "session_uid": uid,
        "db_ok": db_ok,
        "users_count": users_cnt,
        "database_url_set": bool(os.environ.get("DATABASE_URL")),
    }, 200
