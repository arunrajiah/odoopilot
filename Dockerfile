FROM python:3.11-slim

WORKDIR /app

# Install deps first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . 2>/dev/null || true

COPY odoopilot/ odoopilot/
RUN pip install --no-cache-dir -e .

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "odoopilot.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
