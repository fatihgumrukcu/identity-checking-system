import os
import base64
import cv2
import numpy as np
import csv
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from validator import IdentityValidator

app = Flask(__name__)
validator = IdentityValidator()

# Dosya ve Klasör Ayarları
SAVE_FILE = "dogrulanan_kimlikler.csv"
ARCHIVE_FOLDER = "arsiv"

if not os.path.exists(ARCHIVE_FOLDER):
    os.makedirs(ARCHIVE_FOLDER)

def save_all_data(data, img):
    exists = os.path.isfile(SAVE_FILE)
    timestamp_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_short = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with open(SAVE_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Tarih", "Ülke", "Ad", "Soyad", "BelgeNo", "KimlikNo"])
        writer.writerow([
            timestamp_full,
            data.get('ulke'),
            data.get('ad'),
            data.get('soyad'),
            data.get('belge_no'),
            data.get('tc_no')
        ])

    file_name = f"{data.get('ad')}_{data.get('soyad')}_{timestamp_short}.jpg".replace(" ", "_")
    archive_path = os.path.join(ARCHIVE_FOLDER, file_name)
    cv2.imwrite(archive_path, img)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.json
        img_base64 = data['image'].split(",")[1]
        
        nparr = np.frombuffer(base64.b64decode(img_base64), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        temp_path = "current_scan.jpg"
        cv2.imwrite(temp_path, img)
        
        result = validator.process_mrz(temp_path)
        
        if result["status"] == "ok":
            save_all_data(result, img)
            return jsonify(result)
        else:
            return jsonify({"status": "error", "msg": result.get("msg")})

    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)})

# --- CANLI SUNUCU AYARI ---
if __name__ == '__main__':
    # host='0.0.0.0' sayesinde 146.190.238.189 üzerinden erişim sağlanır
    # debug=False yapıldı, canlı ortamda güvenlik ve hız için gereklidir
    app.run(host='0.0.0.0', port=5001, debug=False)