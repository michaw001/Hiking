FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN rm -f .env .env.docker

RUN mkdir -p /app/data /app/user_data

EXPOSE 8088

ENV FLASK_APP=run.py \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health')" || exit 1

CMD ["sh", "-c", "flask db upgrade && flask create-admin --username \"$ADMIN_USERNAME\" --email \"$ADMIN_EMAIL\" --if-none && gunicorn run:app --workers 3 --bind 0.0.0.0:8088 --timeout 120 --access-logfile - --error-logfile -"]
