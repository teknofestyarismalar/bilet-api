FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev tesseract-ocr-tur poppler-utils ghostscript

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
