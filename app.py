import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

def _sa_url():
    raw = os.getenv("DATABASE_URL", "")
    if not raw:
        return "sqlite:///data.sqlite3"
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+psycopg://", 1)
    elif raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = _sa_url()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255))
    display_name = db.Column(db.String(120))
    passhash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey("users.id"), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now())
    user = db.relationship(User, backref="posts")

@app.before_request
def _load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = db.session.get(User, uid)

def ensure_db():
    with app.app_context():
        db.create_all()
        admin_login = os.getenv("ADMIN_USERNAME")
        admin_pass = os.getenv("ADMIN_PASSWORD")
        admin_email = os.getenv("ADMIN_EMAIL", None)
        if admin_login and admin_pass:
            u = User.query.filter_by(username=admin_login).first()
            if not u:
                u = User(username=admin_login,
                         display_name=os.getenv("ADMIN_DISPLAY","Admin"),
                         email=admin_email,
                         passhash=generate_password_hash(admin_pass),
                         is_admin=True)
                db.session.add(u)
                db.session.commit()

@app.route("/")
def index():
    return render_template("index.html", title="Bachatagram")

@app.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.passhash, password):
            session["uid"] = user.id
            return redirect(url_for("feed"))
        flash("Неверный логин или пароль")
    return render_template("auth.html", title="Вход / Регистрация")

@app.route("/auth/register", methods=["POST"])
def register():
    username = request.form.get("username","").strip()
    email = request.form.get("email","").strip() or None
    display_name = request.form.get("display_name","").strip() or None
    password = request.form.get("password","")
    if not username or not password:
        flash("Заполни логин и пароль")
        return redirect(url_for("login"))
    if User.query.filter_by(username=username).first():
        flash("Такой логин уже есть")
        return redirect(url_for("login"))
    u = User(username=username, email=email, display_name=display_name,
             passhash=generate_password_hash(password))
    db.session.add(u)
    db.session.commit()
    flash("Готово! Теперь войдите.")
    return redirect(url_for("login"))

@app.route("/feed", methods=["GET","POST"])
def feed():
    if not g.user:
        return redirect(url_for("login"))
    if request.method == "POST":
        text = request.form.get("text","").strip()
        if text:
            db.session.add(Post(user_id=g.user.id, text=text))
            db.session.commit()
        return redirect(url_for("feed"))
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template("feed.html", title="Лента", posts=posts)

@app.route("/me")
def profile():
    if not g.user:
        return redirect(url_for("login"))
    posts = Post.query.filter_by(user_id=g.user.id).order_by(Post.id.desc()).all()
    return render_template("profile.html", title="Мой профиль", user=g.user, posts=posts)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

ensure_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
