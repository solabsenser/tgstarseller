FROM python:3.11

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir fastapi uvicorn aiogram requests psycopg2-binary

CMD sh -c "uvicorn backend:app --host 0.0.0.0 --port ${PORT:-8080} & python bot.py"
