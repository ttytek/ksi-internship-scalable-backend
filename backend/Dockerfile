FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE $APP_PORT

CMD uvicorn ksi.main:app --host 0.0.0.0 --port $APP_PORT
