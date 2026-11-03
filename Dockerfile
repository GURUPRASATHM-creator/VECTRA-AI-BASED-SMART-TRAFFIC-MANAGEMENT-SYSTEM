FROM python:3.11-slim

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY contracts /contracts
COPY camera-ingestion-service/requirements.txt /srv/requirements.txt

RUN sed -i 's#-e ../contracts/python#-e /contracts/python#' /srv/requirements.txt \
    && pip install --no-cache-dir -r /srv/requirements.txt

COPY camera-ingestion-service/app /srv/app
COPY camera-ingestion-service/yolov8n.pt /srv/yolov8n.pt

EXPOSE 8200

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]