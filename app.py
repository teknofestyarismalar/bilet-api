import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import re

app = Flask(__name__)

KEYWORDS = [
    "TOPLAM (TL) (KDV DAHİL)",
    "Toplam Tutar",
    "ÜCRET (Price)",
    "Ödenecek Tutar",
    "TOPLAM BEDEL (TL)/Total: [KDV DAHİL]",
    "KDV DAHİL ÜCRET / FARE"
]

@app.route('/')
def index():
    return "OK"

@app.route('/analyze', methods=['POST'])
def analyze_pdf():
    try:
        declared_amount = float(request.headers.get('Declared-Amount', '0'))
        if not request.data:
            return jsonify({"valid": False, "issues": ["PDF verisi alınamadı."]})

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(request.data)

        text = extract_text_from_pdf(temp_pdf.name)
        extracted_amount = extract_amount_from_text(text)

        if extracted_amount == 0:
            return jsonify({
                "valid": False,
                "issues": ["PDF okunamadı veya tutar bulunamadı."]
            })

        if abs(extracted_amount - declared_amount) > 1:
            return jsonify({
                "valid": False,
                "issues": [f"Yüklenen bilet tutarı ({extracted_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor"]
            })

        return jsonify({"valid": True})

    except Exception as e:
        return jsonify({
            "valid": False,
            "issues": [f"PDF okunamadı: {str(e)}"]
        })

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        if any(keyword.lower() in text.lower() for keyword in KEYWORDS):
            return text

        # OCR fallback
        images = convert_from_path(pdf_path)
        ocr_text = ""
        for image in images:
            ocr_text += pytesseract.image_to_string(image, lang="tur")
        return ocr_text

    except Exception as e:
        raise Exception("OCR hatası: " + str(e))

def extract_amount_from_text(text):
    pattern = r"(?:" + "|".join(re.escape(k) for k in KEYWORDS) + r")\D{0,20}(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})"
    matches = re.findall(pattern, text, re.IGNORECASE)
    if not matches:
        return 0
    cleaned = matches[-1].replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except:
        return 0

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
