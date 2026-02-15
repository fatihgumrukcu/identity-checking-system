import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker
from datetime import datetime

class IdentityValidator:
    def __init__(self):
        self.reader = easyocr.Reader(['en'], gpu=False)

    def clean_field(self, text):
        if not text:
            return "Bilinmiyor"
        return text.replace('<', ' ').strip()

    # --- MRZ CHECKSUM HESAPLAMA ---
    def compute_checksum(self, data):
        weights = [7, 3, 1]
        total = 0
        for i, char in enumerate(data):
            if char.isdigit():
                val = int(char)
            elif char.isalpha():
                val = ord(char) - 55
            else:
                val = 0
            total += val * weights[i % 3]
        return str(total % 10)

    # --- NUMERIC ZONE REPAIR ---
    def repair_numeric_zone(self, text):
        text = text.replace("O", "0")
        text = text.replace("I", "1")
        text = text.replace("B", "8")
        text = text.replace("S", "5")
        return text

    # --- 30 KARAKTERE ZORLA ---
    def normalize_line(self, line):
        line = line.replace(" ", "")
        if len(line) < 30:
            line = line.ljust(30, "<")
        return line[:30]

    def apply_filters(self, roi, pass_num):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl_img = clahe.apply(gray)

        if pass_num == 0:
            enhanced = cv2.convertScaleAbs(cl_img, alpha=1.8, beta=-40)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 1:
            enhanced = cv2.convertScaleAbs(cl_img, alpha=2.3, beta=-60)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 2:
            kernel = np.array([[-1,-1,-1], [-1,10,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(cl_img, -1, kernel)
            return cv2.adaptiveThreshold(sharpened, 255,
                                         cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 13, 5)
        else:
            return cv2.adaptiveThreshold(cl_img, 255,
                                         cv2.ADAPTIVE_THRESH_MEAN_C,
                                         cv2.THRESH_BINARY, 11, 2)

    def logical_date_check(self, birth, expiry):
        try:
            birth_date = datetime.strptime(birth, "%y%m%d")
            expiry_date = datetime.strptime(expiry, "%y%m%d")
            return birth_date < expiry_date
        except:
            return False

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None:
            return {"status": "error", "msg": "dosya_bulunamadi"}

        img_resized = cv2.resize(img, (1000, 600))
        mrz_roi = img_resized[350:600, 10:990]

        for pass_num in range(4):
            thresh = self.apply_filters(mrz_roi, pass_num)

            results = self.reader.readtext(
                thresh,
                detail=0,
                allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<'
            )

            clean_text = "".join(
                [re.sub(r'[^A-Z0-9<]', '', t.upper()) for t in results]
            )

            lines = re.findall(r'[A-Z0-9<]{30}', clean_text)

            if len(lines) >= 3:
                line1 = self.normalize_line(lines[0])
                line2 = self.normalize_line(self.repair_numeric_zone(lines[1]))
                line3 = self.normalize_line(lines[2])

                mrz_data = "\n".join([line1, line2, line3])

                try:
                    checker = TD1CodeChecker(mrz_data)
                    fields = checker.fields()

                    # --- ALAN BAZLI CHECKSUM ---
                    doc_number = line1[5:14]
                    doc_checksum = line1[14]

                    birth = line2[0:6]
                    birth_checksum = line2[6]

                    expiry = line2[8:14]
                    expiry_checksum = line2[14]

                    doc_ok = self.compute_checksum(doc_number) == doc_checksum
                    birth_ok = self.compute_checksum(birth) == birth_checksum
                    expiry_ok = self.compute_checksum(expiry) == expiry_checksum

                    logical_ok = self.logical_date_check(birth, expiry)

                    final_status = doc_ok and birth_ok and expiry_ok and logical_ok

                    return {
                        "status": "ok",
                        "ulke": fields.country,
                        "ad": self.clean_field(fields.name),
                        "soyad": self.clean_field(fields.surname),
                        "belge_no": fields.document_number.replace('<', ''),
                        "dogrulama": "BAŞARILI" if final_status else "CHECKSUM_HATASI",
                        "doc_checksum": doc_ok,
                        "birth_checksum": birth_ok,
                        "expiry_checksum": expiry_ok,
                        "logical_date_check": logical_ok,
                        "pass_used": pass_num
                    }

                except:
                    continue

        return {"status": "fail", "msg": "mrz_formati_bulunamadi"}
