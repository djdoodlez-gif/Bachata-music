BACHATAGRAM — минимальная соцсеть (Flask + PostgreSQL)

Деплой на Render:
1) PostgreSQL (Free) → Internal Database URL.
2) Web Service → Settings → Environment:
   - DATABASE_URL = (Internal Database URL)
   - SECRET_KEY = длинная случайная строка
   - ADMIN_USERNAME = твой_логин_админа
   - ADMIN_PASSWORD = твой_пароль_админа
   - (опц.) ADMIN_EMAIL, ADMIN_DISPLAY_NAME
3) Start Command: gunicorn app:app  (или оставь Procfile)
4) Manual Deploy → Deploy latest commit
5) Проверка:
   - /health → "ok"
   - /_diag → JSON с db_ok=true
   - /auth/login → регистрация/вход
   - /admin → доступен только админу
