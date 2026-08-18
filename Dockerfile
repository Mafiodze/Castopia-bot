FROM python:3.12-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Python-зависимости
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . .

# Создаём пользователя для запуска приложения
RUN useradd -m -u 1000 castopia \
    && chown -R castopia:castopia /app \
    && chmod +x /app/start.sh

USER castopia

# Запускаем единый entrypoint
CMD ["/app/start.sh"]
