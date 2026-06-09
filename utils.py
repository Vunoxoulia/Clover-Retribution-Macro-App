import mss
import numpy as np
import cv2
import win32api
import win32con
import keyboard
import time
from PIL import Image

class SpatialUtils:
    def __init__(self):
        self.sct = mss.mss()
        self.ocr_reader = None

    def _init_ocr(self):
        if self.ocr_reader is None:
            import easyocr
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)

    def get_text_from_region(self, region):
        
        self._init_ocr()
        img = self.capture_screen(region)
        results = self.ocr_reader.readtext(img, detail=1, paragraph=False)
        return results

    def _parse_target_color(self, target_color):
        
        if isinstance(target_color, str):
            target_color = target_color.lstrip('#').replace('0x', '')
            return tuple(int(target_color[i:i+2], 16) for i in (0, 2, 4))
        return target_color

    def capture_screen(self, region=None):
        
        if region:
            monitor = {"top": region[1], "left": region[0], "width": region[2] - region[0], "height": region[3] - region[1]}
        else:
            monitor = self.sct.monitors[1]
        
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

    def pixel_search_region(self, region, target_color, tolerance=10, img=None):
        
        if img is None:
            img = self.capture_screen(region)
            
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)])
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)])
        
        mask = cv2.inRange(img_bgr, lower, upper)
        
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        centers = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= 2: 
                cx, cy, w, h = cv2.boundingRect(contour)
                centers.append((region[0] + cx + w // 2, region[1] + cy + h // 2))
                
        
        if centers:
            centers.sort(key=lambda p: p[1])
            return centers
        return None

    def check_pixel_area(self, region, target_color, tolerance=10):
        
        img = self.capture_screen(region)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)])
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)])
        
        mask = cv2.inRange(img_bgr, lower, upper)
        return np.any(mask > 0)

    def pixel_search(self, region, target_color, tolerance=10):
        
        img = self.capture_screen(region)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)])
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)])
        
        mask = cv2.inRange(img_bgr, lower, upper)
        coords = np.column_stack(np.where(mask > 0))
        
        if len(coords) > 0:
            
            return (region[0] + coords[0][1], region[1] + coords[0][0])
        return None

    def pixel_search_existing_frame(self, img_rgb, region, target_color, tolerance=15):
        
        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)], dtype="uint8")
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)], dtype="uint8")
        
        mask = cv2.inRange(img_bgr, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            if cv2.contourArea(contour) > 10: 
                cx, cy, w, h = cv2.boundingRect(contour)
                center_x = cx + (w // 2)
                center_y = cy + (h // 2)
                return (region[0] + center_x, region[1] + center_y)
                
        return None

    def image_search(self, image_path, region=None, threshold=0.8):
        
        try:
            template = cv2.imread(image_path)
            if template is None:
                return None
            template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
            th, tw = template.shape[:2]

            img = self.capture_screen(region)
            
            res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= threshold:
                center_x = max_loc[0] + tw // 2
                center_y = max_loc[1] + th // 2
                
                if region:
                    return (region[0] + center_x, region[1] + center_y)
                return (center_x, center_y)
        except Exception as e:
            print(f"Image search error: {e}")
        return None

    def mouse_click(self, x, y, button='left'):
        
        win32api.SetCursorPos((int(x), int(y)))
        if button == 'left':
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif button == 'right':
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

    def mouse_move(self, x, y):
        
        win32api.SetCursorPos((int(x), int(y)))

    def send_key(self, key, duration=0.05):
        
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)