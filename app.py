
import os
import uuid
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, g, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, scoped_session

# ---------------- Config ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
RENDER_UPLOAD_DIR = "/tmp/uploads"
UPLOAD_DIR = RENDER_UPLOAD_DIR if os.getenv("RENDER") else DEFAULT_UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_VIDEO = {".mp4", ".mov", ".webm"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg"}
ALLOWED_ANY = ALLOWED_IMAGE | ALLOWED_VIDEO | ALLOWED_AUDIO

# DB: Postgres via DATABASE_URL if provided, otherwise SQLite (for local dev)
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{os.path.join(BASE_DIR, 'data.sqlite3')}"

# SQLAlchemy engine / session
if DATABASE_URL.startswith("postgres://"):
    # Render/Heroku old scheme. SQLAlchemy requires postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()

# ---------------- Models ----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True)
    passhash = Column(String(255), nullable=False)
    display_name = Column(String(120))
    bio = Column(Text)
    avatar = Column(String(255))  # path
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    posts = relationship("Post", back_populates="user", cascade="all,delete")
    albums = relationship("Album", back_populates="user", cascade="all,delete")
    tracks = relationship("Track", back_populates="user", cascade="all,delete")
    stories = relationship("Story", back_populates="user", cascade="all,delete")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text)
    media_path = Column(String(255))
    media_type = Column(String(10))  # image/video/audio/none
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="posts")

class Album(Base):
    __tablename__ = "albums"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(120), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="albums")
    photos = relationship("Photo", back_populates="album", cascade="all,delete")

class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    path = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    album = relationship("Album", back_populates="photos")

class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=True)
    title = Column(String(160), nullable=False)
    path = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tracks")
    album = relationship("Album", backref="tracks")

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    media_path = Column(String(255), nullable=False)
    media_type = Column(String(10), nullable=False)  # image/video
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="stories")

# ---------------- App ----------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")

# ------------- Helpers -------------
def db():
    if not hasattr(g, "db"):
        g.db = SessionLocal()
    return g.db

@app.teardown_appcontext
def shutdown_session(exception=None):
    if hasattr(g, "db"):
        g.db.close()

def save_uploaded(fs, allowed=ALLOWED_ANY):
    if not fs or not getattr(fs, "filename", ""):
        return None
    name = secure_filename(fs.filename or "").strip()
    ext = os.path.splitext(name)[1].lower()
    if ext not in allowed:
        return None
    new = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, new)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fs.save(path)
    return url_for("uploaded_file", filename=new)

@app.before_request
def attach_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = db().get(User, uid)
    # Theme toggle
    theme = request.args.get("theme")
    if theme in ("light", "dark"):
        session["theme"] = theme

@app.context_processor
def inject_globals():
    return {"now": datetime.utcnow(), "theme": session.get("theme", "dark")}

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

def ensure_admin():
    admin_u = os.getenv("ADMIN_USERNAME")
    admin_p = os.getenv("ADMIN_PASSWORD")
    if not admin_u or not admin_p:
        return
    s = db()
    exists = s.query(User).filter_by(username=admin_u).first()
    if not exists:
        s.add(User(
            username=admin_u,
            email=f"{admin_u}@local",
            passhash=generate_password_hash(admin_p),
            display_name="Administrator",
            is_admin=True
        ))
        s.commit()

def init_db():
    Base.metadata.create_all(bind=engine)
    ensure_admin()

# ------------- Routes -------------
@app.route("/")
def index():
    if g.user:
        return redirect(url_for("feed"))
    return render_template("index.html", title="Bachatagram+ — вход")

# -------- Auth --------
@app.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        u = db().query(User).filter_by(username=username).first()
        if u and check_password_hash(u.passhash, password):
            session["uid"] = u.id
            return redirect(url_for("feed"))
        flash("Неверный логин или пароль")
    return render_template("auth.html", title="Вход / Регистрация")

