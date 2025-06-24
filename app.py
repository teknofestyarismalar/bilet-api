from flask import Flask, request, jsonify
import tempfile
import pytesseract
from pdf2image import convert_from_path
import re
from datetime import datetime

app = Flask(__name__)

# Ayarlar
DATE_MIN = datetime(2025, 4, 26)
DATE_MAX = datetime(2025, 5, 7)
TOLERANCE = 1.0

def extract_text_from_pdf(pdf_path):
    try:
        images = convert_from_path(pdf_path)
        full_text = ""
        for img in images:
            text = pytesseract.image_to_string(img, lang='tur')
            full_text += text + "\n"
        return full_text.lower()
    except Exception as e:
        return ""

def check_conditions(text, full_name, declared_amount):
    issues = []

    # Ad-Soyad kontrolü
    name_ok = all(part in text for part in full_name.lower().split())
    if not name_ok:
        issues.append("Ad-Soyad, fatura üzerinde bulunamadı.")

    # Tarih kontrolü
    dates = re.findall(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", text)
    date_ok = any(DATE_MIN <= datetime.strptime(d.replace("-", ".").replace("/", "."), "%d.%m.%Y") <= DATE_MAX for d in dates)
    if not date_ok:
        issues.append(f"Fatura tarihi desteklenen tarih aralığında değil ({DATE_MIN.strftime('%d.%m.%Y')} - {DATE_MAX.strftime('%d.%m.%Y')})")

    # Tutar kontrolü
    amounts = [float(x.replace(",", ".").replace(" ", "")) for x in re.findall(r"\b\d{2,4}[.,]?\d{0,2}\b", text)]
    total_amount = round(sum(amounts), 2)
    declared = float(declared_amount)
    if abs(total_amount - declared) > TOLERANCE:
        issues.append(f"Yüklenen bilet tutarı ({total_amount} TL), formda beyan edilen tutar ({declared} TL) ile uyuşmuyor")

    return issues

@app.route("/analyze", methods=["POST"])
def analyze_pdf():
    if "file" not in request.files:
        return jsonify({"error": "PDF dosyası eksik"}), 400

    file = request.files["file"]
    full_name = request.form.get("full_name", "")
    declared_amount = request.form.get("declared_amount", "0")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp:
        file.save(temp.name)
        text = extract_text_from_pdf(temp.name)
        issues = check_conditions(text, full_name, declared_amount)

    return jsonify({
        "valid": not issues,
        "issues": issues
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
