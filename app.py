import os
import base64
import cv2
import numpy as np
import csv
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from validator import IdentityValidator

app = Flask(__name__)
validator = IdentityValidator()

# Sunucu loglama ayarları - Hataları terminalden izlemek için kritik
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Dosya ve Arşiv Ayarları
SAVE_FILE = "verified_identities.csv"
ARCHIVE_FOLDER = "archive"

if not os.path.exists(ARCHIVE_FOLDER):
    os.makedirs(ARCHIVE_FOLDER)

def save_all_data(data, img):
    """Doğrulanan verileri CSV'ye yazar ve görseli arşivler"""
    exists = os.path.isfile(SAVE_FILE)
    timestamp_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_short = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with open(SAVE_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not exists:
            # Başlıklar İngilizce olarak güncellendi
            writer.writerow(["Timestamp", "Type", "Country", "First Name", "Last Name", "Doc Number", "Verification"])
        
        writer.writerow([
            timestamp_full,
            data.get('document_type'),
            data.get('country'),
            data.get('first_name'),
            data.get('last_name'),
            data.get('document_number'),
            data.get('verification')
        ])

    # Dosya ismi oluşturulurken yeni anahtarlar kullanılıyor
    safe_first_name = str(data.get('first_name', 'Unknown')).replace(" ", "_")
    safe_last_name = str(data.get('last_name', 'Unknown')).replace(" ", "_")
    file_name = f"{safe_first_name}_{safe_last_name}_{timestamp_short}.jpg"
    archive_path = os.path.join(ARCHIVE_FOLDER, file_name)
    cv2.imwrite(archive_path, img)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"status": "error", "message": "No image data provided"}), 400

        # Base64 görseli decode etme
        img_base64 = data['image'].split(",")[1]
        nparr = np.frombuffer(base64.b64decode(img_base64), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        temp_path = "current_scan.jpg"
        cv2.imwrite(temp_path, img)
        
        # Validator çağrısı - Artık İngilizce anahtarlar dönüyor
        result = validator.process_mrz(temp_path)
        
        # 'success' kontrolü validator.py ile senkronize edildi
        if result.get("status") == "success":
            save_all_data(result, img)
            return jsonify(result)
        else:
            # Hata durumunda frontend'in 'null' almaması için uygun mesaj dönülüyor
            return jsonify({
                "status": "fail", 
                "message": result.get("message", "MRZ not detected")
            })

    except Exception as e:
        logger.error(f"Upload Error: {str(e)}")
        return jsonify({"status": "error", "message": f"Server error: {str(e)}"}), 500

# Droplet üzerinde 5001 portundan yayın yapılması için ayar
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)