FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY odoopilot/ odoopilot/

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "odoopilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
