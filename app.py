import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import difflib
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
        if 'pdf' not in request.files or 'declared_amount' not in request.form or 'full_name' not in request.form:
            return jsonify({"valid": False, "issues": ["Eksik veri"]}), 400

        file = request.files['pdf']
        declared_amount = float(request.form['declared_amount'])
        form_name = request.form['full_name']

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)

        text = extract_text_from_pdf(temp_pdf.name)

        # OCR çıktısını loglamak istersen
        # with open("ocr_debug.txt", "w", encoding="utf-8") as f:
        #     f.write(text)

        extracted_amount = extract_amount_from_text(text)
        matched_name, similarity = find_best_matching_name(form_name, text)

        if similarity < 0.80:
            return jsonify({
                "valid": False,
                "issues": ["Belgedeki isim formdaki isimle uyuşmuyor."],
                "matched_name": matched_name,
                "similarity": similarity
            })

        if extracted_amount == 0:
            return jsonify({
                "valid": False,
                "issues": ["PDF okunamadı veya tutar bulunamadı."],
                "matched_name": matched_name,
                "similarity": similarity
            })

        if abs(extracted_amount - declared_amount) > 1:
            return jsonify({
                "valid": False,
                "issues": [f"Yüklenen bilet tutarı ({extracted_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor"],
                "matched_name": matched_name,
                "similarity": similarity
            })

        return jsonify({
            "valid": True,
            "matched_name": matched_name,
            "similarity": similarity
        })

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
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if any(k.lower() in text.lower() for k in KEYWORDS):
            return text

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

def find_best_matching_name(form_name, text):
    best_ratio = 0
    best_match = ""
    for line in text.split("\n"):
        ratio = difflib.SequenceMatcher(None, form_name.lower(), line.strip().lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = line.strip()
    return best_match, best_ratio

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
