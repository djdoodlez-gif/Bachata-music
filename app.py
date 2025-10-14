import os, sqlite3
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

# ---- DB helpers ----
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as c:
        c.executescript((BASE_DIR / "schema.sql").read_text())

# ---- Auth setup ----
login_manager = LoginManager(app)
login_manager.login_view = "auth"

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def by_id(uid):
        with get_conn() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            return User(row["id"], row["username"], row["password_hash"]) if row else None

    @staticmethod
    def by_username(u):
        with get_conn() as c:
            row = c.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
            return User(row["id"], row["username"], row["password_hash"]) if row else None

@login_manager.user_loader
def load_user(user_id):
    return User.by_id(int(user_id))

# ---- Routes ----
@app.route("/")
def index():
    # фейковая лента «треки» как посты
    tracks = [
        {"title": "Romeo Santos — Propuesta Indecente", "url": "https://youtu.be/QFs3PIZb3js"},
        {"title": "Prince Royce — Darte un Beso", "url": "https://youtu.be/bdOXnTbyk0g"},
        {"title": "Aventura — Obsesión", "url": "https://youtu.be/I6-yj5-F7u4"},
        {"title": "XTreme — Te Extraño", "url": "https://youtu.be/8yW8J6Lw2Zs"},
    ]
    return render_template("feed.html", tracks=tracks)

@app.route("/auth", methods=["GET", "POST"])
def auth():
    # одна форма и для регистрации, и для входа
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()
        action   = request.form.get("action")

        if not username or not password:
            flash("Введите имя и пароль")
            return redirect(url_for("auth"))

        if action == "signup":
            if User.by_username(username):
                flash("Имя занято")
                return redirect(url_for("auth"))
            with get_conn() as c:
                c.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?,?)",
                    (username, generate_password_hash(password)),
                )
                uid = c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            login_user(User.by_id(uid))
            return redirect(url_for("index"))

        # login
        u = User.by_username(username)
        if not u or not check_password_hash(u.password_hash, password):
            flash("Неверные данные")
            return redirect(url_for("auth"))
        login_user(u)
        return redirect(url_for("index"))

    return render_template("auth.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/profile/<username>")
def profile(username):
    u = User.by_username(username.lower())
    if not u:
        flash("Пользователь не найден")
        return redirect(url_for("index"))
    return render_template("profile.html", u=u)

# ---- App startup ----
if not DB_PATH.exists():
    init_db()

if __name__ == "__main__":
    # локально — dev-сервер; на Render запускает gunicorn из Procfile
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
