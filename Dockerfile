# Base image — slim keeps it small
FROM python:3.11-slim

# build-essential — needed to compile some pip packages (e.g. psycopg2-binary deps)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first — layer cache means pip only reruns if requirements change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

# Default command — overridden per service in docker-compose.yml
CMD ["python", "server.py"]
