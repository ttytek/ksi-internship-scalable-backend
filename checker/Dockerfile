FROM python:3.12-slim

WORKDIR /app

COPY backend /app/backend
COPY checker /app/checker

RUN pip install --no-cache-dir ./backend ./checker

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "ksi_checker"]
