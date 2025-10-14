-- users
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user', -- 'user' | 'admin'
  avatar TEXT,                       -- путь к файлу
  bio TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- sessions handled by Flask-Login (в БД не нужно)

-- profiles (если хочешь отделить от users — пока не нужно)

-- posts (на следующей итерации)
