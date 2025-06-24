from flask import Flask, request, jsonify
from PyPDF2 import PdfReader
from datetime import datetime
import re

app = Flask(__name__)

START_DATE = datetime(2025, 4, 26)
END_DATE = datetime(2025, 5, 7)

def extract_text_and_info(pdf_bytes):
    try:
        reader = PdfReader(pdf_bytes)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        dates = []
        total = 0.0

        # Tarihleri bul
        date_matches = re.findall(r"\d{2}\.\d{2}\.\d{4}", text)
        for date_str in date_matches:
            try:
                date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                dates.append(date_obj)
            except:
                continue

        # Tutarları bul
        amount_matches = re.findall(r"([\d,.]+)\s?TL", text, flags=re.IGNORECASE)
        for amt in amount_matches:
            try:
                amt_clean = float(amt.replace(".", "").replace(",", "."))
                if 10 < amt_clean < 5000:
                    total += amt_clean
            except:
                continue

        return text.lower(), dates, total
    except Exception as e:
        return "", [], 0.0

@app.route("/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"valid": False, "issues": ["Dosya bulunamadı."]}), 400

    file = request.files["file"]
    full_name = request.form.get("full_name", "").strip().lower()
    declared_amount = float(request.form.get("declared_amount", 0))

    try:
        content = file.read()
        text, dates, total = extract_text_and_info(content)

        issues = []

        if not any(START_DATE <= d <= END_DATE for d in dates):
            issues.append("Fatura tarihi desteklenen tarih aralığında değil (26.04.2025 - 07.05.2025)")

        if abs(total - declared_amount) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

        if full_name not in text:
            issues.append("Ad-Soyad, fatura üzerinde bulunamadı.")

        return jsonify({
            "valid": len(issues) == 0,
            "issues": issues
        })

    except Exception as e:
        return jsonify({"valid": False, "issues": [f"Hata oluştu: {str(e)}"]}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
