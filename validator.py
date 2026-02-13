import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker

class IdentityValidator:
    def __init__(self):
        # MRZ karakterleri için sadece İngilizce yeterlidir
        self.reader = easyocr.Reader(['en'], gpu=False)

    def clean_field(self, text):
        if not text: return "Bilinmiyor"
        # OCR karakter karıştırmalarını düzelt
        text = text.replace('6', 'G').replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B')
        return text.replace('<', ' ').strip()

    def apply_filters(self, roi, pass_num):
        """Karanlık, bulanık ve uzak çekimler için optimize edilmiş filtre seti"""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # CLAHE: Karanlık bölgelerdeki gizli karakterleri ortaya çıkarır
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl_img = clahe.apply(gray)

        if pass_num == 0: # Standart Mod
            enhanced = cv2.convertScaleAbs(cl_img, alpha=1.8, beta=-40)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            
        elif pass_num == 1: # Karanlık Mod (Yüksek Kontrast)
            enhanced = cv2.convertScaleAbs(cl_img, alpha=2.3, beta=-60)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            
        elif pass_num == 2: # Keskinleştirme Odaklı (Bulanıklık ve Uzaklık İçin)
            kernel = np.array([[-1,-1,-1], [-1,10,-1], [-1,-1,-1]]) # Daha sert keskinleştirme
            sharpened = cv2.filter2D(cl_img, -1, kernel)
            return cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 5)
            
        else: # İnce Detay Modu
            return cv2.adaptiveThreshold(cl_img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "msg": "dosya_bulunamadi"}

        # Kullanıcı gride oturttuğu için 1000x600 standart boyutlandırma yapıyoruz
        img_resized = cv2.resize(img, (1000, 600))
        y_start, y_end = 350, 600
        x_start, x_end = 10, 990
        mrz_roi = img_resized[y_start:y_end, x_start:x_end]

        for pass_num in range(4):
            thresh = self.apply_filters(mrz_roi, pass_num)
            
            # EasyOCR'a sadece MRZ karakterlerini beklemesini söylüyoruz
            results = self.reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<')          
            clean_text = "".join([re.sub(r'[^A-Z0-9<]', '', t.upper()) for t in results])

            lines = re.findall(r'[A-Z0-9<]{30}', clean_text)
            if len(lines) < 3:
                lines = []
                for i in range(len(clean_text)):
                    chunk = clean_text[i:i+30]
                    if len(chunk) == 30 and chunk[0] in 'ICA':
                        lines.append(chunk)

            if len(lines) >= 3:
                mrz_data = "\n".join(lines[:3])
                try:
                    checker = TD1CodeChecker(mrz_data)
                    fields = checker.fields()
                    is_valid = getattr(checker, 'valid', False) or (hasattr(checker, 'is_valid') and checker.is_valid())

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
                except:
                    continue 

        return {"status": "fail", "msg": "mrz_formati_bulunamadi"}