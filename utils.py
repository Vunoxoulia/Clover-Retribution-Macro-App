import mss
import numpy as np
import cv2
import keyboard
import time
import threading
import pywinctl
from PIL import Image
import sys
import ctypes
import random
from pynput.mouse import Button, Controller as MouseController

IS_WINDOWS = sys.platform.startswith('win')

if IS_WINDOWS:
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class MouseInput(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long),
                    ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL)]

    class KeyBdInput(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", PUL)]

    class HardwareInput(ctypes.Structure):
        _fields_ = [("uMsg", ctypes.c_ulong),
                    ("wParamL", ctypes.c_short),
                    ("wParamH", ctypes.c_ushort)]

    class Input_I(ctypes.Union):
        _fields_ = [("mi", MouseInput),
                    ("ki", KeyBdInput),
                    ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong),
                    ("ii", Input_I)]

    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_VIRTUALDESK = 0x4000

class RobloxInputDriver:
    _mouse = MouseController()
    _lock = threading.RLock()

    @classmethod
    def move_to(cls, x, y):
        with cls._lock:
            if IS_WINDOWS:
                left = ctypes.windll.user32.GetSystemMetrics(76)                      
                top = ctypes.windll.user32.GetSystemMetrics(77)                       
                width = ctypes.windll.user32.GetSystemMetrics(78)                      
                height = ctypes.windll.user32.GetSystemMetrics(79)                     
                
                if width <= 0:
                    width = ctypes.windll.user32.GetSystemMetrics(0)                            
                if height <= 0:
                    height = ctypes.windll.user32.GetSystemMetrics(1)                             
                
                nx = int((x - left) * 65535 / (width - 1)) if width > 1 else 0
                ny = int((y - top) * 65535 / (height - 1)) if height > 1 else 0
                
                extra = ctypes.c_ulong(0)
                ii_ = Input_I()
                ii_.mi = MouseInput(nx, ny, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, 0, ctypes.pointer(extra))
                move_input = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(move_input), ctypes.sizeof(move_input))
            else:
                cls._mouse.position = (int(x), int(y))

    @classmethod
    def click_at(cls, x, y, duration=0.03, button='left'):
        with cls._lock:
            if IS_WINDOWS:
                cls.move_to(x, y)
                time.sleep(0.02)
                
                extra = ctypes.c_ulong(0)
                if button == 'left':
                    flags_down = MOUSEEVENTF_LEFTDOWN
                    flags_up = MOUSEEVENTF_LEFTUP
                else:
                    flags_down = MOUSEEVENTF_RIGHTDOWN
                    flags_up = MOUSEEVENTF_RIGHTUP

                ii_down = Input_I()
                ii_down.mi = MouseInput(0, 0, 0, flags_down, 0, ctypes.pointer(extra))
                input_down = Input(ctypes.c_ulong(INPUT_MOUSE), ii_down)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(input_down), ctypes.sizeof(input_down))
                
                time.sleep(duration + random.uniform(0.005, 0.015))
                
                ii_up = Input_I()
                ii_up.mi = MouseInput(0, 0, 0, flags_up, 0, ctypes.pointer(extra))
                input_up = Input(ctypes.c_ulong(INPUT_MOUSE), ii_up)
                ctypes.windll.user32.SendInput(1, ctypes.pointer(input_up), ctypes.sizeof(input_up))
            else:
                cls.move_to(x, y)
                time.sleep(0.015) 
                pynput_button = Button.left if button == 'left' else Button.right
                cls._mouse.press(pynput_button)
                time.sleep(duration)
                cls._mouse.release(pynput_button)

