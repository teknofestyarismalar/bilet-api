import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import difflib
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

@app.route('/')
def index():
    return "OK"

@app.route('/analyze', methods=['POST'])
def analyze_pdf():
    try:
        if 'pdf' not in request.files or 'declared_amount' not in request.form:
            return jsonify({
                "valid": False,
                "issues": ["Eksik veri"]
            })

        file = request.files['pdf']
        declared_amount = float(request.form['declared_amount'])
        full_name = request.form.get('full_name', '').strip()

        if not full_name:
            return jsonify({
                "valid": False,
                "issues": ["Eksik veri"]
            })

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)

        text = extract_text_from_pdf(temp_pdf.name)

        # OCR çıktısını yaz (debug için)
        with open("ocr_output.txt", "w", encoding="utf-8") as f:
            f.write(text)

        extracted_amounts = extract_all_amounts(text)
        total_amount = sum(extracted_amounts)

        extracted_names = extract_possible_names(text)
        matched_name = match_name(full_name, extracted_names)

        issues = []

        if total_amount == 0:
            issues.append("PDF okunamadı veya tutar bulunamadı.")
        elif abs(total_amount - declared_amount) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

        if not matched_name:
            issues.append("Belgedeki isim formdaki isimle uyuşmuyor.")

        if issues:
            return jsonify({
                "valid": False,
                "issues": issues,
                "extracted_name": extracted_names[0] if extracted_names else "BULUNAMADI"
            })

        return jsonify({"valid": True})

    except Exception as e:
        return jsonify({
            "valid": False,
            "issues": [f"PDF okunamadı: {str(e)}"]
        })

def extract_text_from_pdf(pdf_path):
    from pdf2image.exceptions import PDFPageCountError
    from PIL import UnidentifiedImageError

    try:
        # Önce PyPDF2 ile dene
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            if any(keyword.lower() in text.lower() for keyword in KEYWORDS):
                return text
        except Exception as e:
            print("PyPDF2 ile metin okunamadı, OCR ile devam edilecek:", str(e))

        # OCR ile dene
        images = convert_from_path(pdf_path, dpi=200, single_file=False)
        ocr_text = ""
        for i, image in enumerate(images):
            try:
                ocr_text += pytesseract.image_to_string(image, lang="tur") + "\n"
            except UnidentifiedImageError:
                print(f"{i+1}. sayfa okunamadı, atlanıyor.")
                continue

        return ocr_text

    except PDFPageCountError:
        raise Exception("Sayfa sayısı alınamadı. Dosya bozuk olabilir.")
    except Exception as e:
        raise Exception("OCR hatası: " + str(e))

def extract_all_amounts(text):
    pattern = r"(?:" + "|".join(re.escape(k) for k in KEYWORDS) + r")\D{0,20}(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})"
    matches = re.findall(pattern, text, re.IGNORECASE)
    values = []
    seen = set()
    for match in matches:
        cleaned = match.replace(".", "").replace(",", ".")
        try:
            amount = float(cleaned)
            if amount not in seen:
                values.append(amount)
                seen.add(amount)
        except:
            continue
    return values

def extract_possible_names(text):
    lines = text.splitlines()
    possible_names = []
    for line in lines:
        if any(keyword in line.lower() for keyword in ["ad", "soyad", "adı", "yolcu", "name"]):
            words = line.strip().split()
            if 2 <= len(words) <= 5:
                possible_names.append(" ".join(words))
    return possible_names

def match_name(form_name, extracted_names):
    form_name_clean = form_name.lower().strip()
    for name in extracted_names:
        name_clean = name.lower().strip()
        ratio = difflib.SequenceMatcher(None, form_name_clean, name_clean).ratio()
        if ratio >= 0.8:
            return True
    return False

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
