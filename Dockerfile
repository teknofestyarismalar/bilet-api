FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y tesseract-ocr libtesseract-dev poppler-utils && \
    pip install --no-cache-dir Flask==3.1.1 PyPDF2==3.0.1 pytesseract==0.3.13 pdf2image==1.17.0 Pillow==11.2.1

COPY . /app
WORKDIR /app

CMD ["python", "app.py"]
