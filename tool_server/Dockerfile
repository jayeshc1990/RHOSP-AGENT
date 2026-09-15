FROM python:3.12-slim

WORKDIR /app

# netifaces (pulled in transitively by openstacksdk) has no prebuilt wheel for
# every Python version, so pip falls back to compiling it from source - needs a
# C compiler, which the slim base image doesn't have by default.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# clouds.yaml is mounted at runtime (see docker-compose.yml) - never baked into the image.
ENV OS_CLIENT_CONFIG_FILE=/config/clouds.yaml

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
