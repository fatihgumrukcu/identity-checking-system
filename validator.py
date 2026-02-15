import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td3 import TD3CodeChecker

class IdentityValidator:
    def __init__(self):
        # MRZ karakter tanıma için İngilizce modeli yeterlidir
        self.reader = easyocr.Reader(['en'], gpu=False)

    def force_numeric(self, text):
        """Tarih ve checksum alanlarındaki olası karakter hatalarını düzeltir"""
        mapping = {'O': '0', 'I': '1', 'L': '1', 'G': '6', 'S': '5', 'B': '8', 'T': '7', 'Z': '2'}
        for char, digit in mapping.items():
            text = text.replace(char, digit)
        return text

    def clean_field(self, text):
        """OCR tarafından yanlış okunan harf/rakam karışıklıklarını temizler"""
        if not text: return "Unknown"
        text = text.replace('6', 'G').replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B')
        return text.replace('<', ' ').strip()

    def apply_filters(self, roi, pass_num):
        """Karanlık, bulanık ve uzak çekimler için optimize edilmiş filtre seti"""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl_img = clahe.apply(gray)

        if pass_num == 0: # Standart Mod
            enhanced = cv2.convertScaleAbs(cl_img, alpha=1.8, beta=-40)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 1: # Karanlık/Düşük Kontrast Modu
            enhanced = cv2.convertScaleAbs(cl_img, alpha=2.3, beta=-60)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        else: # Keskinleştirme Modu (Bulanık görseller için)
            kernel = np.array([[-1,-1,-1], [-1,10,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(cl_img, -1, kernel)
            return cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 5)

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "message": "file_not_found"}

        # Standart boyutlandırma ve MRZ tarama alanı
        img_resized = cv2.resize(img, (1200, 800))
        mrz_roi = img_resized[450:780, 20:1180] 

        for pass_num in range(3):
            thresh = self.apply_filters(mrz_roi, pass_num)
            results = self.reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<')
            all_text = "".join([t.upper() for t in results])
            
            print(f"--- PASS {pass_num} RAW TEXT: {all_text}")

            # 1. Pasaport (TD3 - 44 Karakter x 2 Satır) Kontrolü
            td3_lines = re.findall(r'[A-Z0-9<]{42,46}', all_text)
            if len(td3_lines) >= 2:
                mrz_data = "\n".join([line.ljust(44, '<')[:44] for line in td3_lines[:2]])
                try:
                    checker = TD3CodeChecker(mrz_data)
                    return self.format_response(checker, "PASSPORT", pass_num)
                except: pass

            # 2. Kimlik Kartı (TD1 - 30 Karakter x 3 Satır) Kontrolü
            td1_lines = re.findall(r'[A-Z0-9<]{28,32}', all_text)
            if len(td1_lines) >= 3:
                processed = []
                for i, l in enumerate(td1_lines[:3]):
                    line = l.ljust(30, '<')[:30]
                    if i == 1: line = self.force_numeric(line)
                    processed.append(line)
                
                try:
                    checker = TD1CodeChecker("\n".join(processed))
                    return self.format_response(checker, "ID_CARD", pass_num)
                except: pass

        return {"status": "fail", "message": "mrz_not_detected"}

    def format_response(self, checker, doc_type, pass_num):
        """API yanıtını profesyonel İngilizce formatında hazırlar"""
        fields = checker.fields()
        
        # Checksum doğrulama kontrolü (Kütüphane versiyonuna uyumlu)
        report = checker.report
        report_data = report() if callable(report) else report
        is_valid = len(report_data.errors) == 0

        if not is_valid:
             print(f"!!! CHECKSUM ERROR: {report_data.errors}")
        
        return {
            "status": "success",
            "document_type": doc_type,
            "country": fields.country,
            "first_name": self.clean_field(fields.name),
            "last_name": self.clean_field(fields.surname),
            "document_number": fields.document_number.replace('<', ''),
            "verification": "SUCCESS" if is_valid else "CHECKSUM_ERROR",
            "pass_used": pass_num
        }