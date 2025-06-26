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

@app.route('/')
def index():
    return "OK"

@app.route('/analyze', methods=['POST'])
def analyze_pdf():
    try:
        if 'pdf' not in request.files or 'declared_amount' not in request.form:
            return jsonify({"valid": False, "issues": ["Eksik veri"]})

        file = request.files['pdf']
        declared_amount = float(request.form['declared_amount'])
        user_name = request.form.get('full_name', "").strip().lower()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            file.save(temp_pdf.name)

        pages = convert_from_path(temp_pdf.name)
        total_amount = 0
        seen_trips = set()
        names_found = set()

        for page in pages:
            text = pytesseract.image_to_string(page, lang="tur")
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if not lines:
                continue

            # 🔍 İsim kontrolü
            name_positions = [i for i, l in enumerate(lines) if user_name in l.lower()]
            if name_positions:
                name_index = name_positions[0]
                names_found.add(True)
            else:
                names_found.add(False)

            # 🚍 Hareket tarihi ve saat kontrolü
            date_pattern = r"(\d{2}[./-]\d{2}[./-]\d{4})"
            time_pattern = r"(\d{2}[:.]\d{2})"
            trip_id = None

            for line in lines:
                date_match = re.search(date_pattern, line)
                time_match = re.search(time_pattern, line)
                if date_match and time_match:
                    trip_id = f"{date_match.group(1)}_{time_match.group(1)}"
                    break

            if trip_id in seen_trips:
                continue  # Aynı bilet, tekrar sayma
            if trip_id:
                seen_trips.add(trip_id)

            # 💰 Tutar çıkarma
            text_lower = "\n".join(lines).lower()
            pattern = r"(?:" + "|".join(re.escape(k.lower()) for k in KEYWORDS) + r")\D{0,20}(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})"
            matches = re.findall(pattern, text_lower, re.IGNORECASE)

            if matches:
                last_match = matches[-1].replace(".", "").replace(",", ".")
                try:
                    extracted = float(last_match)
                    total_amount += extracted
                except:
                    continue

        # ✔️ Kontroller
        if not any(names_found):
            return jsonify({"valid": False, "issues": ["Belgedeki isim formdaki isimle uyuşmuyor."]})

        if total_amount == 0:
            return jsonify({"valid": False, "issues": ["PDF okunamadı veya tutar bulunamadı."]})

        if abs(total_amount - declared_amount) > 1:
            return jsonify({
                "valid": False,
                "issues": [f"Yüklenen bilet tutarı ({total_amount} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor"]
            })

        return jsonify({"valid": True})

    except Exception as e:
        return jsonify({
            "valid": False,
            "issues": [f"PDF okunamadı: {str(e)}"]
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
