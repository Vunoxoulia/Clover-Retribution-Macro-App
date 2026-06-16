import time
import random
import numpy as np
import math
import keyboard
import threading
import cv2
import re
from logic_base import BaseLogic, RobloxInputDriver

class LibraryLogic(BaseLogic):
    def __init__(self, app):
        super().__init__(app)
        
        self.current_move_idx = 0
        self.click_history = [] 
        
        self.SCORE_COLOR = (0, 0, 0)             
        self.GOLD_CLOVER_COLOR = (250, 171, 33)  
        
        self.DEFAULT_CLOVER_COLORS = {
            "gold": (251, 198, 108),
            "silver": (187, 197, 197),
            "bronze": (251, 197, 170)
        }
        
        self.DEFAULT_CLOVER_TOLERANCES = {
            "gold": 17,
            "silver": 17,
            "bronze": 30
        }

    def main_loop(self):
        while self.running:
            if not self.wait_for_roblox_focus():
                break

            settings = self.app.settings.settings
            move_names = settings.get("move_names", ["", "", ""])
            
            trained = self.check_trained_status()
            to_train = [i for i, name in enumerate(move_names) if name and not trained[i]]
            
            if not to_train:
                has_any_names = any(name for name in move_names)
                if has_any_names:
                    self.app.log("All moves trained! Stopping macro.")
                else:
                    self.app.log("No move names set in Settings. Stopping.")
                
                self.running = False
                self.app.root.after(1000, self.app.exit_app)
                break

            self.app.log(f"Talking to NPC... (Training Move {to_train[0] + 1})")
            self.current_move_idx = to_train[0] 

            if not self.initiate_dialogue():
                self.app.log("Failed to talk to NPC, retrying...")
                continue

            time.sleep(2)

            if not self.handle_dialogue_sequence(to_train[0]):
                self.app.log("Dialogue sequence failed, restarting...")
                continue

            time.sleep(2.5)
            self.perform_clover_scoring()

            self.app.log("Cycle Complete")
            self.handle_ok_popup() 
            time.sleep(1.0)

    def check_trained_status(self):
        settings = self.app.settings.settings
        move_names = settings.get("move_names", ["", "", ""])
        trained = [False, False, False]

        for i in range(3):
            if not move_names[i]:
                trained[i] = True 
                continue
                
            icon_region = settings["regions"].get(f"gold_clover_{i+1}", [0, 0, 0, 0])
            if all(v == 0 for v in icon_region):
                continue
            
            if self.utils.check_pixel_area(icon_region, self.GOLD_CLOVER_COLOR, tolerance=25):
                self.app.log(f"Move {i+1} ({move_names[i]}) is already trained (Gold Clover detected).")
                trained[i] = True
                
        return trained

    def perform_approach_movement(self):
        self.app.log("Approaching NPC area (Holding D)...")
        keyboard.press('d')
        start_hold = time.time()
        while self.running and (time.time() - start_hold < 2.0):
            if not self.check_focus():
                keyboard.release('d')
                self.wait_for_roblox_focus()
                keyboard.press('d')
            time.sleep(0.1)
        keyboard.release('d')
        self.app.log("Approaching NPC area (Holding S)...")
        keyboard.press('s')
        start_hold = time.time()
        while self.running and (time.time() - start_hold < 2.0):
            if not self.check_focus():
                keyboard.release('s')
                self.wait_for_roblox_focus()
                keyboard.press('s')
            time.sleep(0.1)
        keyboard.release('s')
        self.app.log("Approaching NPC area (Holding W)...")
        keyboard.press('w')
        start_hold = time.time()
        while self.running and (time.time() - start_hold < 3.0):
            if not self.check_focus():
                keyboard.release('w')
                self.wait_for_roblox_focus()
                keyboard.press('w')
            time.sleep(0.1)
        keyboard.release('w')

    def initiate_dialogue(self):
        self.app.log("Attempting to open dialogue...")
        time.sleep(0.5) 
        self.perform_approach_movement()
        
        start_time = time.time()
        move_menu_region = self.app.settings.get("regions").get("move_menu")
        
        while self.running:
            if not self.wait_for_roblox_focus():
                return False
                
            self.utils.send_key('space')
            time.sleep(0.05)
            self.utils.send_key('space')
            time.sleep(0.05)
            self.utils.send_key('e')
            time.sleep(0.1)
            self.utils.send_key('e')
            time.sleep(0.1)
            
            ocr_results = self.utils.get_text_from_region(move_menu_region)
            for bounding_box, text, confidence in ocr_results:
                text_lower = text.lower()
                if "research" in text_lower or "training" in text_lower:
                    self.app.log("Dialogue menu detected successfully via OCR!")
                    return True
            
            if time.time() - start_time > 20:
                self.app.log("Dialogue initiation timed out.")
                return False
                
        return False

    def _normalize_ocr_text(self, text):
        """Normalizes OCR text specifically for Roman numeral misreadings."""
        text = text.lower().strip()
        
        text = text.replace('1', 'i').replace('l', 'i').replace('|', 'i').replace('!', 'i').replace('j', 'i')
        return text

    def _is_move_match(self, target_name, ocr_text, all_detected=None, current_item=None):
        
        target_name = self._normalize_ocr_text(target_name)
        romans = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5}
        
        target_words = target_name.split()
        if not target_words:
            return False
            
        target_tier = romans.get(target_words[-1], 0)
        base_target = " ".join(target_words[:-1]) if target_tier > 0 else target_name
        base_words = base_target.split()

        
        pool_text = self._normalize_ocr_text(ocr_text)
        if all_detected and current_item:
            for other in all_detected:
                if other == current_item: continue
                
                if abs(current_item["y"] - other["y"]) < 25 and abs(current_item["x"] - other["x"]) < 50:
                    pool_text += " " + self._normalize_ocr_text(other["text"])

        
        if base_target and base_target not in pool_text:
            return False

        
        
        
        current_normalized = self._normalize_ocr_text(ocr_text)
        is_anchor = False
        if not base_words: 
            is_anchor = target_words[-1] in current_normalized
        else:
            
            is_anchor = base_words[-1] in current_normalized

        if not is_anchor:
            return False

        
        if target_tier == 0:
            return True 

        
        x_coords = [p[0] for p in current_item["bbox"]]
        y_coords = [p[1] for p in current_item["bbox"]]
        
        
        expansion = 85 if target_tier >= 4 else 65
        region = [int(min(x_coords)), int(min(y_coords)), int(max(x_coords) + expansion), int(max(y_coords))]
        
        actual_sticks = self.utils.count_vertical_sticks(region)
        
        
        target_roman_str = target_words[-1]
        ocr_has_exact_roman = re.search(r'\b' + re.escape(target_roman_str) + r'\b', pool_text)

        if target_tier <= 3 and actual_sticks == target_tier:
            return True
        elif ocr_has_exact_roman:
            
            return True
            
        return False

    def handle_dialogue_sequence(self, target_idx):
        settings = self.app.settings.settings
        menu_region = settings["regions"].get("move_menu", [0, 0, 0, 0])
        
        if all(v == 0 for v in menu_region):
            self.app.log("Automation Error: 'move_menu' region bounds are not calibrated.")
            return False

        self.app.log("[1/3] Waiting for Clover Training dialogue menu via OCR...")
        clover_menu_clicked = False
        dialogue_start_time = time.time()
        
        while time.time() - dialogue_start_time < 6.0:
            if not self.running:
                return False
                
            results = self.utils.get_text_from_region(menu_region)
            combined_text = " ".join([res[1].lower() for res in results])
            
            if "research" in combined_text or "training" in combined_text:
                for bbox, text, conf in results:
                    if "research" in text.lower() or "training" in text.lower():
                        click_x = menu_region[0] + int(np.mean([p[0] for p in bbox]))
                        click_y = menu_region[1] + int(np.mean([p[1] for p in bbox]))
                        
                        self.app.log(f"-> Found dialogue option! Clicking at ({click_x}, {click_y})")
                        self.human_click(click_x, click_y, duration=0.15)
                        clover_menu_clicked = True
                        break
            if clover_menu_clicked:
                break
            time.sleep(0.15)

        if not clover_menu_clicked:
            self.app.log("-> ERROR: Failed to detect 'research' or 'training' option in time.")
            return False
        
        time.sleep(0.3)

        self.app.log("[2/3] Waiting specifically for 'Skip' option...")
        skip_found = False
        skip_start_time = time.time()
        
        while time.time() - skip_start_time < 4.0:
            if not self.running:
                return False
                
            skip_results = self.utils.get_text_from_region(menu_region)
            for bbox, text, conf in skip_results:
                if "skip" in text.lower():
                    skip_x = int(np.mean([p[0] for p in bbox]))
                    skip_y = int(np.mean([p[1] for p in bbox]))
                    
                    absolute_click_x = menu_region[0] + skip_x
                    absolute_click_y = menu_region[1] + skip_y
                    
                    self.app.log(f"-> Found 'Skip'! Clicking at ({absolute_click_x}, {absolute_click_y})")
                    self.human_click(absolute_click_x, absolute_click_y, duration=0.15)
                    skip_found = True
                    break
                    
            if skip_found:
                break
            time.sleep(0.15) 
            
        if not skip_found:
            self.app.log("-> No 'Skip' button detected within timeout. Forcing transition check.")
        
        time.sleep(0.3)

        move_name = settings.get("move_names")[target_idx]
        if not move_name:
            self.app.log("No move name specified in configurations.")
            return False

        self.app.log(f"[3/3] Searching menu layout for move: '{move_name}'")
        
        move_clicked = False
        move_start_time = time.time()
        while time.time() - move_start_time < 4.0:
            if not self.running:
                return False
                
            results = self.utils.get_text_from_region(menu_region)
            all_detected = []
            for bbox, text, conf in results:
                cx = int(np.mean([p[0] for p in bbox]))
                cy = int(np.mean([p[1] for p in bbox]))
                all_detected.append({"text": text, "x": cx, "y": cy, "bbox": bbox})

            for item in all_detected:
                if self._is_move_match(move_name, item["text"], all_detected, item):
                    
                    x_coords = [p[0] for p in item["bbox"]]
                    y_coords = [p[1] for p in item["bbox"]]
                    
                    
                    center_local_x = int(np.mean(x_coords))
                    center_local_y = int(np.mean(y_coords))
                    
                    absolute_x = menu_region[0] + center_local_x
                    absolute_y = menu_region[1] + center_local_y
                    
                    self.human_click(absolute_x, absolute_y, duration=0.2)
                    self.app.log(f"-> Successfully selected move: {move_name} (Detected as '{item['text']}')")
                    move_clicked = True
                    break
            
            if move_clicked: break
            time.sleep(0.2)
                    
        if not move_clicked:
            self.app.log(f"-> ERROR: OCR failed to find '{move_name}' in menu area.")
            return False
            
        return True

    def test_detection(self):
        settings = self.app.settings.settings
        menu_region = settings["regions"].get("move_menu", [0, 0, 0, 0])
        
        if all(v == 0 for v in menu_region):
            self.app.log("Test: Move Selection Area (move_menu) region is not set!")
            return
            
        self.app.log("Testing Move Selection Area for 'research' or 'training'...")
        
        results = self.utils.get_text_from_region(menu_region)
        combined_text = " ".join([res[1].lower() for res in results])
        
        if "research" in combined_text or "training" in combined_text:
            matched_word = "research" if "research" in combined_text else "training"
            self.app.log(f"Test: SUCCESS! Detected '{matched_word}' in selection area.")
            
            for bbox, text, conf in results:
                if "research" in text.lower() or "training" in text.lower():
                    center_x = menu_region[0] + int(np.mean([p[0] for p in bbox]))
                    center_y = menu_region[1] + int(np.mean([p[1] for p in bbox]))
                    self.smooth_move(center_x, center_y, duration=0.15)
                    break
        else:
            detected_raw = ", ".join([res[1] for res in results]) if results else "Nothing"
            self.app.log(f"Test: FAILED. Keywords not found. Saw: [{detected_raw}]")

    def test_move_ocr(self, idx):
        settings = self.app.settings.settings
        move_name = settings.get("move_names")[idx]
        menu_region = settings["regions"].get("move_menu", [0, 0, 0, 0])
        
        if not move_name:
            self.app.log(f"Test: Move {idx+1} name is empty!")
            return
            
        if all(v == 0 for v in menu_region):
            self.app.log("Test: Move Selection Area not set!")
            return
            
        self.app.log(f"Testing OCR for: {move_name}")
        results = self.utils.get_text_from_region(menu_region)
        
        all_detected = []
        for bbox, text, conf in results:
            cx = int(np.mean([p[0] for p in bbox]))
            cy = int(np.mean([p[1] for p in bbox]))
            all_detected.append({"text": text, "x": cx, "y": cy, "bbox": bbox})
            self.app.log(f"Detected item: '{text}' at {cx}, {cy}")

        found = False
        for item in all_detected:
            if self._is_move_match(move_name, item["text"], all_detected, item):
                self.app.log(f"Test: SUCCESS! Found match: '{item['text']}'")
                abs_x = menu_region[0] + item["x"]
                abs_y = menu_region[1] + item["y"]
                self.utils.mouse_move(abs_x, abs_y)
                found = True
                break
        
        if not found:
            detected = ", ".join([res[1] for res in results])
            self.app.log(f"Test: FAILED. Saw: [{detected}]")

    def test_quest_ocr(self):
        settings = self.app.settings.settings
        quest_region = settings["regions"].get("quest_region", [0, 0, 0, 0])
        
        if all(v == 0 for v in quest_region):
            self.app.log("Test: Quest/Guide region is not set!")
            return
            
        self.app.log(f"Testing OCR in Quest/Guide region: {quest_region}")
        results = self.utils.get_text_from_region(quest_region)
        
        if not results:
            self.app.log("Test: No text detected in region.")
            return

        detected_words = [res[1] for res in results]
        combined = " ".join(detected_words).lower()
        
        self.app.log(f"Test: Detected text: [{', '.join(detected_words)}]")
        
        if "quest" in combined or "guide" in combined:
            found_word = "Quest" if "quest" in combined else "Guide"
            self.app.log(f"Test: SUCCESS! Found '{found_word}'")
        else:
            self.app.log("Test: Keywords 'Quest' or 'Guide' not found.")

    def test_color_detection(self):
        settings = self.app.settings.settings
        region = settings["regions"]["score"]
        clover_colors = settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        global_tolerance = settings.get("color_tolerance", 15)
        clover_tols = settings.get("clover_tolerances", {})
        
        if all(v == 0 for v in region):
            self.app.log("Test: Clover region not set!")
            return

        self.app.log(f"Testing color detection in region: {region}")
        img = self.utils.capture_screen(region)
        
        found_any = False
        for clover_type in ["gold", "silver", "bronze"]:
            color = clover_colors.get(clover_type, self.DEFAULT_CLOVER_COLORS[clover_type])
            tol = clover_tols.get(clover_type, self.DEFAULT_CLOVER_TOLERANCES.get(clover_type, global_tolerance))
            
            target_img = np.uint8([[list(color)]])
            hsv = cv2.cvtColor(target_img, cv2.COLOR_RGB2HSV)[0][0]
            h, s, v = hsv
            lower = [max(0, int(h)-tol), max(30, int(s)-60), max(30, int(v)-80)]
            upper = [min(179, int(h)+tol), 255, 255]
            self.app.log(f"[{clover_type.upper()}] Tol:{tol} | HSV Target:{hsv} | Range:{lower} to {upper}")

            targets = self.utils.pixel_search_region(region, color, tolerance=tol, img=img)
            if targets:
                first_target = targets[0]
                self.smooth_move(first_target[0], first_target[1], duration=0.15)
                self.app.log(f"Test: Found {len(targets)} {clover_type} clovers. Moving to first.")
                found_any = True
                break
        
        if not found_any:
            self.app.log("Test: No clover colors found.")

    def perform_clover_scoring(self):
        settings = self.app.settings.settings
        region = settings["regions"]["score"]  
        quest_region = settings["regions"].get("quest_region", [0, 0, 0, 0])
        clover_colors = settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        global_tolerance = settings.get("color_tolerance", 15)
        clover_tols = settings.get("clover_tolerances", {})

        session_stats = {"gold": 0, "silver": 0, "bronze": 0, "total_clicks": 0}
        self.minigame_running = True
        
        if all(v == 0 for v in quest_region):
            import win32api, win32con
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            quest_region = [0, 0, screen_w, screen_h]
            self.app.log("Quest region not set, defaulting to full screen OCR.")

        self.app.log("Waiting for 'Quest' or 'Guide' text to vanish...")
        
        start_wait = time.time()
        while self.running:
            if not self.wait_for_roblox_focus(): return
            ocr_text = self.utils.get_text_from_region(quest_region) 
            if not any(word in item[1].lower() for item in ocr_text for word in ["quest", "guide"]):
                self.app.log("Minigame started (Quest UI vanished).")
                break
            if time.time() - start_wait > 15:
                self.app.log("Timeout waiting for minigame start.")
                return
            time.sleep(0.1)

        def end_detector():
            while self.running and self.minigame_running:
                time.sleep(0.5)
                try:
                    current_text = self.utils.get_text_from_region(quest_region)
                    if any(word in item[1].lower() for item in current_text for word in ["quest", "guide"]):
                        self.app.log("End detected via OCR.")
                        self.minigame_running = False
                        break
                except: pass

        threading.Thread(target=end_detector, daemon=True).start()

        bgr_targets = {}
        for ctype in ["gold", "silver", "bronze"]:
            rgb = clover_colors.get(ctype, self.DEFAULT_CLOVER_COLORS[ctype])
            tol = clover_tols.get(ctype, self.DEFAULT_CLOVER_TOLERANCES.get(ctype, global_tolerance))
            r, g, b = rgb
            lower = np.array([max(0, b - tol), max(0, g - tol), max(0, r - tol)], dtype=np.uint8)
            upper = np.array([min(255, b + tol), min(255, g + tol), min(255, r + tol)], dtype=np.uint8)
            bgr_targets[ctype] = (lower, upper)

        minigame_start_time = time.time()
        
        try:
            while self.running and self.minigame_running:
                if not self.wait_for_roblox_focus(): break
                
                current_frame_bgr = self.utils.capture_screen_bgr(region)
                
                found_target = None
                found_type = None

                for clover_type, (lower, upper) in bgr_targets.items():
                    mask = cv2.inRange(current_frame_bgr, lower, upper)
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    if contours:
                        best_cnt = max(contours, key=cv2.contourArea)
                        if cv2.contourArea(best_cnt) >= 2:
                            cx_local, cy_local, w, h_ = cv2.boundingRect(best_cnt)
                            tx = region[0] + cx_local + w // 2
                            ty = region[1] + cy_local + h_ // 2
                            
                            current_time = time.time()
                            self.click_history = [c for c in self.click_history if current_time - c['t'] < 1.0]
                            is_too_close = any(math.hypot(tx - p['x'], ty - p['y']) < 70 for p in self.click_history)
                            
                            if not is_too_close:
                                found_target = (tx, ty)
                                found_type = clover_type
                                break

                if found_target:
                    tx, ty = found_target
                    RobloxInputDriver.click_at(tx, ty, duration=0.035)
                    RobloxInputDriver.click_at(tx + 5, ty, duration=0.035)
                    RobloxInputDriver.click_at(tx - 5, ty, duration=0.035)
                    
                    self.click_history.append({'x': tx, 'y': ty, 't': time.time()})
                    session_stats[found_type] += 1
                    session_stats["total_clicks"] += 1
                    self.app.log(f"-> Clicked {found_type.capitalize()} Clover!")
                
                time.sleep(0.001)

        except Exception as e:
            self.app.log(f"Minigame error: {e}")
        
        self.minigame_running = False
        duration = time.time() - minigame_start_time
        self.app.log(f"Summary: {duration:.1f}s | G:{session_stats['gold']} S:{session_stats['silver']} B:{session_stats['bronze']} | Total:{session_stats['total_clicks']}")
        
        new_gold = self.app.settings.get("total_gold", 0) + 250
        self.app.settings.set("total_gold", new_gold)
        
        move_stats = self.app.settings.get("move_stats", [0, 0, 0])
        if hasattr(self, 'current_move_idx'):
            move_stats[self.current_move_idx] += 250
            self.app.settings.set("move_stats", move_stats)

        self.app.update_gold_display()

    def test_active_movement(self):
        """Tests the 5-pixel toggle movement"""
        region = self.app.settings.get("regions")["score"]
        if all(v == 0 for v in region): return
        cx = region[0] + (region[2] - region[0]) // 2
        cy = region[1] + (region[3] - region[1]) // 2
        for _ in range(10):
            RobloxInputDriver.move_to(cx + 5, cy)
            time.sleep(0.1)
            RobloxInputDriver.move_to(cx - 5, cy)
            time.sleep(0.1)
