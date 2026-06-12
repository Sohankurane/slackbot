# Multi-tenant Slack bot platform — single-container image
FROM python:3.13-slim

# Don't buffer logs; don't write .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (cached layer — rebuilds are fast
# unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

EXPOSE 8000

# Container healthcheck — pings the app's /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# No --reload in containers; bind 0.0.0.0 so the port mapping works
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]