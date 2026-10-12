FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

EXPOSE 8000

# start.sh applies migrations (a hosted database starts empty), optionally
# seeds the demo accounts, then serves on $PORT.
CMD ["./start.sh"]
