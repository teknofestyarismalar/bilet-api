FROM python:3.10-slim

# Sisteme gerekli paketleri kur
RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev poppler-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Dosyaları kopyala
COPY . /app

# Python bağımlılıklarını kur
RUN pip install --no-cache-dir -r requirements.txt

# Uygulamayı başlat
CMD ["python", "app.py"]
