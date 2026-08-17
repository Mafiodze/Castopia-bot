FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 castopia && chown -R castopia:castopia /app
USER castopia

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import discord, aiogram; print('OK')" || exit 1

# Default to Discord bot, but can be overridden
CMD ["python", "dsc/bot.py"]
