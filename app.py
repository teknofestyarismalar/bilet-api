from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
import re
from datetime import datetime
from difflib import SequenceMatcher
from io import BytesIO

app = Flask(__name__)

# Ayarlar
ACCEPTABLE_DATE_START = datetime(2025, 4, 26)
ACCEPTABLE_DATE_END = datetime(2025, 5, 7)
TOLERANCE_TL = 1.0

def extract_text_from_pdf(pdf_bytes):
    text = ""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            text += page.extract_text() or ""
    except:
        pass
    
    if len(text.strip()) < 30:
        images = convert_from_bytes(pdf_bytes)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img, lang="tur")
    return text

def extract_date(text):
    pattern = r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b"
    matches = re.findall(pattern, text)
    for match in matches:
        for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(match, fmt)
            except:
                continue
    return None

def extract_amount(text):
    pattern = r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s?(TL|tl|₺)?"
    matches = re.findall(pattern, text)
    if matches:
        amt = matches[0][0].replace(".", "").replace(",", ".")
        return float(amt)
    return None

def names_similar(name1, name2):
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio() > 0.85

@app.route('/analyze', methods=['POST'])
def analyze():
    file = request.files['file']
    full_name = request.form.get('full_name', '').strip()
    declared_amount = float(request.form.get('declared_amount', '0'))

    pdf_bytes = file.read()
    text = extract_text_from_pdf(pdf_bytes)

    issues = []

    # 1. Ad soyad kontrolü
    if full_name.lower() not in text.lower():
        if not names_similar(full_name, text):
            issues.append("Bilette yer alan ad-soyad, formdaki ad-soyad ile uyuşmuyor")

    # 2. Tarih kontrolü
    travel_date = extract_date(text)
    if not travel_date:
        issues.append("Fatura tarihi bulunamadı")
    elif not (ACCEPTABLE_DATE_START <= travel_date <= ACCEPTABLE_DATE_END):
        issues.append(f"Fatura tarihi desteklenen tarih aralığında değil ({ACCEPTABLE_DATE_START.strftime('%d.%m.%Y')} - {ACCEPTABLE_DATE_END.strftime('%d.%m.%Y')})")

    # 3. Tutar kontrolü
    actual_amount = extract_amount(text)
    if actual_amount is None:
        issues.append("Fatura tutarı bulunamadı")
    elif abs(actual_amount - declared_amount) > TOLERANCE_TL:
        issues.append(f"Yüklenen bilet tutarı ({actual_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

    valid = len(issues) == 0

    return jsonify({
        "valid": valid,
        "issues": issues
    })

if __name__ == '__main__':
    app.run(debug=True)