class SpatialUtils:
    def __init__(self):
        self._thread_local = threading.local()
        self._key_lock = threading.RLock()
        self.ocr_reader = None

    @property
    def sct(self):
        if not hasattr(self._thread_local, 'sct'):
            self._thread_local.sct = mss.mss()
        return self._thread_local.sct

    def _init_ocr(self):
        if self.ocr_reader is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                import platform
                
                providers = ['CPUExecutionProvider']
                system = platform.system()
                
                if system == 'Darwin': 
                    providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
                elif system == 'Linux':
                    
                    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                
                self.ocr_reader = RapidOCR(providers=providers)
                print(f"✅ RapidOCR initialized on {system}")
            except Exception as e:
                print(f"OCR (RapidOCR) Initialization error: {e}")
                self.ocr_reader = False

    def get_text_from_region(self, region, upscale=2):
        self._init_ocr()
        if not self.ocr_reader:
            return []
            
        img = self.capture_screen(region)
        
        if upscale > 1:
            h, w = img.shape[:2]
            img = cv2.resize(img, (w * upscale, h * upscale), interpolation=cv2.INTER_CUBIC)
        
        try:
            
            results, elapse = self.ocr_reader(img)
            
            final_results = []
            if results:
                for res in results:
                    bbox, text, conf = res
                    
                    if upscale > 1:
                        bbox = [[p[0] / upscale, p[1] / upscale] for p in bbox]
                    final_results.append((bbox, text, float(conf)))
            
            return final_results
        except Exception as e:
            print(f"RapidOCR Error: {e}")
            return []

    def capture_screen(self, region=None):
        if region:
            
            monitor = {
                "top": int(region[1]), 
                "left": int(region[0]), 
                "width": int(region[2] - region[0]), 
                "height": int(region[3] - region[1])
            }
        else:
            try:
                
                windows = pywinctl.getWindowsWithTitle("Roblox")
                if windows:
                    
                    active = pywinctl.getActiveWindow()
                    target = active if active and "Roblox" in active.title else windows[0]
                    
                    monitor = {
                        "top": target.top,
                        "left": target.left,
                        "width": target.width,
                        "height": target.height
                    }
                else:
                    monitor = self.sct.monitors[1]
            except Exception:
                monitor = self.sct.monitors[1]
        
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

    def capture_screen_bgr(self, region=None):
        if region:
            monitor = {
                "top": int(region[1]), 
                "left": int(region[0]), 
                "width": int(region[2] - region[0]), 
                "height": int(region[3] - region[1])
            }
        else:
            try:
                windows = pywinctl.getWindowsWithTitle("Roblox")
                if windows:
                    active = pywinctl.getActiveWindow()
                    target = active if active and "Roblox" in active.title else windows[0]
                    monitor = {
                        "top": target.top,
                        "left": target.left,
                        "width": target.width,
                        "height": target.height
                    }
                else:
                    monitor = self.sct.monitors[1]
            except Exception:
                monitor = self.sct.monitors[1]
        
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def pixel_search_region(self, region, target_color, tolerance=10, img=None, is_bgr=False):
        if img is None:
            img = self.capture_screen(region)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            if is_bgr:
                img_bgr = img
            else:
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

    def pixel_search_raw(self, region, target_color, tolerance=10):
        img = self.capture_screen(region)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)])
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)])
        mask = cv2.inRange(img_bgr, lower, upper)
        coords = np.column_stack(np.where(mask > 0))
        if len(coords) == 0:
            return []
        return [(region[0] + int(c[1]), region[1] + int(c[0])) for c in coords]

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
        RobloxInputDriver.click_at(x, y, duration=0.05, button=button)

    def mouse_move(self, x, y):
        RobloxInputDriver.move_to(x, y)

    def send_key(self, key, duration=0.05):
        """Send a keyboard key press with optional duration, thread‑safe."""
        with self._key_lock:
            keyboard.press(key)
            time.sleep(duration)
            keyboard.release(key)

    def find_color_x(self, region, target_color, tolerance=25, min_area=0):
        """Finds the average X coordinate of a color within a region, with optional size filtering."""
        img = self.capture_screen(region)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        r, g, b = self._parse_target_color(target_color)
        lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)], dtype="uint8")
        upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)], dtype="uint8")
        
        mask = cv2.inRange(img_bgr, lower, upper)
        
        if min_area > 0:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid_mask = np.zeros_like(mask)
            for cnt in contours:
                if cv2.contourArea(cnt) >= min_area:
                    cv2.drawContours(valid_mask, [cnt], -1, 255, -1)
            mask = valid_mask

        coords = np.column_stack(np.where(mask > 0))
        if len(coords) > 0:
            avg_x = np.mean(coords[:, 1])
            return region[0] + int(avg_x)
        return None

    def find_color_hsv_x(self, region, target_rgb, hue_tol=10, sat_min=50, val_min=50, min_area=0):
        """
        Brightness-robust detection using HSV. 
        Focuses on Hue (color) while being flexible with Value (brightness).
        """
        img_rgb = self.capture_screen(region)
        img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        
        target_img = np.uint8([[list(target_rgb)]])
        target_hsv = cv2.cvtColor(target_img, cv2.COLOR_RGB2HSV)[0][0]
        
        target_hue = target_hsv[0]
        
        lower = np.array([max(0, target_hue - hue_tol), sat_min, val_min])
        upper = np.array([min(179, target_hue + hue_tol), 255, 255])
        
        mask = cv2.inRange(img_hsv, lower, upper)
        
        if min_area > 0:
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            valid_mask = np.zeros_like(mask)
            for cnt in contours:
                if cv2.contourArea(cnt) >= min_area:
                    cv2.drawContours(valid_mask, [cnt], -1, 255, -1)
            mask = valid_mask

        coords = np.column_stack(np.where(mask > 0))
        if len(coords) > 0:
            avg_x = np.mean(coords[:, 1])
            return region[0] + int(avg_x)
        return None

    def count_vertical_sticks(self, region, img_rgb=None):
        """Counts the number of vertical 'sticks' (like I, II, III) in a region."""
        if img_rgb is None:
            img_rgb = self.capture_screen(region)
        
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
        projection = np.sum(thresh, axis=0)
        
        sticks = 0
        in_stick = False
        current_width = 0
        min_width = 2 
        
        for val in projection:
            if val > 0: 
                current_width += 1
                if not in_stick and current_width >= min_width:
                    sticks += 1
                    in_stick = True
            else:
                in_stick = False
                current_width = 0
        
        return sticks

    def _parse_target_color(self, target_color):
        if isinstance(target_color, str):
            target_color = target_color.lstrip('#')
            if len(target_color) == 6:
                return tuple(int(target_color[i:i+2], 16) for i in (0, 2, 4))
        return target_color