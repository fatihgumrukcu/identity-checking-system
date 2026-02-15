import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td3 import TD3CodeChecker

class IdentityValidator:
    def __init__(self):
        # OCR modelini daha iyi sonuç için GPU=False (CPU'da daha kararlı olabilir) 
        # veya varsa GPU=True yapabilirsin.
        self.reader = easyocr.Reader(['en'], gpu=False)

    def clean_mrz_line(self, text):
        """MRZ satırındaki çöp karakterleri temizler ve standartlaştırır."""
        # Sadece A-Z, 0-9 ve < karakterlerini tut
        text = re.sub(r'[^A-Z0-9<]', '', text.upper())
        return text

    def apply_advanced_preprocessing(self, image):
        """Görüntüyü OCR için optimize eder."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 1. Gürültü Azaltma
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 2. Kontrastı Artırma (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrast = clahe.apply(blurred)
        
        # 3. Dinamik Eşikleme (Morfometrik İşlemler)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(contrast, kernel, iterations=1)
        eroded = cv2.erode(dilated, kernel, iterations=1)
        
        return eroded

    def process_mrz(self, path):
        img = cv2.imread(path)
        if img is None: return {"status": "error", "msg": "dosya_bulunamadi"}

        # ROI'yi dinamik tutmak için resmi büyük ölçekte işliyoruz
        h, w = img.shape[:2]
        # Resmin sadece alt %50'sini al (MRZ her zaman alttadır)
        roi = img[int(h*0.4):h, 0:w]
        
        # Farklı ön işleme kombinasyonları ile 3 deneme yap (Pass sistemi)
        for pass_num in range(3):
            if pass_num == 0:
                processed = self.apply_advanced_preprocessing(roi)
            elif pass_num == 1:
                # Daha yüksek kontrast denemesi
                processed = cv2.convertScaleAbs(roi, alpha=1.5, beta=10)
                processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            else:
                # Orijinal ROI üzerinde gri tonlama
                processed = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

            # OCR Oku
            results = self.reader.readtext(processed, detail=0, paragraph=False)
            all_text_lines = [self.clean_mrz_line(t) for t in results if len(self.clean_mrz_line(t)) > 10]
            
            combined_text = "".join(all_text_lines)
            print(f"--- PASS {pass_num} CLEANED TEXT: {combined_text}")

            # TD1 (Kimlik) Arama: 30 karakterlik 3 grup
            td1_match = re.findall(r'[A-Z0-9<]{25,31}', combined_text)
            if len(td1_match) >= 3:
                # Satırları 30'a tamamla
                mrz_lines = [line.ljust(30, '<')[:30] for line in td1_match[:3]]
                mrz_data = "\n".join(mrz_lines)
                try:
                    checker = TD1CodeChecker(mrz_data)
                    if checker.report().valid or pass_num == 2: # Pass 2'de zorla döndür
                        return self.format_response(checker, checker.fields(), "KİMLİK", pass_num)
                except: pass

            # TD3 (Pasaport) Arama: 44 karakterlik 2 grup
            td3_match = re.findall(r'[A-Z0-9<]{40,45}', combined_text)
            if len(td3_match) >= 2:
                mrz_lines = [line.ljust(44, '<')[:44] for line in td3_match[:2]]
                mrz_data = "\n".join(mrz_lines)
                try:
                    checker = TD3CodeChecker(mrz_data)
                    return self.format_response(checker, checker.fields(), "PASAPORT", pass_num)
                except: pass

        return {"status": "fail", "msg": "mrz_okunamadi"}

    def format_response(self, checker, fields, doc_type, pass_num):
        # Checksum analizi
        report = checker.report()
        is_valid = report.valid
        
        # Eğer checksum hatası varsa hangi alanların hatalı olduğunu logla
        if not is_valid:
            print(f"!!! CHECKSUM ERRORS: {report.errors}")

        return {
            "status": "success",
            "document_type": doc_type,
            "country": fields.country,
            "first_name": fields.name.replace('<', ' ').strip(),
            "last_name": fields.surname.replace('<', ' ').strip(),
            "document_number": fields.document_number.replace('<', ''),
            "verification": "SUCCESS" if is_valid else "CHECKSUM_ERROR",
            "pass_used": pass_num,
            "raw_report": str(report.errors) if not is_valid else None
        }