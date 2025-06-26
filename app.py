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
        if 'pdf' not in request.files or 'declared_amount' not in request.form:
            return jsonify({
                "valid": False,
                "issues": ["Eksik veri"]
            })

        file = request.files['pdf']
        declared_amount = float(request.form['declared_amount'])

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)
            pdf_path = temp_pdf.name

        # Metin çıkarma
        text = extract_text_from_pdf(pdf_path)

        # Metni dosyaya kaydetmek istersen:
        # with open("ocr_output.txt", "w", encoding="utf-8") as f:
        #     f.write(text)

        extracted_amounts = extract_amounts_from_text(text)

        if not extracted_amounts:
            return jsonify({
                "valid": False,
                "issues": ["PDF okunamadı veya tutar bulunamadı."]
            })

        total_extracted = sum(set(extracted_amounts))  # aynı bilet tekrar edilmişse, sadece 1 tanesi alınsın

        if abs(total_extracted - declared_amount) > 1:
            return jsonify({
                "valid": False,
                "issues": [f"Yüklenen bilet tutarı ({total_extracted} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor"]
            })

        return jsonify({"valid": True})

    except Exception as e:
        return jsonify({
            "valid": False,
            "issues": [f"PDF okunamadı: {str(e)}"]
        })

def extract_text_from_pdf(pdf_path):
    try:
        # Önce doğrudan metin çıkar
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        if any(keyword.lower() in text.lower() for keyword in KEYWORDS):
            return text

        # OCR ile dene (daha hızlı hale getirildi)
        images = convert_from_path(pdf_path, dpi=100)
        ocr_text = ""
        for image in images:
            ocr_text += pytesseract.image_to_string(image)
        return ocr_text

    except Exception as e:
        raise Exception("OCR hatası: " + str(e))

def extract_amounts_from_text(text):
    pattern = r"(?:" + "|".join(re.escape(k) for k in KEYWORDS) + r")\D{0,20}(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})"
    matches = re.findall(pattern, text, re.IGNORECASE)
    results = []
    for match in matches:
        try:
            cleaned = match.replace(".", "").replace(",", ".")
            amount = float(cleaned)
            results.append(amount)
        except:
            continue
    return results

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
