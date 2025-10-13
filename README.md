# Bachata Music — VK-style мини-соцсеть

Мини-соцсеть для твоего сообщества: лента, профили, посты, лайки, комментарии.
Стек: Flask + SQLite + Bootstrap.

## Быстрый запуск (локально или на сервере)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask --app app.py init-db
python app.py
```
Открой: http://127.0.0.1:5000

## Прод на сервере (Gunicorn)
```bash
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

## NGINX + HTTPS (пример)
Поставь nginx и certbot:
```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

Создай конфиг `/etc/nginx/sites-available/bachata`:
```
server {
    server_name bachata-music.ru bachata-music.com;
    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Активируй и перезапусти:
```bash
sudo ln -s /etc/nginx/sites-available/bachata /etc/nginx/sites-enabled/bachata
sudo nginx -t && sudo systemctl restart nginx
```

Выдай сертификаты:
```bash
sudo certbot --nginx -d bachata-music.ru -d www.bachata-music.ru -d bachata-music.com -d www.bachata-music.com
```

## systemd сервис (чтобы работало после перезагрузки)
Файл `/etc/systemd/system/bachata.service`:
```
[Unit]
Description=Bachata Music Flask App
After=network.target

[Service]
User=www-data
WorkingDirectory=/home/USERNAME/bachata_site
Environment="SECRET_KEY=change-me"
ExecStart=/home/USERNAME/bachata_site/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bachata
sudo systemctl start bachata
```

Готово! Дальше можно добавлять загрузку фото, подписки, роли админов и т.д.
