FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# SQLite DB will live here (mount this if you want persistence)
ENV DATABASE_PATH=/app/data/todo.db
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["gunicorn", "--chdir", "app", "server:app", "--bind", "0.0.0.0:8000"]
