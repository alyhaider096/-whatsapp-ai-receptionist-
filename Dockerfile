FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway (and most PaaS hosts) assign a dynamic port via $PORT and health-check
# exactly that port -- hardcoding 8000 here means the health check never
# succeeds and the platform crash-loops the deploy. Default to 8000 for local
# `docker run` where $PORT isn't set.
ENV PORT=8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
