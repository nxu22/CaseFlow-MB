# Slim image keeps the final container ~150MB instead of ~1GB.
FROM python:3.12-slim

WORKDIR /app

# Copy requirements first so Docker caches the pip install layer
# as long as requirements.txt doesn't change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the rest of the source code.
COPY . .

EXPOSE 8000

# --reload is for development. Day 3 production will use gunicorn with workers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
