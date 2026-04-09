FROM python:3.12-slim

WORKDIR /app

# Copy all project files (knowledge base, references, scripts)
COPY . .

# No pip install needed -- stdlib only

CMD ["python3", "scripts/channel_monitor.py"]
