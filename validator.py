import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td3 import TD3CodeChecker

class IdentityValidator:
    def __init__(self):
        self.reader = easyocr.Reader(['en'], gpu=False)

    def force_numeric(self, text):
        mapping = {'O': '0', 'I': '1', 'L': '1', 'G': '6', 'S': '5', 'B': '8', 'T': '7', 'Z': '2'}
        for char, digit in mapping.items():
            text = text.replace(char, digit)
        return text

    def clean_field(self, text):
        if not text: return "Bilinmiyor"
        text = text.replace('6', 'G').replace('0', 'O').replace('1', 'I').replace('5', 'S').replace('8', 'B')
        return text.replace('<', ' ').strip()

    def apply_filters(self, roi, pass_num):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        cl_img = clahe.apply(gray)

        if pass_num == 0:
            enhanced = cv2.convertScaleAbs(cl_img, alpha=1.5, beta=0)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 1:
            return cv2.adaptiveThreshold(cl_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8)
        else:
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(cl_img, -1, kernel)
            return cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "msg": "dosya_bulunamadi"}

        img_resized = cv2.resize(img, (1200, 800))
        # ROI: Pasaport ve Kimliklerin MRZ alanını kapsayacak geniş bölge
        mrz_roi = img_resized[450:780, 20:1180] 

        for pass_num in range(3):
            thresh = self.apply_filters(mrz_roi, pass_num)
            results = self.reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<')
            all_text = "".join([t.upper() for t in results])
            
            print(f"--- PASS {pass_num} HAM METİN: {all_text}")

            # 1. PASAPORT (TD3) KONTROLÜ - 44 Karakterli 2 Satır
            td3_lines = re.findall(r'[A-Z0-9<]{42,46}', all_text)
            if len(td3_lines) >= 2:
                mrz_data = "\n".join([line.ljust(44, '<')[:44] for line in td3_lines[:2]])
                try:
                    checker = TD3CodeChecker(mrz_data)
                    fields = checker.fields()
                    return self.format_response(checker, fields, "PASAPORT", pass_num)
                except: pass

            # 2. KİMLİK (TD1) KONTROLÜ - 30 Karakterli 3 Satır
            td1_lines = re.findall(r'[A-Z0-9<]{28,32}', all_text)
            if len(td1_lines) >= 3:
                processed = []
                for i, l in enumerate(td1_lines[:3]):
                    line = l.ljust(30, '<')[:30]
                    if i == 1: line = self.force_numeric(line)
                    processed.append(line)
                
                try:
                    checker = TD1CodeChecker("\n".join(processed))
                    fields = checker.fields()
                    return self.format_response(checker, fields, "KİMLİK", pass_num)
                except: pass

        return {"status": "fail", "msg": "mrz_okunamadi"}

    def format_response(self, checker, fields, doc_type, pass_num):
        # Kütüphane sürümüne göre valid kontrolü
        try:
            if hasattr(checker, 'valid'):
                is_valid = checker.valid
            elif hasattr(checker, 'report'):
                report = checker.report
                errors = report() if callable(report) else (report.errors if hasattr(report, 'errors') else [])
                is_valid = len(errors) == 0
            else:
                is_valid = True  # Fallback
        except Exception as e:
            print(f"Validation check error: {e}")
            is_valid = False
        
        return {
            "status": "ok",
            "document_type": doc_type,
            "ulke": fields.country,
            "ad": self.clean_field(fields.name),
            "soyad": self.clean_field(fields.surname),
            "belge_no": fields.document_number.replace('<', ''),
            "tc_no": fields.optional_data.replace('<', '') if hasattr(fields, 'optional_data') else '',
            "dogrulama": "BAŞARILI" if is_valid else "CHECKSUM_HATASI",
            "pass_used": pass_num
        }