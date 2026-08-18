FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN useradd -m -u 1000 castopia \
    && chown -R castopia:castopia /app \
    && chmod +x /app/start.sh

USER castopia

CMD ["/app/start.sh"]

