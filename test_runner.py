from validator import IdentityValidator
import os
import csv

validator = IdentityValidator()
input_folder = "dirty_images"
report_file = "stres_test_raporu.csv"

# Rapor dosyasını hazırla
with open(report_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Dosya", "Senaryo", "Sonuç", "Ülke", "Hata Mesajı"])

print(f"--- 🛡️ STRES TESTİ BAŞLIYOR ---")

files = [f for f in os.listdir(input_folder) if f.endswith(('.jpg', '.png'))]
files.sort()

results_summary = {"Parlama": [0, 0], "Bulanıklık": [0, 0], "Karanlık": [0, 0]} # [Başarı, Toplam]

for file in files:
    path = os.path.join(input_folder, file)
    scenario = "Parlama" if "parlak" in file else "Bulanıklık" if "bulanik" in file else "Karanlık"
    
    res = validator.process_mrz(path)
    
    is_success = res["status"] == "ok"
    results_summary[scenario][1] += 1
    if is_success: results_summary[scenario][0] += 1
    
    status_icon = "✅" if is_success else "❌"
    print(f"{status_icon} [{scenario}] {file} -> {'BAŞARILI' if is_success else res.get('msg')}")
    
    # CSV'ye yaz
    with open(report_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([file, scenario, "BAŞARILI" if is_success else "HATA", res.get('ulke', '-'), res.get('msg', '-')])

print("\n" + "="*40)
print("📊 STRES TESTİ ÖZETİ")
for s, counts in results_summary.items():
    perc = (counts[0] / counts[1]) * 100 if counts[1] > 0 else 0
    print(f"{s}: %{perc:.1f} Başarı ({counts[0]}/{counts[1]})")
print("="*40)
print(f"Detaylı rapor '{report_file}' dosyasına kaydedildi.")