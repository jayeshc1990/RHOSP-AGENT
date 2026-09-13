FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# clouds.yaml is mounted at runtime (see docker-compose.yml) - never baked into the image.
ENV OS_CLIENT_CONFIG_FILE=/config/clouds.yaml

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
