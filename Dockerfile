FROM python:3.10-slim

# Sistem paketlerini yükle
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && apt-get clean

# Çalışma dizini
WORKDIR /app

# Gerekli dosyaları kopyala
COPY . .

# Python bağımlılıklarını kur
RUN pip install --no-cache-dir -r requirements.txt

# Uygulamayı başlat
CMD ["python", "app.py"]
