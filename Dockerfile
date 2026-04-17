FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY pyproject.toml .

RUN pip install --no-cache-dir -e .

# Data directory for SQLite — override via volume mount
RUN mkdir -p /data

CMD ["python", "-m", "inboxagent.main"]
