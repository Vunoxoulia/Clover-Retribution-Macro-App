import time
import random
import numpy as np
import math
import keyboard
import threading
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

            time.sleep(1)

            if not self.handle_dialogue_sequence(to_train[0]):
                self.app.log("Dialogue sequence failed, restarting...")
                continue

            time.sleep(2.5)
            self.perform_clover_scoring()

            self.app.log("Cycle Complete")
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
        while self.running and (time.time() - start_hold < 4.0):
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
        first_move_name = self.app.settings.get("move_names")[0].lower()
        
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
                if (first_move_name and first_move_name in text_lower) or "research" in text_lower or "training" in text_lower:
                    self.app.log("Dialogue menu detected successfully via OCR!")
                    return True
            
            if time.time() - start_time > 20:
                self.app.log("Dialogue initiation timed out.")
                return False
                
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
        
        time.sleep(1.0)

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
        
        time.sleep(1.0)

        move_name = settings.get("move_names")[target_idx]
        if not move_name:
            self.app.log("No move name specified in configurations.")
            return False

        self.app.log(f"[3/3] Searching menu layout for move: '{move_name}'")
        
        move_clicked = False
        move_start_time = time.time()
        while time.time() - move_start_time < 3.0:
            if not self.running:
                return False
                
            results = self.utils.get_text_from_region(menu_region)
            for bbox, text, conf in results:
                if move_name.lower() in text.lower():
                    center_x = int(np.mean([p[0] for p in bbox]))
                    center_y = int(np.mean([p[1] for p in bbox]))
                    
                    self.human_click(menu_region[0] + center_x, menu_region[1] + center_y, duration=0.2)
                    self.app.log(f"-> Successfully selected and clicked move: {move_name}")
                    move_clicked = True
                    break
            if move_clicked:
                break
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
        found = False
        for bbox, text, conf in results:
            if move_name.lower() in text.lower():
                self.app.log(f"Test: SUCCESS! Found '{text}' (Conf: {conf:.2f})")
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
        tolerance = settings.get("color_tolerance", 15)
        
        if all(v == 0 for v in region):
            self.app.log("Test: Clover region not set!")
            return

        found_any = False
        for clover_type in ["gold", "silver", "bronze"]:
            color = clover_colors.get(clover_type, self.DEFAULT_CLOVER_COLORS[clover_type])
            targets = self.utils.pixel_search_region(region, color, tolerance=tolerance)
            if targets:
                first_target = targets[0]
                self.smooth_move(first_target[0], first_target[1], duration=0.15)
                self.app.log(f"Test: Found {len(targets)} {clover_type} clovers. Moving to first.")
                found_any = True
                break
        
        if not found_any:
            self.app.log("Test: No clover colors found in clover region.")

    def perform_clover_scoring(self):
        settings = self.app.settings.settings
        region = settings["regions"]["score"]  
        quest_region = settings["regions"].get("quest_region", [0, 0, 0, 0])
        clover_colors = settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        tolerance = settings.get("color_tolerance", 15)

        session_stats = {"gold": 0, "silver": 0, "bronze": 0, "total_clicks": 0}
        minigame_start_time = 0

        if all(v == 0 for v in quest_region):
            import win32api, win32con
            screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            quest_region = [0, 0, screen_w, screen_h]
            self.app.log("Quest region not set, defaulting to full screen OCR.")
        else:
            self.app.log(f"Monitoring Quest/Guide text in calibrated region: {quest_region}")

        self.app.log("Waiting for 'Quest' or 'Guide' text to vanish...")
        
        start_time = time.time()
        while self.running:
            if not self.wait_for_roblox_focus(): return
            
            try:
                ocr_text = self.utils.get_text_from_region(quest_region) 
                if not any(word in item[1].lower() for item in ocr_text for word in ["quest", "guide"]):
                    self.app.log("Quest/Guide text vanished! Minigame started.")
                    minigame_start_time = time.time()
                    break
            except Exception as e:
                self.app.log(f"OCR Error during transition: {e}")
                
            if time.time() - start_time > 12:
                self.app.log("Timeout waiting for minigame initialization.")
                return
            time.sleep(0.1)

        x1, y1, x2, y2 = region
        self.jiggle_center_x = x1 + ((x2 - x1) // 2)
        self.jiggle_center_y = y1 + ((y2 - y1) // 2)
        
        self.scoring_sweep_active = True
        self.clover_lock_active = False  
        
        jiggle_thread = threading.Thread(
            target=self.execute_smooth_horizontal_jiggle,
            kwargs={"span": 35, "speed_delay": 0.01, "region": region},
            daemon=True
        )
        jiggle_thread.start()

        last_ocr_check = time.time()
        
        try:
            while self.running:
                if not self.wait_for_roblox_focus(): break
                    
                if time.time() - last_ocr_check > 0.3:
                    last_ocr_check = time.time()
                    current_text = self.utils.get_text_from_region(quest_region)
                    if any(word in item[1].lower() for item in current_text for word in ["quest", "guide"]):
                        duration = time.time() - minigame_start_time
                        self.app.log(f"Detected 'Quest' or 'Guide' reappearing! Ending minigame.")
                        
                        new_xp = self.app.settings.get("total_xp", 0) + 250
                        self.app.settings.set("total_xp", new_xp)
                        
                        move_stats = self.app.settings.get("move_stats", [0, 0, 0])
                        if hasattr(self, 'current_move_idx'):
                            move_stats[self.current_move_idx] += 250
                            self.app.settings.set("move_stats", move_stats)

                        self.app.update_xp_display()
                        self.app.log(f"Session Summary: {duration:.1f}s | G:{session_stats['gold']} S:{session_stats['silver']} B:{session_stats['bronze']} | Total:{session_stats['total_clicks']}")
                        break

                current_cycle_frame = self.utils.capture_screen(region)
                found_targets = [] 

                for clover_type in ["gold", "silver", "bronze"]:
                    color = clover_colors.get(clover_type, self.DEFAULT_CLOVER_COLORS[clover_type])
                    targets = self.utils.pixel_search_region(region, color, tolerance=tolerance, img=current_cycle_frame)
                    
                    if targets:
                        for t in targets:
                            found_targets.append((t, clover_type))

                if found_targets:
                    current_time = time.time()
                    self.click_history = [c for c in self.click_history if current_time - c['t'] < 1.2]
                    
                    for target, clover_type in found_targets:
                        if not self.running: break
                        
                        is_too_close = False
                        for prev_click in self.click_history:
                            dist = math.hypot(target[0] - prev_click['x'], target[1] - prev_click['y'])
                            if dist < 80:
                                is_too_close = True
                                break
                        
                        if is_too_close:
                            continue

                        self.clover_lock_active = True 
                        time.sleep(0.005) 
                        RobloxInputDriver.click_at(target[0], target[1], duration=0.03)
                        self.click_history.append({'x': target[0], 'y': target[1], 't': time.time()})
                        session_stats[clover_type] += 1
                        session_stats["total_clicks"] += 1
                        self.jiggle_center_x, self.jiggle_center_y = target[0], target[1]
                        self.clover_lock_active = False 
                        time.sleep(0.01)
                
                time.sleep(0.002)
        except Exception as e:
            self.app.log(f"CRITICAL ERROR in minigame loop: {e}")
        
        self.scoring_sweep_active = False
        self.app.log("Minigame Completed. Returning to movement state.")

    def execute_smooth_horizontal_jiggle(self, span, speed_delay, region):
        x1, y1, x2, y2 = region
        direction = 1 
        offset = 0
        last_periodic_click = time.time()
        
        while self.running and self.scoring_sweep_active:
            if self.clover_lock_active:
                time.sleep(0.01)
                continue

            if time.time() - last_periodic_click > 0.2:
                RobloxInputDriver.click_at(int(self.jiggle_center_x + offset), int(self.jiggle_center_y), duration=0.01)
                last_periodic_click = time.time()

            if direction == 1:
                offset += 0.5
                if offset >= span:
                    direction = -1
            else:
                offset -= 0.5
                if offset <= -span:
                    direction = 1
            
            pixel_x = int(self.jiggle_center_x + offset)
            pixel_y = int(self.jiggle_center_y)
            pixel_x = max(x1, min(pixel_x, x2))
            pixel_y = max(y1, min(pixel_y, y2))
            
            RobloxInputDriver.move_to(pixel_x, pixel_y)
            time.sleep(speed_delay)
