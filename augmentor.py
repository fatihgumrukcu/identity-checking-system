import cv2
import numpy as np
import os
import random

class DataAugmentor:
    def __init__(self, input_dir="images/clean", output_dir="dirty_images"):
        self.input_dir = input_dir
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def apply_perspective_warp(self, img):
        """Karta rastgele perspektif (bakış açısı) kayması ekler"""
        h, w = img.shape[:2]
        # Orijinal köşe noktaları
        pts1 = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
        
        # Rastgele kaydırma miktarı (Perspektif şiddeti)
        warp_val = 0.15 # %15 sapma
        
        # Yeni köşe noktalarını rastgele belirle
        pts2 = np.float32([
            [random.uniform(0, w * warp_val), random.uniform(0, h * warp_val)],
            [w - random.uniform(0, w * warp_val), random.uniform(0, h * warp_val)],
            [random.uniform(0, w * warp_val), h - random.uniform(0, h * warp_val)],
            [w - random.uniform(0, w * warp_val), h - random.uniform(0, h * warp_val)]
        ])
        
        matrix = cv2.getPerspectiveTransform(pts1, pts2)
        # Arka planı nötr gri yapıyoruz ki kartın dışı belli olsun
        return cv2.warpPerspective(img, matrix, (w, h), borderValue=(127, 127, 127))

    def apply_distance_and_bg(self, img):
        """Kartı önce yamultur, sonra uzaklaştırır ve arka plana yerleştirir"""
        # Önce perspektifi bozuyoruz
        img = self.apply_perspective_warp(img)
        
        h, w = img.shape[:2]
        scale = random.uniform(0.25, 0.4) # Uzaklığı biraz daha artırdık
        new_w, new_h = int(w * scale), int(h * scale)
        resized_card = cv2.resize(img, (new_w, new_h))

        bg_color = random.randint(30, 150)
        canvas = np.full((600, 1000, 3), bg_color, dtype=np.uint8)
        noise = np.random.normal(0, 5, canvas.shape).astype(np.uint8)
        canvas = cv2.add(canvas, noise)

        y_off = random.randint(50, 600 - new_h - 50)
        x_off = random.randint(50, 1000 - new_w - 50)
        
        canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized_card
        return canvas

    def apply_glare(self, img):
        h, w = img.shape[:2]
        overlay = img.copy()
        circle_center = (random.randint(w//4, 3*w//4), random.randint(h//4, 3*h//4))
        cv2.circle(overlay, circle_center, random.randint(80, 200), (255, 255, 255), -1)
        return cv2.addWeighted(overlay, 0.3, img, 0.7, 0)

    def apply_motion_blur(self, img):
        size = random.choice([5, 7, 9])
        kernel = np.zeros((size, size))
        kernel[int((size-1)/2), :] = np.ones(size)
        kernel = kernel / size
        return cv2.filter2D(img, -1, kernel)

    def apply_low_light(self, img):
        dark = cv2.convertScaleAbs(img, alpha=0.3, beta=-30)
        noise = np.random.normal(0, 20, dark.shape).astype(np.uint8)
        return cv2.add(dark, noise)

    def run(self):
        valid_extensions = ('.jpg', '.png', '.jpeg')
        files = [f for f in os.listdir(self.input_dir) if f.lower().endswith(valid_extensions)]
        
        print(f"--- 📐 Perspektif ve Mesafe Destekli Augmentor Başlatıldı ---")
        
        for f in files:
            img_path = os.path.join(self.input_dir, f)
            img = cv2.imread(img_path)
            if img is None: continue
            
            name = os.path.splitext(f)[0]
            
            # 1. Yamuk + Uzak + Parlama
            dist_img = self.apply_distance_and_bg(img)
            cv2.imwrite(os.path.join(self.output_dir, f"{name}_aci_uzak_parlak.jpg"), self.apply_glare(dist_img))
            
            # 2. Yamuk + Uzak + Bulanık
            dist_img = self.apply_distance_and_bg(img)
            cv2.imwrite(os.path.join(self.output_dir, f"{name}_aci_uzak_bulanik.jpg"), self.apply_motion_blur(dist_img))
            
            # 3. Yamuk + Uzak + Karanlık
            dist_img = self.apply_distance_and_bg(img)
            cv2.imwrite(os.path.join(self.output_dir, f"{name}_aci_uzak_karanlik.jpg"), self.apply_low_light(dist_img))

        print(f"✅ İşlem tamam! Yeni veri seti 'Açılı ve Uzak' çekimlerle güncellendi.")

if __name__ == "__main__":
    augmentor = DataAugmentor()
    augmentor.run()