# Override via build-arg if Docker Hub is unreachable (TLS timeout): e.g. a registry mirror or pre-pulled tag.
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

# LibreOffice Writer (headless) — used to update STYLEREF/SEQ/REF fields before parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
