from validator import IdentityValidator
import os

validator = IdentityValidator()
folder_path = "images" # Görsellerinin olduğu klasör adı

for file in os.listdir(folder_path):
    if file.endswith((".png", ".jpg", ".jpeg")):
        print(f"\nİşleniyor: {file}")
        path = os.path.join(folder_path, file)
        
        # Yeni MRZ process fonksiyonunu çağırıyoruz
        result = validator.process_mrz(path)
        
        if result["status"] == "ok":
            print(f"  > Durum: BAŞARILI")
            print(f"  > Ülke: {result['ulke']}")
            print(f"  > İsim: {result['ad']} {result['soyad']}")
            print(f"  > Belge No: {result['belge_no']}")
            print(f"  > Kimlik No: {result['tc_no']}")
        else:
            print(f"  > Durum: HATA")
            print(f"  > Sebep: {result.get('msg')}")
            if "raw_mrz" in result:
                print(f"  > Okunan Ham Veri: {result['raw_mrz']}")