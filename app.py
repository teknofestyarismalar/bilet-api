from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
import io
import re
from datetime import datetime

app = Flask(__name__)

# Geçerli tarih aralığı
MIN_DATE = datetime(2025, 4, 26)
MAX_DATE = datetime(2025, 5, 7)

# OCR ile görselden metin çıkar
def extract_text_from_pdf(file_stream):
    text = ""
    images = convert_from_bytes(file_stream.read())
    for img in images:
        text += pytesseract.image_to_string(img, lang='tur') + "\n"
    return text

# Yalnızca belirli ifadeleri içeren satırlardan tutar çek
def extract_amounts(text):
    keywords = [
        "TOPLAM (TL) (KDV DAHİL)",
        "Toplam Tutar",
        "ÜCRET (Price)",
        "Ödenecek Tutar",
        "TOPLAM BEDEL (TL)/Total",
        "KDV DAHİL ÜCRET / FARE"
    ]
    
    amounts = []
    for line in text.splitlines():
        for keyword in keywords:
            if keyword.lower() in line.lower():
                match = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', line)
                if match:
                    cleaned = match.group().replace('.', '').replace(',', '.')
                    try:
                        amounts.append(float(cleaned))
                    except:
                        continue
    return amounts

# Tarihleri bulur
def extract_dates(text):
    matches = re.findall(r'\d{2}[./-]\d{2}[./-]\d{4}', text)
    dates = []
    for date_str in matches:
        try:
            date = datetime.strptime(date_str.replace('-', '.').replace('/', '.'), '%d.%m.%Y')
            dates.append(date)
        except:
            continue
    return dates

@app.route("/analyze", methods=["POST"])
def analyze_pdf():
    file = request.files.get("file")
    full_name = request.form.get("full_name", "").lower()
    declared_amount = float(request.form.get("declared_amount", "0"))

    if not file or not full_name:
        return jsonify({"valid": False, "issues": ["Eksik dosya veya isim bilgisi."]})

    try:
        text = extract_text_from_pdf(file.stream)
    except Exception as e:
        return jsonify({"valid": False, "issues": [f"PDF okunamadı: {str(e)}"]})

    issues = []

    # İsim kontrolü
    if full_name.lower() not in text.lower():
        issues.append("Ad-Soyad, fatura üzerinde bulunamadı.")

    # Tarih kontrolü
    dates = extract_dates(text)
    if not any(MIN_DATE <= d <= MAX_DATE for d in dates):
        issues.append(f"Fatura tarihi desteklenen tarih aralığında değil ({MIN_DATE.strftime('%d.%m.%Y')} - {MAX_DATE.strftime('%d.%m.%Y')})")

    # Tutar kontrolü
    amounts = extract_amounts(text)
    total_amount = sum(amounts)
    if abs(total_amount - declared_amount) > 1:
        issues.append(f"Yüklenen bilet tutarı ({total_amount:.0f} TL), formda beyan edilen tutar ({declared_amount:.1f} TL) ile uyuşmuyor")

    if issues:
        return jsonify({"valid": False, "issues": issues})
    else:
        return jsonify({"valid": True})

# Render veya benzeri platformda çalıştırma için
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
