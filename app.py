import os
import tempfile
from flask import Flask, request, jsonify
import fitz  # PyMuPDF
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

        if file.mimetype != "application/pdf":
            return jsonify({"valid": False, "issues": ["Yüklenen dosya PDF değil."]}), 400

        declared_amount = float(declared_amount)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)
            print(f"PDF kaydedildi: {temp_pdf.name}")
            print(f"Dosya boyutu: {os.path.getsize(temp_pdf.name)} bayt")

        text_pages = extract_text_by_page(temp_pdf.name)
        all_text = "\n".join(text_pages)

        amounts = extract_all_amounts(text_pages)
        print("Extracted amounts:", amounts)
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
        return jsonify({"valid": False, "issues": [f"PDF okunamadı: {str(e)}"]})


def extract_text_by_page(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        return [page.get_text() for page in doc]
    except Exception as e:
        raise Exception(f"PyMuPDF PDF açma hatası: {str(e)}")


def extract_all_amounts(text_pages):
    seen_tickets = set()
    amounts = []

    for text in text_pages:
        lines = text.splitlines()
        amount = None
        date = None

        for line in lines:
            for kw in KEYWORDS:
                if kw.lower() in line.lower():
                    matches = re.findall(r"[\d\s]*[\.,]\d{2}", line)
                    for m in matches:
                        cleaned = m.replace(" ", "").replace(".", "").replace(",", ".")
                        try:
                            val = float(cleaned)
                            if val > 0:
                                amount = val
                        except:
                            continue

            date_match = re.search(r"\d{2}/\d{2}/\d{4}", line)
            if date_match:
                date = date_match.group()

        if amount and date and date not in seen_tickets:
            seen_tickets.add(date)
            amounts.append(amount)

    return amounts


def extract_name(text):
    lines = text.splitlines()
    for line in lines:
        if "Adı Soyadı" in line or "Yolcu" in line or "Ad-Soyad" in line:
            parts = line.split(":")
            if len(parts) > 1:
                return parts[1].strip()
    return "Belirlenemedi"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
