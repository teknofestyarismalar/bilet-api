import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
import re

from PIL import Image

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
        if 'file' not in request.files or 'declared_amount' not in request.form or 'full_name' not in request.form:
            return jsonify({"valid": False, "issues": ["Eksik veri"]})

        file = request.files['file']
        declared_amount = float(request.form['declared_amount'])
        full_name = request.form['full_name'].strip()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)

        text = extract_text_from_pdf(temp_pdf.name).replace("\f", "\n===PAGE===\n")

        total_amount, detected_names = extract_info_from_text(text, full_name)

        issues = []

        # 👤 İsim uyuşmazlığı kontrolü
        mismatching_names = [name for name in detected_names if name.lower() != full_name.lower()]
        if mismatching_names:
            issues.append("PDF dosyasında birden fazla kişiye ait bilet tespit edildi veya ad soyad uyuşmuyor.")

        # 💰 Tutar kontrolü
        if total_amount == 0:
            issues.append("PDF okunamadı veya tutar bulunamadı.")
        elif abs(total_amount - declared_amount) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

        if issues:
            return jsonify({"valid": False, "issues": issues})
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
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n===PAGE===\n"
        
        if any(keyword.lower() in text.lower() for keyword in KEYWORDS):
            return text

        # PDF okunamıyorsa OCR dene
        images = convert_from_path(pdf_path)
        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang="tur") + "\n===PAGE===\n"
        return ocr_text

    except Exception as e:
        raise Exception("OCR hatası: " + str(e))


def extract_info_from_text(text, full_name):
    pages = text.split("===PAGE===")
    detected_names = set()
    trips = set()
    total_amount = 0

    for page in pages:
        page_lower = page.lower()
        if full_name.lower() not in page_lower:
            # Başka bir isim olabilir
            names = re.findall(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+", page)
            detected_names.update(names)
        else:
            detected_names.add(full_name)

        for keyword in KEYWORDS:
            pattern = re.escape(keyword) + r"\D{0,20}(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})"
            matches = re.findall(pattern, page, re.IGNORECASE)
            for m in matches:
                try:
                    cleaned = m.replace(".", "").replace(",", ".")
                    amount = float(cleaned)

                    # Aynı bileti tekrar toplama: tarih + saat ile eşle
                    date_match = re.search(r"\d{2}/\d{2}/\d{4}", page)
                    time_match = re.search(r"\d{2}:\d{2}", page)
                    trip_key = (date_match.group() if date_match else '', time_match.group() if time_match else '')
                    if trip_key not in trips:
                        trips.add(trip_key)
                        total_amount += amount
                except:
                    continue

    return total_amount, detected_names


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
