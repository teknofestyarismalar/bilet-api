from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from datetime import datetime
import io
import re
import unicodedata

app = Flask(__name__)

# Tarih aralığı
DATE_MIN = datetime(2025, 4, 26)
DATE_MAX = datetime(2025, 5, 7)

def normalize_text(text):
    # Büyük küçük harf farkını ve Türkçe karakterleri normalize eder
    text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("ASCII")
    return text.lower()

@app.route("/analyze", methods=["POST"])
def analyze():
    file = request.files.get("file")
    full_name = request.form.get("full_name", "").strip()
    declared_amount = float(request.form.get("declared_amount", 0))

    issues = []
    found_name = False
    found_date = False
    total_amount = 0
    extracted_text = ""

    if not file:
        return jsonify({"valid": False, "issues": ["Dosya alınamadı."], "ocr_text": ""})

    try:
        # PDF sayfalarını resme dönüştür
        images = convert_from_bytes(file.read())

        # OCR işlemi
        for image in images:
            text = pytesseract.image_to_string(image, lang="tur")
            extracted_text += text + "\n"

        # Ad-Soyad kontrolü
        normalized_name = normalize_text(full_name)
        if normalized_name in normalize_text(extracted_text):
            found_name = True
        else:
            issues.append("Ad-Soyad, fatura üzerinde bulunamadı.")

        # Tarih kontrolü
        dates_found = re.findall(r"\d{2}[./-]\d{2}[./-]\d{4}", extracted_text)
        for date_str in dates_found:
            try:
                date_obj = datetime.strptime(date_str.replace("-", ".").replace("/", "."), "%d.%m.%Y")
                if DATE_MIN <= date_obj <= DATE_MAX:
                    found_date = True
                    break
            except:
                continue
        if not found_date:
            issues.append(f"Fatura tarihi desteklenen tarih aralığında değil ({DATE_MIN.strftime('%d.%m.%Y')} - {DATE_MAX.strftime('%d.%m.%Y')})")

        # Tutar kontrolü
        amounts = re.findall(r"\d+[.,]?\d*", extracted_text)
        try:
            total_amount = sum([float(a.replace(",", ".")) for a in amounts])
        except:
            total_amount = 0

        if abs(total_amount - declared_amount) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total_amount:.0f} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

        return jsonify({
            "valid": len(issues) == 0,
            "issues": issues,
            "ocr_text": extracted_text  # debug amaçlı tüm metin
        })

    except Exception as e:
        return jsonify({"valid": False, "issues": [f"PDF işleme hatası: {str(e)}"], "ocr_text": extracted_text})
