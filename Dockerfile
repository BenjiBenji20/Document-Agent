FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && grep -vE "pywin32|pywinpty|pypiwin32|wmi" requirements.txt \
    | pip install --no-cache-dir -r /dev/stdin

COPY . .

ENV PORT=8080

EXPOSE 8080

CMD uvicorn src.main:app --host 0.0.0.0 --port $PORT --log-level debug
