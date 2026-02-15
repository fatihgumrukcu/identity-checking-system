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

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# File and Folder Settings
SAVE_FILE = os.path.join(os.getcwd(), "verified_identities.csv")
ARCHIVE_FOLDER = os.path.join(os.getcwd(), "archive")

os.makedirs(ARCHIVE_FOLDER, exist_ok=True)

def save_all_data(data, img):
    """Saves validation results to CSV and archives the image"""
    exists = os.path.isfile(SAVE_FILE)
    timestamp_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_short = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        with open(SAVE_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(["Timestamp", "Type", "Country", "First Name", "Last Name", "Doc Number", "Verification", "Doc Checksum", "Birth Checksum", "Expiry Checksum", "Logical Date Check"])
            
            writer.writerow([
                timestamp_full,
                data.get('document_type', 'ID'),
                data.get('ulke'),
                data.get('ad'),
                data.get('soyad'),
                data.get('belge_no'),
                data.get('dogrulama'),
                data.get('doc_checksum', ''),
                data.get('birth_checksum', ''),
                data.get('expiry_checksum', ''),
                data.get('logical_date_check', '')
            ])

        safe_name = f"{data.get('ad')}_{data.get('soyad')}_{timestamp_short}.jpg".replace(" ", "_")
        archive_path = os.path.join(ARCHIVE_FOLDER, safe_name)
        cv2.imwrite(archive_path, img)
        logger.info(f"Data saved: {safe_name}")
    except Exception as e:
        logger.error(f"Error saving data: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"status": "error", "message": "No image data provided"}), 400

        # Decode base64 image
        try:
            img_base64 = data['image'].split(",")[1]
        except IndexError:
            return jsonify({"status": "error", "message": "Invalid image format"}), 400

        nparr = np.frombuffer(base64.b64decode(img_base64), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"status": "error", "message": "Could not decode image"}), 400
        
        temp_path = os.path.join(os.getcwd(), "current_scan.jpg")
        cv2.imwrite(temp_path, img)
        
        # Process MRZ
        result = validator.process_mrz(temp_path)
        
        if result["status"] == "ok":
            if result.get("dogrulama") == "CHECKSUM_HATASI":
                logger.warning(f"Checksum mismatch: {result.get('ad')} {result.get('soyad')}")

            save_all_data(result, img)
            return jsonify(result)
        else:
            return jsonify({"status": "fail", "message": result.get("msg")}), 400

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)