FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN grep -vE "pywin32|pywinpty|pypiwin32|wmi" requirements.txt \
    | pip install --no-cache-dir -r /dev/stdin

COPY . .

ENV PORT=8080

EXPOSE 8080

CMD uvicorn main:app --host 0.0.0.0 --port $PORT --log-level debug