@app.route("/auth/register", methods=["POST"])
def register():
    username = request.form.get("username","").strip()
    email = request.form.get("email","").strip() or None
    display_name = request.form.get("display_name","").strip() or username
    password = request.form.get("password","")
    if not username or not password:
        flash("Заполни логин и пароль")
        return redirect(url_for("login"))
    s = db()
    if s.query(User.id).filter_by(username=username).first():
        flash("Такой логин уже есть")
        return redirect(url_for("login"))
    u = User(username=username, email=email,
             display_name=display_name, passhash=generate_password_hash(password))
    s.add(u); s.commit()
    session["uid"] = u.id
    return redirect(url_for("feed"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# -------- Feed / Posts --------
@app.route("/feed", methods=["GET","POST"])
def feed():
    if not g.user:
        return redirect(url_for("login"))
    s = db()
    if request.method == "POST":
        text = request.form.get("text","").strip()
        media = save_uploaded(request.files.get("media"), ALLOWED_ANY)
        media_type = "none"
        if media:
            ext = os.path.splitext(media)[1].lower()
            if ext in ALLOWED_IMAGE: media_type = "image"
            elif ext in ALLOWED_VIDEO: media_type = "video"
            elif ext in ALLOWED_AUDIO: media_type = "audio"
        if text or media:
            s.add(Post(user_id=g.user.id, text=text, media_path=media, media_type=media_type))
            s.commit()
        return redirect(url_for("feed"))
    posts = s.query(Post).order_by(Post.id.desc()).limit(100).all()
    return render_template("feed.html", title="Лента", posts=posts)

# -------- Profile & Settings --------
@app.route("/me")
def me():
    if not g.user: return redirect(url_for("login"))
    return redirect(url_for("profile", username=g.user.username))

@app.route("/u/<username>")
def profile(username):
    s = db()
    user = s.query(User).filter_by(username=username).first()
    if not user: abort(404)
    posts = s.query(Post).filter_by(user_id=user.id).order_by(Post.id.desc()).all()
    albums = s.query(Album).filter_by(user_id=user.id).order_by(Album.id.desc()).all()
    tracks = s.query(Track).filter_by(user_id=user.id).order_by(Track.id.desc()).all()
    stories = s.query(Story).filter(Story.user_id==user.id, Story.expires_at > datetime.utcnow()).order_by(Story.id.desc()).all()
    return render_template("profile.html", user=user, posts=posts, albums=albums, tracks=tracks, stories=stories, title=f"{user.username} — профиль")

@app.route("/settings", methods=["GET","POST"])
def settings():
    if not g.user: return redirect(url_for("login"))
    s = db()
    u = s.get(User, g.user.id)
    if request.method == "POST":
        u.display_name = request.form.get("display_name","").strip() or u.display_name
        u.bio = request.form.get("bio","").strip()
        avatar = save_uploaded(request.files.get("avatar"), ALLOWED_IMAGE)
        if avatar: u.avatar = avatar
        s.commit()
        flash("Профиль обновлён")
        return redirect(url_for("settings"))
    return render_template("settings.html", title="Настройки", user=u)

# -------- Albums & Photos --------
@app.route("/albums", methods=["GET","POST"])
def albums():
    if not g.user: return redirect(url_for("login"))
    s = db()
    if request.method == "POST":
        title = request.form.get("title","").strip()
        desc = request.form.get("description","").strip()
        if title:
            s.add(Album(user_id=g.user.id, title=title, description=desc))
            s.commit()
        return redirect(url_for("albums"))
    my_albums = s.query(Album).filter_by(user_id=g.user.id).order_by(Album.id.desc()).all()
    return render_template("albums.html", title="Альбомы", albums=my_albums)

@app.route("/albums/<int:album_id>", methods=["GET","POST"])
def album_detail(album_id):
    if not g.user: return redirect(url_for("login"))
    s = db()
    album = s.get(Album, album_id)
    if not album or album.user_id != g.user.id: abort(404)
    if request.method == "POST":
        photo = save_uploaded(request.files.get("photo"), ALLOWED_IMAGE)
        if photo:
            s.add(Photo(album_id=album.id, path=photo)); s.commit()
        return redirect(url_for("album_detail", album_id=album.id))
    photos = s.query(Photo).filter_by(album_id=album.id).order_by(Photo.id.desc()).all()
    return render_template("album_detail.html", title=album.title, album=album, photos=photos)

# -------- Music --------
@app.route("/music", methods=["GET","POST"])
def music():
    if not g.user: return redirect(url_for("login"))
    s = db()
    if request.method == "POST":
        title = request.form.get("title","").strip()
        album_id = request.form.get("album_id")
        album_id = int(album_id) if album_id and album_id.isdigit() else None
        path = save_uploaded(request.files.get("track"), ALLOWED_AUDIO)
        if title and path:
            s.add(Track(user_id=g.user.id, album_id=album_id, title=title, path=path)); s.commit()
        return redirect(url_for("music"))
    my_tracks = s.query(Track).filter_by(user_id=g.user.id).order_by(Track.id.desc()).all()
    my_albums = s.query(Album).filter_by(user_id=g.user.id).order_by(Album.id.desc()).all()
    return render_template("music.html", title="Музыка", tracks=my_tracks, albums=my_albums)

# -------- Stories --------
@app.route("/stories", methods=["GET","POST"])
def stories():
    if not g.user: return redirect(url_for("login"))
    s = db()
    if request.method == "POST":
        media = save_uploaded(request.files.get("media"), ALLOWED_IMAGE | ALLOWED_VIDEO)
        if media:
            ext = os.path.splitext(media)[1].lower()
            mtype = "image" if ext in ALLOWED_IMAGE else "video"
            s.add(Story(user_id=g.user.id, media_path=media, media_type=mtype,
                        expires_at=datetime.utcnow() + timedelta(hours=24)))
            s.commit()
        return redirect(url_for("stories"))
    # garbage collect expired
    s.query(Story).filter(Story.expires_at <= datetime.utcnow()).delete()
    s.commit()
    recent = s.query(Story).filter(Story.expires_at > datetime.utcnow()).order_by(Story.id.desc()).all()
    return render_template("stories.html", title="Истории", stories=recent)

# -------- Admin (minimal) --------
@app.route("/admin")
def admin():
    if not g.user or not g.user.is_admin:
        abort(403)
    s = db()
    users = s.query(User).order_by(User.id.desc()).all()
    return render_template("admin.html", title="Админ", users=users)

# ------------- Bootstrap -------------
init_db()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
