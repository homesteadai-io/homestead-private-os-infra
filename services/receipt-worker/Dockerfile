FROM python:3.12-slim

WORKDIR /app

COPY services/receipt-worker/app /app/app

CMD ["python", "-m", "app.worker"]

