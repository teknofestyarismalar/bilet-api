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

DATE_TIME_PATTERN = r"\b\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}\b"  # Tarih ve saat birlikte

@app.route('/')
def index():
    return "OK"

@app.route('/analyze', methods=['POST'])
def analyze_pdf():
    try:
        if 'pdf' not in request.files or 'declared_amount' not in request.form:
            return jsonify({"valid": False, "issues": ["Eksik veri"]})

        file = request.files['pdf']
        declared_amount = float(request.form['declared_amount'])
        full_name = request.form.get('full_name', "").strip().lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)

        texts = extract_texts_per_page(temp_pdf.name)

        all_names = set()
        all_amounts = []
        seen_datetimes = set()

        for text in texts:
            text_lower = text.lower()
            if full_name not in text_lower:
                found_name = find_name(text)
                if found_name:
                    all_names.add(found_name)

            amount = extract_amount_from_text(text)
            dt = extract_datetime(text)

            if amount > 0 and dt not in seen_datetimes:
                all_amounts.append(amount)
                seen_datetimes.add(dt)

        total = sum(all_amounts)

        if len(all_names) > 1:
            return jsonify({
                "valid": False,
                "issues": ["Farklı kişilere ait biletler bulundu."]
            })

        if full_name and all_names and full_name not in {n.lower() for n in all_names}:
            return jsonify({
                "valid": False,
                "issues": ["Belgedeki isim formdaki isimle uyuşmuyor."]
            })

        if total == 0:
            return jsonify({
                "valid": False,
                "issues": ["PDF okunamadı veya tutar bulunamadı."]
            })

        if abs(total - declared_amount) > 1:
            return jsonify({
                "valid": False,
                "issues": [f"Yüklenen bilet tutarı ({total} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor"]
            })

        return jsonify({"valid": True})

    except Exception as e:
        return jsonify({"valid": False, "issues": [f"PDF okunamadı: {str(e)}"]})

def extract_texts_per_page(pdf_path):
    reader = PdfReader(pdf_path)
    texts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if any(k.lower() in text.lower() for k in KEYWORDS):
            texts.append(text)
        else:
            # OCR fallback
            images = convert_from_path(pdf_path, dpi=200, first_page=reader.pages.index(page)+1, last_page=reader.pages.index(page)+1)
            ocr_text = pytesseract.image_to_string(images[0], lang="tur")
            texts.append(ocr_text)
    return texts

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

def extract_datetime(text):
    match = re.search(DATE_TIME_PATTERN, text)
    return match.group() if match else None

def find_name(text):
    # Basitçe büyük harfli tam isim seç
    matches = re.findall(r"[A-ZÇĞİÖŞÜ]{2,}(?:\s+[A-ZÇĞİÖŞÜ]{2,}){1,3}", text)
    return matches[0] if matches else None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
