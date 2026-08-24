FROM python:3.11-slim

WORKDIR /app

# Install ping, curl and other utilities if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY infrastructure/docker/requirements-tester.txt .
RUN pip install --no-cache-dir -r requirements-tester.txt

COPY test_media_pipeline.py .

EXPOSE 8005

CMD ["python", "test_media_pipeline.py"]
