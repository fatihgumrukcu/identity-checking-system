import cv2
import easyocr
import re
import numpy as np
from mrz.checker.td1 import TD1CodeChecker

class IdentityValidator:
    def __init__(self):
        # Model dosyalarını sunucuda CPU ile çalışacak şekilde yükler
        self.reader = easyocr.Reader(['en'], gpu=False)

    def force_numeric(self, text):
        """Özellikle tarih ve numara alanlarındaki harf hatalarını rakama çevirir."""
        mapping = {'O': '0', 'I': '1', 'L': '1', 'G': '6', 'S': '5', 'B': '8', 'T': '7', 'Z': '2'}
        for char, digit in mapping.items():
            text = text.replace(char, digit)
        return text

    def clean_field(self, text):
        if not text: return "Bilinmiyor"
        # İsimlerdeki rakam hatalarını harfe çevirir
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

        img_resized = cv2.resize(img, (1000, 600))
        mrz_roi = img_resized[370:590, 10:990]

        for pass_num in range(3):
            thresh = self.apply_filters(mrz_roi, pass_num)
            results = self.reader.readtext(thresh, detail=0, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<')
            all_text = "".join([t.upper() for t in results])

            # Debug: OCR'ın yakaladığı tüm ham metni logla
            print(f"--- PASS {pass_num} HAM METİN: {all_text}")

            lines = re.findall(r'[A-Z0-9<]{30}', all_text)
            
            if len(lines) >= 3:
                # Kritik: 2. satırı rakamlara zorla (Tarih ve Checksumların olduğu yer)
                line1 = lines[0]
                line2 = self.force_numeric(lines[1])
                line3 = lines[2]
                
                mrz_data = f"{line1}\n{line2}\n{line3}"
                
                # Debug: Oluşturulan MRZ bloğunu logla
                print(f"--- ANALİZ EDİLEN MRZ:\n{mrz_data}")
                
                try:
                    checker = TD1CodeChecker(mrz_data)
                    fields = checker.fields()
                    
                    # Eğer checksum hatası varsa hangi alanın hatalı olduğunu logla
                    if not checker.valid:
                        print(f"!!! CHECKSUM HATASI DETAYI: {checker.report()}") 

                    return {
                        "status": "ok",
                        "ulke": fields.country,
                        "ad": self.clean_field(fields.name),
                        "soyad": self.clean_field(fields.surname),
                        "tc_no": fields.optional_data.replace('<', ''),
                        "belge_no": fields.document_number.replace('<', ''),
                        "dogrulama": "BAŞARILI" if checker.valid else "CHECKSUM_HATASI",
                        "pass_used": pass_num
                    }
                except Exception as e:
                    print(f"!!! MRZ PARSE HATASI: {str(e)}")
                    continue 

        return {"status": "fail", "msg": "mrz_okunamadi"}