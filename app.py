import os
import tempfile
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
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

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

    if any(k.lower() in text.lower() for k in KEYWORDS):
        return text

    images = convert_from_path(pdf_path)
    for image in images:
        text += pytesseract.image_to_string(image, lang="tur")

    return text

def extract_amounts(text):
    pattern = r"(?:" + "|".join(re.escape(k) for k in KEYWORDS) + r")\D{0,20}(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})"
    matches = re.findall(pattern, text, re.IGNORECASE)
    values = set()
    for match in matches:
        try:
            amount = float(match.replace(".", "").replace(",", "."))
            values.add(amount)
        except:
            continue
    return list(values)

def extract_names(text):
    name_pattern = r"(?:Sayın|Sn\.?)\s+([A-ZÇĞİÖŞÜ][a-zçğıöşü]+\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)"
    return re.findall(name_pattern, text)

@app.route("/analyze", methods=["POST"])
def analyze():
    if "pdf" not in request.files or "declared_amount" not in request.form:
        return jsonify({"valid": False, "issues": ["Eksik veri"]})

    try:
        declared = float(request.form["declared_amount"])
        uploaded = request.files["pdf"]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            uploaded.save(tmp.name)

        text = extract_text_from_pdf(tmp.name)
        amounts = extract_amounts(text)
        names = extract_names(text)

        if not amounts:
            return jsonify({"valid": False, "issues": ["PDF okunamadı veya tutar bulunamadı."]})

        matched_amounts = [a for a in amounts if abs(a - declared) < 1]
        total = sum(set(amounts))  # aynı bilet tekrar yüklenmişse iki kez saymamak için set

        issues = []
        matched_name = names[0] if names else ""

        if not matched_amounts and abs(total - declared) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total} TL), formda beyan edilen tutar ({declared} TL) ile uyuşmuyor")

        if names:
            form_name = request.form.get("full_name", "").strip().lower()
            doc_name = names[0].strip().lower()
            if form_name != doc_name:
                issues.append("Belgedeki isim formdaki isimle uyuşmuyor")

        return jsonify({
            "valid": len(issues) == 0,
            "issues": issues,
            "matched_name": matched_name
        })

    except Exception as e:
        return jsonify({"valid": False, "issues": [f"PDF okunamadı: {str(e)}"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
