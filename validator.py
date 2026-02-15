import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker

class IdentityValidator:
    def __init__(self):
        # MRZ karakterleri için sadece İngilizce yeterlidir
        self.reader = easyocr.Reader(['en'], gpu=False)

    def force_numeric(self, text):
        """Sayısal alanlardaki tipik OCR hatalarını onarır"""
        mapping = {'O': '0', 'I': '1', 'L': '1', 'G': '6', 'S': '5', 'B': '8', 'T': '7', 'Z': '2'}
        for char, digit in mapping.items():
            text = text.replace(char, digit)
        return text

    def clean_field(self, text):
        if not text: return "Bilinmiyor"
        # OCR karakter karıştırmalarını düzelt
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
        elif pass_num == 1: # Karanlık Mod (Yüksek Kontrast)
            enhanced = cv2.convertScaleAbs(cl_img, alpha=2.3, beta=-60)
            return cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        elif pass_num == 2: # Keskinleştirme Odaklı
            kernel = np.array([[-1,-1,-1], [-1,10,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(cl_img, -1, kernel)
            return cv2.adaptiveThreshold(sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 13, 5)
        else: # İnce Detay Modu
            return cv2.adaptiveThreshold(cl_img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "msg": "dosya_bulunamadi"}

        # Boyutlandırmayı ve ROI alanını biraz genişleterek esneklik sağlıyoruz
        img_resized = cv2.resize(img, (1200, 800))
        # Tarama alanını dikeyde genişlettik (Bulgaristan/Avusturya kartları için kritik)
        mrz_roi = img_resized[300:790, 10:1190] 

        for pass_num in range(4):
            thresh = self.apply_filters(mrz_roi, pass_num)
            results = self.reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<')          
            clean_text = "".join([re.sub(r'[^A-Z0-9<]', '', t.upper()) for t in results])

            # 1. Pasaport (TD3) Kontrolü - 44 Karakter
            lines = re.findall(r'[A-Z0-9<]{40,46}', clean_text)
            if len(lines) >= 2:
                mrz_data = "\n".join([l.ljust(44, '<')[:44] for l in lines[:2]])
                try:
                    checker = TD3CodeChecker(mrz_data)
                    return self.prepare_result(checker, pass_num)
                except: pass

            # 2. Kimlik (TD1) Kontrolü - 30 Karakter
            lines = re.findall(r'[A-Z0-9<]{28,32}', clean_text)
            if len(lines) >= 3:
                # 2. satırı sayısal onarıma sok (Tarih güvenliği)
                processed = [lines[0].ljust(30, '<')[:30], 
                             self.force_numeric(lines[1].ljust(30, '<')[:30]), 
                             lines[2].ljust(30, '<')[:30]]
                try:
                    checker = TD1CodeChecker("\n".join(processed))
                    return self.prepare_result(checker, pass_num)
                except: pass

        return {"status": "fail", "msg": "mrz_formati_bulunamadi"}

    def prepare_result(self, checker, pass_num):
        fields = checker.fields()
        # Checksum kontrolü
        report = checker.report()
        is_valid = len(report.errors) == 0
        
        return {
            "status": "ok",
            "ulke": fields.country,
            "ad": self.clean_field(fields.name),
            "soyad": self.clean_field(fields.surname),
            "tc_no": fields.optional_data.replace('<', '') if hasattr(fields, 'optional_data') else "",
            "belge_no": fields.document_number.replace('<', ''),
            "dogrulama": "BAŞARILI" if is_valid else "CHECKSUM_HATASI",
            "pass_used": pass_num
        }