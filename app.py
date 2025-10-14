import os, sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "data.sqlite3")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        passhash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """
    db = get_db()
    db.executescript(sql)
    db.commit()

# ---------- helpers ----------
def current_user():
    if "uid" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (session["uid"],)).fetchone()

# ---------- routes ----------
@app.route("/")
def index():
    return render_template("index.html", title="Bachatagram")

@app.route("/auth/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["passhash"], password):
            session["uid"] = user["id"]
            return redirect(url_for("feed"))
        flash("Неверный логин или пароль")
    return render_template("auth.html", title="Вход / Регистрация")

@app.route("/auth/register", methods=["POST"])
def register():
    db = get_db()
    username = request.form.get("username","").strip()
    password = request.form.get("password","")
    if not username or not password:
        flash("Заполни логин и пароль")
        return redirect(url_for("login"))
    try:
        db.execute(
            "INSERT INTO users(username, passhash) VALUES (?,?)",
            (username, generate_password_hash(password))
        )
        db.commit()
        flash("Готово! Войдите своим логином и паролем.")
    except sqlite3.IntegrityError:
        flash("Такой логин уже есть")
    return redirect(url_for("login"))

@app.route("/feed", methods=["GET","POST"])
def feed():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    if request.method == "POST":
        text = request.form.get("text","").strip()
        if text:
            db.execute("INSERT INTO posts(user_id, text) VALUES (?,?)", (user["id"], text))
            db.commit()
        return redirect(url_for("feed"))
    posts = db.execute(
        """SELECT p.id, p.text, p.created_at, u.username
           FROM posts p JOIN users u ON u.id = p.user_id
           ORDER BY p.id DESC"""
    ).fetchall()
    return render_template("feed.html", title="Лента — Bachatagram", posts=posts, user=user)

@app.route("/me")
def profile():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    db = get_db()
    my_posts = db.execute(
        "SELECT id, text, created_at FROM posts WHERE user_id = ? ORDER BY id DESC",
        (user["id"],)
    ).fetchall()
    return render_template("profile.html", title="Мой профиль", user=user, posts=my_posts)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- bootstrap ----------
def bootstrap():
    with app.app_context():
        init_db()

if __name__ == "__main__":
    bootstrap()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    bootstrap()
