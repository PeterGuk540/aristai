FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL}
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies including Playwright browser deps
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    # Playwright/Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install Python dependencies
COPY requirements.txt constraints.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt -c constraints.txt --prefer-binary

# Install Playwright browsers (Chromium for Chrome MCP)
RUN playwright install chromium

# Copy application code
COPY . .

# Default command (overridden in docker-compose)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
