# Skillik

Образовательная платформа — мини онлайн-школа по **математике** и **информатике** для учеников 5–7 классов.

Один преподаватель (администратор), ученики и родительский доступ.  
Стек: **FastAPI** · **SQLite** · **Jinja2** · HTML/CSS · минимальный JS.

## Возможности

| Роль | Что умеет |
|------|-----------|
| **Админ** | Ученики, уроки, ДЗ, темы, календарь, шаблоны, магазин XP, сообщения, статистика, экспорт CSV |
| **Ученик** | Прогресс, стрик, уроки, ДЗ, карта знаний, тренировка, достижения, магазин, чат, срочный вопрос |
| **Родитель** | Прогресс ребёнка, посещаемость, оценки, стрик (без чатов и решений) |

Геймификация: XP, уровни (Новичок → Легенда), бейджи, стрик с заморозкой, магазин (аватары, рамки, отсрочка ДЗ, акцент).

## Быстрый старт (локально)

```bash
cd skillik
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # или: cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Откройте: http://127.0.0.1:8000

### Демо-аккаунты (создаются при первом запуске)

| Роль | Логин | Пароль |
|------|-------|--------|
| Админ | `admin` | `admin123` |
| Ученик | `ivan` | `ivan123` |
| Родитель | `parent_ivan` | `parent123` |

**Смените пароли в продакшене.**

## Запуск на VPS (Ubuntu)

```bash
# 1. Система
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx

# 2. Проект
sudo mkdir -p /var/www/skillik
sudo chown $USER:$USER /var/www/skillik
# скопируйте файлы проекта в /var/www/skillik
cd /var/www/skillik
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Секреты
cp .env.example .env
nano .env   # обязательно: SECRET_KEY=<длинная случайная строка>, DEBUG=false

# 4. systemd
sudo nano /etc/systemd/system/skillik.service
```

Содержимое unit-файла:

```ini
[Unit]
Description=Skillik educational platform
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/skillik
Environment="PATH=/var/www/skillik/.venv/bin"
ExecStart=/var/www/skillik/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo chown -R www-data:www-data /var/www/skillik
sudo systemctl daemon-reload
sudo systemctl enable --now skillik
```

### Nginx (прокси)

```nginx
server {
    listen 80;
    server_name skillik.example.com;

    client_max_body_size 25M;

    location /static/ {
        alias /var/www/skillik/app/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/skillik /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# HTTPS: sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx -d skillik.example.com
```

## Переход на PostgreSQL

В `.env`:

```env
DATABASE_URL=postgresql+psycopg2://user:pass@localhost/skillik
```

Установите драйвер: `pip install psycopg2-binary`  
Модели SQLAlchemy совместимы; для миграций удобно подключить Alembic.

## Структура проекта

```
skillik/
├── app/
│   ├── main.py              # FastAPI entry
│   ├── config.py
│   ├── database.py
│   ├── security.py          # bcrypt, JWT, CSRF
│   ├── deps.py
│   ├── models/              # SQLAlchemy
│   ├── routers/             # auth, admin, student, parent
│   ├── services/            # XP, seed, auto-check, export
│   ├── templates/           # Jinja2
│   └── static/              # CSS, JS, uploads
├── requirements.txt
├── .env.example
└── README.md
```

## Безопасность

- Пароли: **bcrypt** (passlib)
- Сессии: **JWT** в HttpOnly cookie
- **CSRF** на POST-формах (HMAC cookie + hidden field)
- SQLAlchemy ORM → защита от SQL-инъекций
- Экранирование Jinja2 → XSS
- Заголовки: CSP, X-Frame-Options, nosniff
- Загрузки: whitelist расширений, лимит размера, безопасные имена

## Дизайн

- Primary `#1e3a5f` · Accent `#2a9d8f` · BG `#f8fafc`
- Шрифты: Inter + Source Serif 4
- Тёмная тема (кнопка в шапке / preference в профиле)
- Адаптив: sidebar → drawer на телефоне

## Лицензия

Учебный / личный проект. Используйте свободно.
