FROM python:3.10-slim

# Sistem bağımlılıkları
RUN apt-get update && \
    apt-get install -y tesseract-ocr libgl1 libglib2.0-0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Gereksinimler ve kod
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Uygulama başlat
CMD ["python", "app.py"]
