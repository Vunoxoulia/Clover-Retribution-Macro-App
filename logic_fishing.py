import time
import keyboard
import cv2
import numpy as np
from logic_base import BaseLogic

class FishingLogic(BaseLogic):
    def __init__(self, app):
        super().__init__(app)
        self.is_holding_space = False

    def test_detection(self):
        """The 'Test Full Tracking' button logic."""
        self.app.log("Manual Test: Waiting for Minigame Bar...")
        bar_region = self.app.settings.get("regions", {}).get("minigame_bar")
        bar_color = self.app.settings.get("bar_color", [95, 153, 98])
        fish_color = self.app.settings.get("fish_color", [188, 187, 144])
        tolerance = self.app.settings.get("color_tolerance", 25)
        
        if not bar_region or all(v == 0 for v in bar_region):
            self.app.log("Error: Minigame Bar region not set!")
            return

        
        minigame_active = False
        start_wait = time.time()
        while time.time() - start_wait < 60: 
            
            if self.utils.find_color_hsv_x(bar_region, bar_color, hue_tol=15, min_area=300):
                minigame_active = True
                break
            time.sleep(0.2)
        
        if not minigame_active:
            self.app.log("Test timed out waiting for bar.")
            return

        
        self.app.log("Test: Minigame Detected! Tracking...")
        last_seen_bar = time.time()
        
        while True:
            
            bar_x, fish_x = self._get_positions(bar_region, bar_color, fish_color, tolerance)
            
            if bar_x:
                last_seen_bar = time.time()
                if fish_x:
                    if bar_x < fish_x:
                        if not self.is_holding_space:
                            keyboard.press('space')
                            self.is_holding_space = True
                    else:
                        if self.is_holding_space:
                            keyboard.release('space')
                            self.is_holding_space = False
            else:
                
                if time.time() - last_seen_bar > 0.5:
                    break
            
            time.sleep(0.005)

        if self.is_holding_space:
            keyboard.release('space')
            self.is_holding_space = False
        self.app.log("Test Complete: Bar no longer detected.")

    def test_bar_detection(self):
        self.app.log("Testing Bar Detection (HSV/LARGE)...")
        bar_region = self.app.settings.get("regions", {}).get("minigame_bar")
        bar_color = self.app.settings.get("bar_color", [95, 153, 98])
        
        if not bar_region or all(v == 0 for v in bar_region):
            self.app.log("Error: Minigame Bar region not set!")
            return

        bar_x = self.utils.find_color_hsv_x(bar_region, bar_color, hue_tol=15, min_area=300)
        if bar_x:
            center_y = bar_region[1] + (bar_region[3] - bar_region[1]) // 2
            self.utils.mouse_move(bar_x, center_y)
            self.app.log(f"Bar found (HSV)! X: {bar_x}")
        else:
            self.app.log("Bar NOT found. Try re-picking the color.")

    def test_fish_detection(self):
        self.app.log("Testing Fish Detection (Hybrid)...")
        bar_region = self.app.settings.get("regions", {}).get("minigame_bar")
        fish_color = self.app.settings.get("fish_color", [188, 187, 144])
        tolerance = self.app.settings.get("color_tolerance", 25)
        
        if not bar_region or all(v == 0 for v in bar_region):
            self.app.log("Error: Minigame Bar region not set!")
            return

        _, fish_x = self._get_positions(bar_region, [0,0,0], fish_color, tolerance) 

        if fish_x:
            center_y = bar_region[1] + (bar_region[3] - bar_region[1]) // 2
            self.utils.mouse_move(fish_x, center_y)
            self.app.log(f"Fish found! X: {fish_x}")
        else:
            self.app.log("Fish NOT found. Check area/color.")

    def _get_positions(self, region, bar_color, fish_color, tolerance):
        """Unified method to find Bar and Fish positions."""
        img_rgb = self.utils.capture_screen(region)
        img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
        
        bar_x, fish_x = None, None
        
        
        b_target_img = np.uint8([[list(bar_color)]])
        b_target_hsv = cv2.cvtColor(b_target_img, cv2.COLOR_RGB2HSV)[0][0]
        b_lower = np.array([max(0, b_target_hsv[0] - 15), 40, 40])
        b_upper = np.array([min(179, b_target_hsv[0] + 15), 255, 255])
        b_mask = cv2.inRange(img_hsv, b_lower, b_upper)
        
        b_contours, _ = cv2.findContours(b_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in b_contours:
            if cv2.contourArea(cnt) > 350:
                cx, _, w, _ = cv2.boundingRect(cnt)
                bar_x = region[0] + cx + w // 2
                break

        
        f_target_img = np.uint8([[list(fish_color)]])
        f_target_hsv = cv2.cvtColor(f_target_img, cv2.COLOR_RGB2HSV)[0][0]
        f_lower = np.array([max(0, f_target_hsv[0] - 15), 30, 30])
        f_upper = np.array([min(179, f_target_hsv[0] + 15), 255, 255])
        f_mask = cv2.inRange(img_hsv, f_lower, f_upper)
        
        f_contours, _ = cv2.findContours(f_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in f_contours:
            area = cv2.contourArea(cnt)
            if 10 < area < 250:
                cx, _, w, _ = cv2.boundingRect(cnt)
                fish_x = region[0] + cx + w // 2
                break
        
        if not fish_x:
            rgb_pos = self.utils.pixel_search_existing_frame(img_rgb, region, fish_color, tolerance)
            if rgb_pos: fish_x = rgb_pos[0]
            
        return bar_x, fish_x

    def main_loop(self):
        self.app.log("Fishing Macro Started")
        bar_color = self.app.settings.get("bar_color", [95, 153, 98])
        fish_color = self.app.settings.get("fish_color", [188, 187, 144])
        tolerance = self.app.settings.get("color_tolerance", 25)
        
        if not self.wait_for_roblox_focus():
            return

        
        self.app.log("Initial Setup: Pressing Comma (1/2)")
        self.utils.send_key(',')
        time.sleep(1.5)

        if not self.running: return

        self.app.log("Initial Setup: Pressing Comma (2/2)")
        self.utils.send_key(',')
        time.sleep(1.5)
        
        while self.running:
            if not self.wait_for_roblox_focus():
                break
            
            
            click_pos = self.app.settings.get("regions", {}).get("fishing_click_pos")
            if not click_pos or all(v == 0 for v in click_pos):
                self.app.log("Error: Fishing Click Position not set!")
                self.running = False
                break
            
            self.app.log(f"Moving to {click_pos}...")
            self.smooth_move(click_pos[0], click_pos[1], duration=0.25)
            time.sleep(0.5)
            self.app.log("Clicking to start fishing...")
            self.utils.mouse_click(click_pos[0], click_pos[1])
            time.sleep(1.0)
            
            
            self.app.log("Waiting for minigame...")
            bar_region = self.app.settings.get("regions", {}).get("minigame_bar")
            if not bar_region or all(v == 0 for v in bar_region):
                self.app.log("Error: Minigame Bar region not set!")
                self.running = False
                break
                
            minigame_active = False
            start_wait = time.time()
            while self.running and (time.time() - start_wait < 30): 
                
                bx, _ = self._get_positions(bar_region, bar_color, fish_color, tolerance)
                if bx:
                    minigame_active = True
                    break
                time.sleep(0.2)
            
            if not minigame_active:
                self.app.log("Minigame didn't start. Retrying click...")
                continue
                
            
            self.app.log("Minigame ACTIVE! Tracking...")
            last_seen_bar = time.time()
            self.is_holding_space = False
            
            while self.running:
                bar_x, fish_x = self._get_positions(bar_region, bar_color, fish_color, tolerance)
                
                if bar_x:
                    last_seen_bar = time.time()
                    if fish_x:
                        if bar_x < fish_x:
                            if not self.is_holding_space:
                                keyboard.press('space')
                                self.is_holding_space = True
                        else:
                            if self.is_holding_space:
                                keyboard.release('space')
                                self.is_holding_space = False
                else:
                    if time.time() - last_seen_bar > 0.5:
                        break
                
                time.sleep(0.005)
            
            if self.is_holding_space:
                keyboard.release('space')
                self.is_holding_space = False
            
            self.app.log("Caught! Waiting 2 seconds before next cast...")
            self.handle_ok_popup()
            time.sleep(2.0) 
            
            if not self.running:
                break
        
        self.app.log("Fishing Macro Stopped")

    def stop(self):
        super().stop()
        if self.is_holding_space:
            keyboard.release('space')
            self.is_holding_space = False
