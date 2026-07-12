FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /code

# Dependencias del sistema mínimas para compilar wheels si hiciera falta
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# entrypoint.sh espera a la BD, aplica migraciones y arranca uvicorn
RUN chmod +x ./entrypoint.sh
CMD ["./entrypoint.sh"]
