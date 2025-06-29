import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from difflib import SequenceMatcher
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

def is_similar(a, b, threshold=0.8):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold

@app.route('/')
def index():
    return "OK"

@app.route('/analyze', methods=['POST'])
def analyze_pdf():
    try:
        file = request.files.get('pdf')
        declared_amount = request.form.get('declared_amount')
        full_name = request.form.get('full_name')

        if not file or not declared_amount or not full_name:
            return jsonify({"valid": False, "issues": ["Eksik veri"]}), 400

        declared_amount = float(declared_amount)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)

        text_pages = extract_text_by_page(temp_pdf.name)
        all_text = "\n".join(text_pages)

        amounts = extract_all_amounts(text_pages)
        total_amount = sum(amounts)

        extracted_name = extract_name(all_text)
        similarity = SequenceMatcher(None, full_name.lower(), extracted_name.lower()).ratio()

        issues = []
        if not amounts:
            issues.append("PDF okunamadı veya tutar bulunamadı.")
        if similarity < 0.8:
            issues.append("Belgedeki isim formdaki isimle uyuşmuyor.")

        return jsonify({
            "valid": len(issues) == 0 and abs(total_amount - declared_amount) <= 1,
            "issues": issues,
            "extracted_name": extracted_name
        })

    except Exception as e:
        return jsonify({"valid": False, "issues": [f"OCR da başarısız: {str(e)}"]})

def extract_text_by_page(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        return [page.extract_text() or "" for page in reader.pages]
    except:
        images = convert_from_path(pdf_path)
        return [pytesseract.image_to_string(img, lang="tur") for img in images]

def extract_all_amounts(text_pages):
    seen_dates = set()
    amounts = []

    for text in text_pages:
        lines = text.splitlines()
        amount = None
        date = None

        for line in lines:
            if any(kw.lower() in line.lower() for kw in KEYWORDS):
                match = re.search(r"(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})", line)
                if match:
                    raw = match.group(1).replace(".", "").replace(",", ".")
                    try:
                        amount = float(raw)
                    except:
                        continue

            date_match = re.search(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", line)
            if date_match:
                date = date_match.group()

        if amount and date and date not in seen_dates:
            seen_dates.add(date)
            amounts.append(amount)

    return amounts

def extract_name(text):
    lines = text.splitlines()
    for line in lines:
        if "Beyza Kurt" in line:
            return "Beyza Kurt"
        if any(k in line for k in ["Adı Soyadı", "Yolcu", "Ad-Soyad"]):
            match = re.search(r"(Beyza\s+Kurt)", line)
            if match:
                return match.group(1)
            parts = re.split(r"[:\-]", line)
            if len(parts) > 1:
                return parts[-1].strip()
            words = line.strip().split()
            if len(words) >= 2:
                return words[-2] + " " + words[-1]
    return "Belirlenemedi"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
