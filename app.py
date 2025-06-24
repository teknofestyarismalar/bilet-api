from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import re
from datetime import datetime
from rapidfuzz import fuzz

app = Flask(__name__)

# Kabul edilen tarih aralığı
ALLOWED_DATE_START = datetime(2025, 4, 26)
ALLOWED_DATE_END = datetime(2025, 5, 7)

# PDF içinden metni çıkar
def extract_text_from_pdf(file_bytes):
    images = convert_from_bytes(file_bytes.read())
    text = ""
    for image in images:
        text += pytesseract.image_to_string(image, lang='tur')
    return text

# Sadece "Toplam Tutar" satırından tutar çek
def extract_amount(text):
    lines = text.splitlines()
    for line in lines:
        if 'toplam tutar' in line.lower():
            match = re.search(r'(\d+[.,]\d{2})', line)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except:
                    continue
    return 0.0

# Sadece "hareket" kelimesi geçen satırlardan tarih ayıkla
def extract_dates(text):
    lines = text.splitlines()
    for line in lines:
        if 'hareket' in line.lower():
            match = re.search(r'(\d{2}[./-]\d{2}[./-]\d{4})', line)
            if match:
                try:
                    date = datetime.strptime(match.group(1), '%d.%m.%Y')
                    if ALLOWED_DATE_START <= date <= ALLOWED_DATE_END:
                        return [date]
                except:
                    continue
    return []

# Ad-soyad benzerliğini kontrol et (fuzzy match)
def fuzzy_match(a, b):
    return fuzz.partial_ratio(a.lower(), b.lower()) > 80

# Ana API endpoint
@app.route("/analyze", methods=["POST"])
def analyze_pdf():
    file = request.files.get("file")
    full_name = request.form.get("full_name", "").strip()
    declared_amount = float(request.form.get("declared_amount", "0"))

    if not file or not full_name:
        return jsonify({"valid": False, "issues": ["Eksik dosya veya ad-soyad bilgisi."]})

    text = extract_text_from_pdf(file)

    # Kontroller
    name_match = fuzzy_match(full_name, text)
    extracted_total = extract_amount(text)
    amount_match = abs(extracted_total - declared_amount) <= 1
    valid_dates = extract_dates(text)
    date_match = len(valid_dates) > 0

    # Geri bildirim nedenleri
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

# Sunucuyu başlat
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
