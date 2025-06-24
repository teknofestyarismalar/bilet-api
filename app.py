from flask import Flask, request, jsonify
import pytesseract
from pdf2image import convert_from_bytes
import io
from datetime import datetime
from PyPDF2 import PdfReader

app = Flask(__name__)

START_DATE = datetime(2025, 4, 26)
END_DATE = datetime(2025, 5, 7)

def extract_text_and_amount(pdf_bytes):
    try:
        images = convert_from_bytes(pdf_bytes)
    except Exception as e:
        return "", [], f"PDF dönüştürme hatası: {str(e)}"

    text = ""
    dates = []
    total = 0

    for image in images:
        page_text = pytesseract.image_to_string(image, lang="tur")
        text += page_text

        # Tarihleri bul
        for line in page_text.split("\n"):
            if any(ay in line.lower() for ay in ["nisan", "mayıs", "2025"]):
                try:
                    parcalar = line.strip().split()
                    for parca in parcalar:
                        try:
                            tarih = datetime.strptime(parca.strip(), "%d.%m.%Y")
                            dates.append(tarih)
                        except:
                            continue
                except:
                    continue

            # Tutarları yakala
            if "tl" in line.lower():
                try:
                    tl = float(line.lower().replace("tl", "").replace(",", ".").strip().split()[0])
                    if 10 < tl < 5000:
                        total += tl
                except:
                    continue

    return text, dates, total

@app.route("/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"valid": False, "issues": ["Dosya bulunamadı."]}), 400

    file = request.files["file"]
    full_name = request.form.get("full_name", "").strip().lower()
    declared_amount = float(request.form.get("declared_amount", 0))

    try:
        content = file.read()
        text, dates, total = extract_text_and_amount(content)

        issues = []

        if not any(START_DATE <= d <= END_DATE for d in dates):
            issues.append("Fatura tarihi desteklenen tarih aralığında değil (26.04.2025 - 07.05.2025)")

        if abs(total - declared_amount) > 1:
            issues.append(f"Yüklenen bilet tutarı ({total} TL), formda beyan edilen tutar ({declared_amount} TL) ile uyuşmuyor")

        if full_name not in text.lower():
            issues.append("Ad-Soyad, fatura üzerinde bulunamadı.")

        return jsonify({
            "valid": len(issues) == 0,
            "issues": issues
        })
    except Exception as e:
        return jsonify({"valid": False, "issues": [f"Hata oluştu: {str(e)}"]}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
