from flask import Flask, request, jsonify
import pytesseract
from PyPDF2 import PdfReader
from pdf2image import convert_from_bytes
from PIL import Image
import io
import re

app = Flask(__name__)

# Anahtar kelimeler (büyük/küçük harf duyarsız eşleşme yapılacak)
KEYWORDS = [
    "TOPLAM (TL) (KDV DAHİL)",
    "Toplam Tutar",
    "ÜCRET (Price)",
    "Ödenecek Tutar",
    "TOPLAM BEDEL (TL)/Total: [KDV DAHİL]",
    "KDV DAHİL ÜCRET / FARE"
]

def extract_text_from_pdf(file_stream):
    text = ""

    # Önce metin olarak çıkarmayı dene
    try:
        reader = PdfReader(file_stream)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print("PDF metin çıkarma hatası:", str(e))

    # Eğer metin yoksa veya yetersizse OCR'a geç
    if not text.strip() or len(text) < 30:
        try:
            file_stream.seek(0)
            images = convert_from_bytes(file_stream.read())
            for image in images:
                ocr_text = pytesseract.image_to_string(image, lang="tur")
                print("==== OCR ÇIKTISI ====")
                print(ocr_text)
                text += ocr_text
        except Exception as e:
            raise RuntimeError(f"OCR başarısız: {str(e)}")

    return text

def extract_amount_from_text(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for keyword in KEYWORDS:
            if keyword.lower() in line.lower():
                possible_line = line
                # Bazen sayı bir alt satırda olabilir
                if not any(char.isdigit() for char in line) and i + 1 < len(lines):
                    possible_line += " " + lines[i + 1]

                # Sayı bulma
                match = re.search(r"(\d{1,3}(?:[\.,]\d{3})*[\.,]?\d{0,2})", possible_line.replace(" ", ""))
                if match:
                    amount_str = match.group(1).replace(".", "").replace(",", ".")
                    try:
                        return float(amount_str)
                    except ValueError:
                        continue
    return 0.0

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        file = request.files["file"]
        full_name = request.form["full_name"]
        declared_amount = float(request.form["declared_amount"])

        text = extract_text_from_pdf(file.stream)
        print("==== TAM OCR METNİ ====")
        print(text)

        extracted_amount = extract_amount_from_text(text)

        issues = []
        if abs(extracted_amount - declared_amount) > 1:
            issues.append(
                f"Yüklenen bilet tutarı ({extracted_amount:.0f} TL), formda beyan edilen tutar ({declared_amount:.1f} TL) ile uyuşmuyor"
            )

        is_valid = len(issues) == 0
        return jsonify({"valid": is_valid, "issues": issues})

    except Exception as e:
        print("ANALİZ HATASI:", str(e))
        return jsonify({"valid": False, "issues": [f"PDF okunamadı: {str(e)}"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
