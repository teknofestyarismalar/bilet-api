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

# OCR ile PDF'ten metin çıkarma
def extract_text_from_pdf(file_stream):
    text = ""
    images = convert_from_bytes(file_stream.read())
    for img in images:
        text += pytesseract.image_to_string(img, lang='tur') + "\n"
    return text

# Tutarları ayıklama
def extract_amounts(text):
    amount_labels = [
        "TOPLAM (TL) (KDV DAHİL)",
        "Toplam Tutar",
        "ÜCRET (Price)",
        "Ödenecek Tutar",
        "TOPLAM BEDEL (TL)/Total: [KDV DAHİL]",
        "KDV DAHİL ÜCRET / FARE"
    ]
    pattern = r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))'
    lines = text.splitlines()
    amounts = []

    for line in lines:
        for label in amount_labels:
            if label.lower() in line.lower():
                matches = re.findall(pattern, line)
                for match in matches:
                    cleaned = match.replace('.', '').replace(',', '.')
                    try:
                        amount = float(cleaned)
                        amounts.append(amount)
                    except:
                        continue
    return amounts

# Tarihleri ayıklama
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
        print("==== OCR ÇIKTISI ====")
        print(text)
    except Exception as e:
        return jsonify({"valid": False, "issues": [f"PDF okunamadı: {str(e)}"]})

    issues = []

    # Ad kontrolü
    if full_name not in text.lower():
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

# Render için zorunlu
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
