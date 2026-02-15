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
SAVE_FILE = "verified_identities.csv"
ARCHIVE_FOLDER = "archive"

if not os.path.exists(ARCHIVE_FOLDER):
    os.makedirs(ARCHIVE_FOLDER)

def save_all_data(data, img):
    """Saves validation results to CSV and archives the image"""
    exists = os.path.isfile(SAVE_FILE)
    timestamp_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_short = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with open(SAVE_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not exists:
            # Header updated to English
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

    # Filename generated using English keys
    safe_name = f"{data.get('first_name')}_{data.get('last_name')}_{timestamp_short}.jpg".replace(" ", "_")
    archive_path = os.path.join(ARCHIVE_FOLDER, safe_name)
    cv2.imwrite(archive_path, img)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({"status": "error", "message": "no_image_data"}), 400

        img_base64 = data['image'].split(",")[1]
        nparr = np.frombuffer(base64.b64decode(img_base64), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        temp_path = "current_scan.jpg"
        cv2.imwrite(temp_path, img)
        
        # Call the updated English validator
        result = validator.process_mrz(temp_path)
        
        if result["status"] == "success":
            # Log Checksum errors internally
            if result.get("verification") == "CHECKSUM_ERROR":
                logger.warning(f"Checksum mismatch detected for: {result.get('first_name')} {result.get('last_name')}")

            # Persist data using English keys
            save_all_data(result, img)
            
            # Return success to frontend
            return jsonify(result)
        else:
            return jsonify({"status": "fail", "message": result.get("message")})

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # host='0.0.0.0' allows access via Droplet IP: 146.190.238.189
    app.run(host='0.0.0.0', port=5001, debug=False)