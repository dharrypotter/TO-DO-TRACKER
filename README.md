# TaskFlow — TODO Tracker

A polished, multi-user TODO tracker built with Flask. Sign up, organise your day, and watch your streaks grow.

## Features

- User accounts with secure password hashing (sign up, log in, log out)
- Each user has their own private list of tasks and categories
- Mark tasks complete (toggle) with strikethrough styling
- Edit task title, description, priority, due date, and category
- Priority levels (High / Medium / Low) with color-coded indicators
- Due dates with automatic overdue highlighting
- Categories with custom colors — three sensible defaults seeded on signup (Work, Personal, Errands)
- Filter the list by status (active / completed / all), priority, or category
- Search across titles and descriptions
- Reorder tasks with up / down buttons
- Dashboard with completion rate, daily streak, 14-day activity chart, and per-category breakdown
- Dark mode toggle (saved to localStorage so it sticks)
- Mobile-responsive layout
- Deployment-ready: Procfile, Dockerfile, gunicorn, env-var configuration

## Quick start (local dev)

```bash
pip install -r requirements.txt
cp .env.example .env          # optional, lets you override SECRET_KEY etc.
python app/server.py
```

Then visit http://localhost:5000 — sign up, log in, and start adding tasks.

## Running tests

```bash
pip install -r requirements.txt
pytest -v
```

## Configuration (env vars)

| Variable        | Default                | Purpose                             |
| --------------- | ---------------------- | ----------------------------------- |
| `SECRET_KEY`    | `dev-secret-change-me` | Flask session signing key. **Change this in production.** |
| `DATABASE_PATH` | `app/todo.db`          | Where the SQLite DB lives           |
| `PORT`          | `5000`                 | Port to bind to                     |
| `FLASK_DEBUG`   | unset                  | Set to `1` to enable debug mode     |

## Deploy for free

The app ships with a `Procfile`, `runtime.txt`, and `Dockerfile`, so it works on every common free-tier Python host.

### Render.com

1. Push this repo to GitHub.
2. On Render: **New → Web Service**, point it at your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn --chdir app server:app`
5. Add environment variable `SECRET_KEY` (any long random string).
6. Add a persistent disk if you want the DB to survive deploys (mount it at `/var/data` and set `DATABASE_PATH=/var/data/todo.db`).

### Railway / Fly.io

Both pick up the `Procfile` automatically. Set `SECRET_KEY` as a secret/env var, deploy, done.

### Docker (anywhere)

```bash
docker build -t taskflow .
docker run -p 8000:8000 -e SECRET_KEY=... -v $(pwd)/data:/app/data taskflow
```

The mounted `data/` folder keeps the SQLite DB across container restarts.

### Note on SQLite + serverless

The app uses SQLite, which is great for simple deploys but doesn't survive serverless cold starts (e.g. Vercel) or environments without a persistent disk. For those, mount a volume or swap in Postgres.

## Project layout

```
app/
  server.py           # Flask app, routes, DB helpers, auth
  schema.sql          # Tables: user, category, todo
  templates/          # Jinja templates
  static/css/         # Custom styling + dark mode
tests/
  test_server.py      # pytest suite
requirements.txt
Procfile              # `web: gunicorn …`
runtime.txt           # Python version pin
Dockerfile
.env.example
```
