import time
import random
import numpy as np
import math
import keyboard
import threading
import cv2
import re
import customtkinter as ctk
from logic_base import BaseLogic
from utils import RobloxInputDriver

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
            "bronze": (219, 151, 139)
        }
        
        self.DEFAULT_CLOVER_TOLERANCES = {
            "gold": 33,
            "silver": 30,
            "bronze": 40
        }
        
        self.ocr_cache = {}

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

            self.perform_approach_movement()
            dialogue_fail_count = 0

            while self.running:
                if not self.initiate_dialogue():
                    dialogue_fail_count += 1
                    self.app.log("Failed to open dialogue, retrying without moving...")
                    if dialogue_fail_count >= 3:
                        self.app.log("3 consecutive dialogue failures, re-running approach movement.")
                        self.perform_approach_movement()
                        dialogue_fail_count = 0
                    time.sleep(1.0)
                    continue

                dialogue_fail_count = 0
                time.sleep(2)

                if not self.handle_dialogue_sequence(to_train[0]):
                    self.app.log("Dialogue sequence failed, retrying without moving...")
                    time.sleep(1.0)
                    continue

                time.sleep(2.5)
                self.perform_clover_scoring()

                self.app.log("Cycle Complete")
                self.handle_ok_popup()
                time.sleep(1.0)
                break

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
        
        start_time = time.time()
        move_menu_region = self.app.settings.get("regions").get("move_menu")
        
        while self.running:
            if not self.wait_for_roblox_focus():
                return False
                
            self.utils.send_key('space')
            time.sleep(0.184)
            self.utils.send_key('space')
            time.sleep(0.159)
            self.utils.send_key('e')
            time.sleep(0.08)
            self.utils.send_key('e')
            time.sleep(0.08)
            self.utils.send_key('e')
            time.sleep(0.08)
            self.utils.send_key('e')
            time.sleep(0.5)

            ocr_results = self.utils.get_text_from_region(move_menu_region)
            for bounding_box, text, confidence in ocr_results:
                text_lower = text.lower()
                if "research" in text_lower or "training" in text_lower:
                    self.app.log("Dialogue menu detected successfully via OCR!")
                    return True
            
            if time.time() - start_time > 20:
                self.app.log("Dialogue initiation timed out.")
                return False
                
            time.sleep(0.1)
        return False

    def _is_move_match(self, target_name, ocr_text, exact=False):
        """Match target_name against ocr_text.
        exact=True  → full string equality (used when a lock is set)
        exact=False → substring match (used for raw/partial names)
        """
        t = target_name.lower().strip()
        o = ocr_text.lower().strip()
        if exact:
            return t == o
        return t in o

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
        
        self.app.log("[2/3] Waiting 1.5s for menu to settle...")
        time.sleep(1.5)

        move_name = settings.get("move_names")[target_idx]
        if not move_name:
            self.app.log("No move name specified in configurations.")
            return False

        resolved_names = self.app.settings.settings.get("resolved_move_names", ["", "", ""])
        resolved_positions = self.app.settings.settings.get("resolved_move_positions", [None, None, None])
        resolved = resolved_names[target_idx]
        resolved_pos = resolved_positions[target_idx]

        if resolved and resolved_pos:
            self.app.log(f"[3/3] Waiting for '{move_name}' to appear, then clicking locked position {resolved_pos}...")
            lock_start = time.time()
            while time.time() - lock_start < 8.0:
                if not self.running:
                    return False
                results = self.utils.get_text_from_region(menu_region)
                for _, text, _ in results:
                    if self._is_move_match(move_name, text, exact=False):
                        self.app.log(f"-> Detected '{text}' — clicking saved position {resolved_pos}.")
                        self.human_click(resolved_pos[0], resolved_pos[1], duration=0.2)
                        return True
                time.sleep(0.2)
            self.app.log(f"-> ERROR: '{move_name}' never appeared in menu within timeout.")
            return False

        if resolved:
            search_name = resolved
            use_exact = True
        else:
            search_name = move_name
            use_exact = False

        self.app.log(f"[3/3] Searching menu layout for move: '{search_name}'" +
                     (" (exact)" if use_exact else " (partial)"))
        
        self.last_move_candidates = []
        move_clicked = False
        move_start_time = time.time()
        while time.time() - move_start_time < 8.0:
            if not self.running:
                return False
            
            results = self.utils.get_text_from_region(menu_region)
            for bbox, text, conf in results:
                cx = int(np.mean([p[0] for p in bbox]))
                cy = int(np.mean([p[1] for p in bbox]))
                if self._is_move_match(search_name, text, exact=use_exact):
                    is_dup = any(
                        abs(cx - c["x"]) < 30 and abs(cy - c["y"]) < 30
                        for c in self.last_move_candidates
                    )
                    if not is_dup:
                        self.last_move_candidates.append({
                            "text": text,
                            "x": cx,
                            "y": cy,
                            "bbox": bbox
                        })
            
            if self.last_move_candidates:
                if len(self.last_move_candidates) == 1:
                    cand = self.last_move_candidates[0]
                    absolute_x = menu_region[0] + cand["x"]
                    absolute_y = menu_region[1] + cand["y"]
                    self.human_click(absolute_x, absolute_y, duration=0.2)
                    self.app.log(f"-> Successfully selected move: {search_name} (Detected as '{cand['text']}')")
                    self._save_resolved_name(target_idx, cand["text"], abs_pos=[absolute_x, absolute_y])
                    move_clicked = True
                    break
                else:
                                                                                               
                    self.app.log(
                        f"-> ERROR: '{search_name}' matched {len(self.last_move_candidates)} items. "
                        f"Use the Test button in Settings to lock the exact move first."
                    )
                    return False
            time.sleep(0.2)
        
        if not move_clicked:
            self.app.log(f"-> ERROR: OCR failed to find '{move_name}' in menu area. Trying 'Nevermind'...")
            nevermind_clicked = False
            nevermind_results = self.utils.get_text_from_region(menu_region)
            for bbox, text, conf in nevermind_results:
                if "nevermind" in text.lower() or "never" in text.lower():
                    center_x = menu_region[0] + int(np.mean([p[0] for p in bbox]))
                    center_y = menu_region[1] + int(np.mean([p[1] for p in bbox]))
                    self.human_click(center_x, center_y, duration=0.15)
                    self.app.log(f"-> Clicked 'Nevermind' at ({center_x}, {center_y})")
                    nevermind_clicked = True
                    break
            
            if not nevermind_clicked:
                self.app.log("-> ERROR: 'Nevermind' option not found.")
            return False
        
        return True

    def test_detection(self):
        settings = self.app.settings.settings
        menu_region = settings["regions"].get("move_menu", [0, 0, 0, 0])
        
        if all(v == 0 for v in menu_region):
            self.app.log("Test: Move Selection Area (move_menu) region is not set!")
            return
            
        self.app.log("Testing Move Selection Area for 'clover' or 'training'...")
        
        results = self.utils.get_text_from_region(menu_region)
        combined_text = " ".join([res[1].lower() for res in results])
        
        if "clover" in combined_text or "training" in combined_text:
            matched_word = "clover" if "clover" in combined_text else "training"
            self.app.log(f"Test: SUCCESS! Detected '{matched_word}' in selection area.")
            
            for bbox, text, conf in results:
                if "clover" in text.lower() or "training" in text.lower():
                    center_x = menu_region[0] + int(np.mean([p[0] for p in bbox]))
                    center_y = menu_region[1] + int(np.mean([p[1] for p in bbox]))
                    self.smooth_move(center_x, center_y, duration=0.15)
                    break
        else:
            detected_raw = ", ".join([res[1] for res in results]) if results else "Nothing"
            self.app.log(f"Test: FAILED. Keywords not found. Saw: [{detected_raw}]")

    def _save_resolved_name(self, idx, text, abs_pos=None):
        """Persist the resolved move name and optional absolute screen position for slot idx."""
        resolved = list(self.app.settings.get("resolved_move_names", ["", "", ""]))
        resolved[idx] = text.strip()
        self.app.settings.set("resolved_move_names", resolved)

        positions = list(self.app.settings.get("resolved_move_positions", [None, None, None]))
        positions[idx] = abs_pos                  
        self.app.settings.set("resolved_move_positions", positions)

        if hasattr(self.app, "refresh_resolved_label"):
            self.app.root.after(0, lambda: self.app.refresh_resolved_label(idx))

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

        resolved_names = settings.get("resolved_move_names", ["", "", ""])
        resolved_positions = settings.get("resolved_move_positions", [None, None, None])
        current_resolved = resolved_names[idx]
        current_pos = resolved_positions[idx]

        if current_resolved and current_pos:
            self.app.log(
                f"Test: Already locked to '{current_resolved}' at {current_pos}. "
                f"Moving cursor to confirm."
            )
            time.sleep(0.5)
            self.utils.mouse_move(current_pos[0], current_pos[1])
            return

        if current_resolved:
            self.app.log(f"Testing OCR for: {move_name}  [locked to: '{current_resolved}']")
        else:
            self.app.log(f"Testing OCR for: {move_name}  (no lock set)")

        results = self.utils.get_text_from_region(menu_region)
        
        all_detected = []
        for bbox, text, conf in results:
            cx = int(np.mean([p[0] for p in bbox]))
            cy = int(np.mean([p[1] for p in bbox]))
            all_detected.append({"text": text, "x": cx, "y": cy, "bbox": bbox})
            self.app.log(f"Detected item: '{text}' at {cx}, {cy}")

        search_name = current_resolved if current_resolved else move_name
        use_exact = bool(current_resolved)
        matches = []
        for item in all_detected:
            if self._is_move_match(search_name, item["text"], exact=use_exact):
                matches.append(item)
                self.app.log(f"Test: MATCH -> '{item['text']}' at ({item['x']}, {item['y']})")

        if not matches:
            detected = ", ".join([res[1] for res in results])
            self.app.log(f"Test: FAILED. Saw: [{detected}]")
            return

        if len(matches) == 1:
            chosen = matches[0]
        else:
            self.app.log(f"Test: Found {len(matches)} matches — pick one to lock.")
            self.last_move_candidates = matches
            chosen = self.prompt_user_for_move()
            if not chosen:
                self.app.log("Test: No selection made, lock unchanged.")
                return

        abs_x = menu_region[0] + chosen["x"]
        abs_y = menu_region[1] + chosen["y"]
        self._save_resolved_name(idx, chosen["text"], abs_pos=[abs_x, abs_y])
        self.app.log(f"Test: Locked to '{chosen['text']}' at ({abs_x}, {abs_y}).")
        time.sleep(0.5)
        self.utils.mouse_move(abs_x, abs_y)

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
        
        white_found = self.utils.check_pixel_area(quest_region, (255, 255, 255), tolerance=25)
        if white_found:
            self.app.log("Test: SUCCESS! Quest/Guide region contains white text.")
        else:
            self.app.log("Test: Quest/Guide region does not contain white text.")

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
            screen_w, screen_h = self.get_screen_size()
            quest_region = [0, 0, screen_w, screen_h]
            self.app.log("Quest region not set, defaulting to full screen OCR.")

        self.app.log("Waiting for Quest/Guide white text to vanish...")
        
        start_wait = time.time()
        while self.running:
            if not self.wait_for_roblox_focus(): return
            white_found = self.utils.check_pixel_area(quest_region, (255, 255, 255), tolerance=30)
            if not white_found:
                self.app.log("Minigame started (Quest/Guide UI vanished).")
                break
            if time.time() - start_wait > 15:
                self.app.log("Timeout waiting for minigame start.")
                return
            time.sleep(0.1)

        def end_detector():
            while self.running and self.minigame_running:
                time.sleep(0.5)
                try:
                    white_found = self.utils.check_pixel_area(quest_region, (255, 255, 255), tolerance=30)
                    if white_found:
                        self.app.log("End detected via white Quest/Guide text.")
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
                
                current_time = time.time()
                self.click_history = [c for c in self.click_history if current_time - c['t'] < 0.5]
                raw_targets = []

                for clover_type, (lower, upper) in bgr_targets.items():
                    mask = cv2.inRange(current_frame_bgr, lower, upper)
                                                                                  
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
                    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    
                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area < 2:
                            continue
                        cx_local, cy_local, w, h_ = cv2.boundingRect(cnt)
                        tx = region[0] + cx_local + w // 2
                        ty = region[1] + cy_local + h_ // 2
                        
                        is_too_close = any(math.hypot(tx - p['x'], ty - p['y']) < 50 for p in self.click_history)
                        if is_too_close:
                            continue
                        raw_targets.append((clover_type, tx, ty, area))

                if raw_targets:
                    type_priority = {'gold': 0, 'silver': 1, 'bronze': 2}
                    raw_targets.sort(key=lambda item: (type_priority.get(item[0], 3), -item[3]))

                    targets = []
                    for clover_type, tx, ty, area in raw_targets:
                        duplicate = any(math.hypot(tx - px, ty - py) < 50 for _, px, py, _ in targets)
                        if duplicate:
                            continue
                        targets.append((clover_type, tx, ty, area))
                        if len(targets) >= 3:
                            break

                    with self.input_lock:
                        for clover_type, tx, ty, _ in targets:
                            RobloxInputDriver.click_at(tx, ty, duration=0.035)
                            RobloxInputDriver.click_at(tx - 5, ty, duration=0.035)
                            
                            self.click_history.append({'x': tx, 'y': ty, 't': time.time()})
                            session_stats[clover_type] += 1
                            session_stats["total_clicks"] += 1
                            self.app.log(f"-> Clicked {clover_type.capitalize()} Clover!")
                            time.sleep(0.02)

                time.sleep(0.001)

        except Exception as e:
            self.app.log(f"Minigame error: {e}")
        
    def prompt_user_for_move(self):
        """Show a customtkinter popup for the user to pick among multiple move candidates.
        Returns the selected candidate dict, or None if cancelled.
        """
        if not hasattr(self, "last_move_candidates") or not self.last_move_candidates:
            return None

        self.app.log("Multiple move candidates found – prompting user...")
        selected = [None]

        popup = ctk.CTkToplevel(self.app.root)
        popup.title("Select Move")
        popup.geometry("340x300")
        popup.grab_set()
        popup.focus_force()

        ctk.CTkLabel(
            popup,
            text="Multiple matches found.\nChoose the correct move:",
            font=("Arial", 13)
        ).pack(pady=(18, 8), padx=16)

        btn_frame = ctk.CTkScrollableFrame(popup, height=160)
        btn_frame.pack(fill="both", expand=True, padx=16, pady=4)

        def make_handler(cand):
            def handler():
                selected[0] = cand
                popup.destroy()
            return handler

        for cand in self.last_move_candidates:
            label = f"{cand['text']}  ({cand['x']}, {cand['y']})"
            ctk.CTkButton(btn_frame, text=label, command=make_handler(cand)).pack(
                fill="x", pady=3
            )

        ctk.CTkButton(popup, text="Cancel", fg_color="gray40", command=popup.destroy).pack(
            pady=(6, 14)
        )

        popup.wait_window()
        if selected[0] is None:
            self.app.log("User cancelled move selection.")
        else:
            self.app.log(f"User selected: '{selected[0]['text']}'")
        return selected[0]

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