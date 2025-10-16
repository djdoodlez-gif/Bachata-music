
# Bachatagram+ (mini‑VK/Instagram style)

Features:
- Auth: login/registration (hashed passwords), sessions
- Profiles: avatar, bio, display name editing
- Feed: posts with text + photo/video/audio
- Stories: 24h image/video
- Albums & Photos
- Music: upload audio, optional album bind
- Light/Dark theme toggle (?theme=light / dark)
- Minimal Admin page (USER list). Admin created from env vars.

## Run locally
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='dev'
# optional Postgres: export DATABASE_URL='postgresql://...'
python app.py
```

## Render
Create Web Service from this repo.
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`
- **Env Vars**:
  - `SECRET_KEY` — random string
  - `DATABASE_URL` — your Render Postgres URL (or omit to use SQLite; note: uploads are ephemeral)
  - `ADMIN_USERNAME` / `ADMIN_PASSWORD` — to auto-create admin
  - `RENDER` = `1` (enables /tmp uploads)

Uploads are stored in `/tmp/uploads` on Render (ephemeral). For persistence use S3 or a paid disk.
