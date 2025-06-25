FROM python:3.10-slim

# Sistemi güncelle, poppler ve tesseract + turkish dil dosyasını yükle
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-tur \
    poppler-utils \
    && apt-get clean

# Gereken Python paketlerini yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Uygulamayı başlat
CMD ["python", "app.py"]
