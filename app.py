from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import re
from datetime import datetime
from rapidfuzz import fuzz

app = Flask(__name__)

ALLOWED_DATE_START = datetime(2025, 4, 26)
ALLOWED_DATE_END = datetime(2025, 5, 7)

def extract_text_from_pdf(file_bytes):
    images = convert_from_bytes(file_bytes.read())
    text = ""
    for image in images:
        text += pytesseract.image_to_string(image, lang='tur')
    return text

def extract_amount(text):
    lines = text.splitlines()
    total = 0.0
    for line in lines:
        if 'toplam' in line.lower() or 'bilet' in line.lower():
            matches = re.findall(r'(\d{1,5}[.,]?\d{0,2})', line)
            for match in matches:
                try:
                    normalized = match.replace('.', '').replace(',', '.')
                    amount = float(normalized)
                    if 0 < amount < 5000:  # aşırı büyükleri hariç tut
                        total += amount
                except:
                    continue
    return round(total, 2)

def extract_dates(text):
    date_matches = re.findall(r'\b\d{2}[./-]\d{2}[./-]\d{4}\b', text)
    valid_dates = []
    for date_str in date_matches:
        try:
            date = datetime.strptime(date_str, "%d.%m.%Y")
        except:
            try:
                date = datetime.strptime(date_str, "%d/%m/%Y")
            except:
                continue
        if ALLOWED_DATE_START <= date <= ALLOWED_DATE_END:
            valid_dates.append(date)
    return valid_dates

def fuzzy_match(a, b):
    return fuzz.partial_ratio(a.lower(), b.lower()) > 80

@app.route("/analyze", methods=["POST"])
def analyze_pdf():
    file = request.files.get("file")
    full_name = request.form.get("full_name", "").strip()
    declared_amount = float(request.form.get("declared_amount", "0"))

    if not file or not full_name:
        return jsonify({"valid": False, "issues": ["Eksik dosya veya ad-soyad bilgisi."]})

    text = extract_text_from_pdf(file)

    # Ad-soyad kontrolü
    name_match = fuzzy_match(full_name, text)

    # Tutar kontrolü
    extracted_total = extract_amount(text)
    amount_match = abs(extracted_total - declared_amount) <= 1

    # Tarih kontrolü
    valid_dates = extract_dates(text)
    date_match = len(valid_dates) > 0

    issues = []
    if not name_match:
        issues.append("Fatura üzerindeki ad-soyad ile formdaki ad-soyad uyuşmuyor.")
    if not date_match:
        issues.append(f"Fatura tarihi desteklenen tarih aralığında değil ({ALLOWED_DATE_START.strftime('%d.%m.%Y')} - {ALLOWED_DATE_END.strftime('%d.%m.%Y')})")
    if not amount_match:
        issues.append(f"Yüklenen bilet tutarı ({extracted_total} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

    return jsonify({
        "valid": len(issues) == 0,
        "issues": issues
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
