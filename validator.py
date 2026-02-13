import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker

class IdentityValidator:
    def __init__(self):
        # Sunucuda CPU ile çalışacak şekilde EasyOCR yüklenir.
        self.reader = easyocr.Reader(['en'], gpu=False)

    def force_numeric(self, text):
        """Tarih ve checksum alanlarındaki harf hatalarını rakama çevirir."""
        mapping = {'O': '0', 'I': '1', 'L': '1', 'G': '6', 'S': '5', 'B': '8', 'T': '7', 'Z': '2'}
        for char, digit in mapping.items():
            text = text.replace(char, digit)
        return text

    def clean_field(self, text):
        if not text: return "Bilinmiyor"
        # İsim alanlarındaki rakam karışıklıklarını harfe çevirir.
        text = text.replace('6', 'G').replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B')
        return text.replace('<', ' ').strip()

    def apply_filters(self, roi, pass_num):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl_img = clahe.apply(gray)

        if pass_num == 0:
            enhanced = cv2.convertScaleAbs(cl_img, alpha=1.3, beta=10)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 1:
            enhanced = cv2.convertScaleAbs(cl_img, alpha=2.0, beta=-30)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        else:
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(cl_img, -1, kernel)
            return cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 7)

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "msg": "dosya_bulunamadi"}

        # Daha iyi OCR için çözünürlüğü artırıyoruz.
        img_resized = cv2.resize(img, (1200, 800))
        # MRZ alanı genellikle alt kısımdadır, koordinatları buna göre optimize ettik.
        mrz_roi = img_resized[450:780, 20:1180] 

        for pass_num in range(3):
            thresh = self.apply_filters(mrz_roi, pass_num)
            results = self.reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<')
            all_text = "".join([t.upper() for t in results])

            # Ham metni logla.
            print(f"--- PASS {pass_num} HAM METİN: {all_text}")

            # Sadece geçerli karakter uzunluğunda ve içinde '<' olan satırları bul (Metinleri elemek için).
            lines = re.findall(r'[A-Z0-9<]{28,32}', all_text)
            actual_mrz_lines = [l for l in lines if '<' in l]

            if len(actual_mrz_lines) >= 3:
                processed_lines = []
                # İlk 3 satırı formatla.
                for idx, line in enumerate(actual_mrz_lines[:3]):
                    if idx == 1: 
                        line = self.force_numeric(line)
                    processed_lines.append(line.ljust(30, '<')[:30])
                
                mrz_data = "\n".join(processed_lines)
                print(f"--- ANALİZ EDİLEN MRZ:\n{mrz_data}")
                
                try:
                    checker = TD1CodeChecker(mrz_data)
                    
                    # _Report object is not callable hatası için güvenli erişim:
                    report_obj = checker.report
                    report_data = report_obj() if callable(report_obj) else report_obj
                    
                    is_valid = len(report_data.errors) == 0

                    if not is_valid:
                        print(f"!!! CHECKSUM HATASI: {report_data.errors}")

                    fields = checker.fields()
                    return {
                        "status": "ok",
                        "ulke": fields.country,
                        "ad": self.clean_field(fields.name),
                        "soyad": self.clean_field(fields.surname),
                        "tc_no": fields.optional_data.replace('<', ''),
                        "belge_no": fields.document_number.replace('<', ''),
                        "dogrulama": "BAŞARILI" if is_valid else "CHECKSUM_HATASI",
                        "pass_used": pass_num
                    }
                except Exception as e:
                    print(f"!!! PARSE HATASI: {str(e)}")
                    continue 

        return {"status": "fail", "msg": "mrz_bulunamadi"}