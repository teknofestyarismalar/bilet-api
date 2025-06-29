import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import re
from difflib import SequenceMatcher

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
            return jsonify({"valid": False, "issues": ["Eksik veri"]})

        pdf_file = request.files['pdf']
        declared_amount = float(request.form['declared_amount'])
        full_name = request.form.get("full_name", "").strip()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            pdf_file.save(temp_pdf.name)
            pdf_path = temp_pdf.name

        # OCR ile tüm sayfaları işle
        pages_text = extract_text_per_page(pdf_path)

        seen_tickets = set()
        total_amount = 0
        all_names = []
        issues = []

        for text in pages_text:
            name = extract_name(text)
            if name:
                all_names.append(name)

            date = extract_date(text)
            amount = extract_amount_from_text(text)

            # Aynı tarihli bilet zaten varsa sayma
            if date and date in seen_tickets:
                continue
            if date:
                seen_tickets.add(date)

            total_amount += amount

        # İsim uyuşmazlığı kontrolü
        matched_name = all_names[0] if all_names else ""
        similarity = SequenceMatcher(None, full_name.lower(), matched_name.lower()).ratio()

        issues = []

        if similarity < 0.8:
            issues.append("Belgedeki isim formdaki isimle uyuşmuyor.")

        if abs(total_amount - declared_amount) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

        if not total_amount:
            issues.append("PDF okunamadı veya tutar bulunamadı.")

        return jsonify({
            "valid": len(issues) == 0,
            "issues": issues,
            "matched_name": matched_name
        })

    except Exception as e:
        return jsonify({
            "valid": False,
            "issues": [f"PDF okunamadı: {str(e)}"]
        })


def extract_text_per_page(pdf_path):
    images = convert_from_path(pdf_path)
    texts = []
    for img in images:
        text = pytesseract.image_to_string(img, lang="tur")
        texts.append(text)
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

def extract_name(text):
    # Muhtemelen ad soyad büyük harfli, bu satırı filtreleyebiliriz
    lines = text.split("\n")
    candidates = [line.strip() for line in lines if re.match(r"^[A-ZÇĞİÖŞÜ ]{5,}$", line.strip())]
    return candidates[0] if candidates else ""

def extract_date(text):
    match = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", text)
    return match.group() if match else None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
