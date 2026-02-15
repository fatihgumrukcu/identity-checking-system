import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td3 import TD3CodeChecker

class IdentityValidator:
    def __init__(self):
        # OCR doğruluğu için CPU'da çalıştırıyoruz.
        self.reader = easyocr.Reader(['en'], gpu=False)

    def force_numeric(self, text):
        """Tarih alanlarındaki karakter hatalarını rakama zorlar."""
        mapping = {'O': '0', 'I': '1', 'L': '1', 'G': '6', 'S': '5', 'B': '8', 'T': '7', 'Z': '2'}
        for char, digit in mapping.items():
            text = text.replace(char, digit)
        return text

    def apply_filters(self, roi, pass_num):
        """Görüntüyü farklı kontrast ve keskinlik seviyelerinde işler."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        if pass_num == 0:
            # Standart iyileştirme
            return cv2.threshold(cv2.GaussianBlur(gray, (3,3), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 1:
            # Yüksek kontrast (Karanlık çekimler için)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            return clahe.apply(gray)
        else:
            # Keskinleştirme (Bulanık çekimler için)
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            return cv2.filter2D(gray, -1, kernel)

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "message": "file_not_found"}

        # Dinamik ROI: Resmin alt %60'lık kısmını tara (Kimlik tipine göre değişebilir)
        h, w = img.shape[:2]
        roi = img[int(h*0.35):h, 0:w]
        
        for pass_num in range(3):
            processed = self.apply_filters(roi, pass_num)
            # OCR satırları paragraf olarak değil, tek tek okumalı
            results = self.reader.readtext(processed, detail=0)
            
            # 1. ADIM: OCR çıktılarını temizle ama bütünlüğü bozma
            raw_lines = [re.sub(r'[^A-Z0-9<]', '', t.upper()) for t in results]
            full_text = "".join(raw_lines)
            
            print(f"--- PASS {pass_num} RAW: {full_text}")

            # 2. ADIM: TD3 (Pasaport) Ara - 44 karakter
            td3_lines = re.findall(r'[A-Z0-9<]{40,45}', full_text)
            if len(td3_lines) >= 2:
                # En az bir tane '<' içeren satırları seç
                mrz_lines = [l for l in td3_lines if '<' in l]
                if len(mrz_lines) >= 2:
                    final_mrz = "\n".join([l.ljust(44, '<')[:44] for l in mrz_lines[:2]])
                    try:
                        checker = TD3CodeChecker(final_mrz)
                        return self.format_response(checker, "PASSPORT", pass_num)
                    except: pass

            # 3. ADIM: TD1 (Kimlik) Ara - 30 karakter
            td1_lines = re.findall(r'[A-Z0-9<]{27,33}', full_text)
            if len(td1_lines) >= 3:
                mrz_lines = [l for l in td1_lines if '<' in l]
                if len(mrz_lines) >= 3:
                    processed_td1 = []
                    for i, l in enumerate(mrz_lines[:3]):
                        line = l.ljust(30, '<')[:30]
                        if i == 1: line = self.force_numeric(line)
                        processed_td1.append(line)
                    
                    try:
                        checker = TD1CodeChecker("\n".join(processed_td1))
                        return self.format_response(checker, "ID_CARD", pass_num)
                    except: pass

        return {"status": "fail", "message": "mrz_not_detected"}

    def format_response(self, checker, doc_type, pass_num):
        fields = checker.fields()
        report = checker.report()
        is_valid = report.valid

        return {
            "status": "success",
            "document_type": doc_type,
            "country": fields.country,
            "first_name": fields.name.replace('<', ' ').strip(),
            "last_name": fields.surname.replace('<', ' ').strip(),
            "document_number": fields.document_number.replace('<', ''),
            "verification": "SUCCESS" if is_valid else "CHECKSUM_ERROR",
            "pass_used": pass_num,
            "details": str(report.errors) if not is_valid else "None"
        }