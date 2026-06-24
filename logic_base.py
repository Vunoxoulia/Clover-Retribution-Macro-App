import threading
import time
import random  
import numpy as np
import math
import keyboard
import pywinctl
from pynput.mouse import Button, Controller as MouseController
from screeninfo import get_monitors
from utils import SpatialUtils, RobloxInputDriver

class BaseLogic:
    def __init__(self, app):
        self.app = app
        self.utils = SpatialUtils()
        self.running = False
        self.paused = False
        self.thread = None
        self.ok_scanner_thread = None
        self.ok_scanner_running = False
        self._ok_scanner_lock = threading.Lock()
        self._mouse = MouseController()
        self.input_lock = RobloxInputDriver._lock
        self.test_running = False

    def _sleep(self, seconds, granularity=0.05):
        end = time.time() + seconds
        while time.time() < end:
            if not self.test_running:
                return False
            time.sleep(min(granularity, end - time.time()))
        return True

    def start(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.ok_scanner_running = True
            self.ok_scanner_thread = threading.Thread(target=self._ok_scanner_loop, daemon=True)
            self.ok_scanner_thread.start()
            self.thread = threading.Thread(target=self.main_loop, daemon=True)
            self.thread.start()
            self.app.log("Macro thread started")

    def stop(self):
        self.test_running = False
        if not self.running:
            return
        self.running = False
        self.ok_scanner_running = False
        self.app.log("Stopping macro...")
        if self.ok_scanner_thread:
            self.ok_scanner_thread.join(timeout=1.0)
        if self.thread:
            self.thread.join(timeout=1.0)
        self.app.log("Macro stopped")

    def _ok_scanner_loop(self):
        while self.running and self.ok_scanner_running:
            if self._ok_scanner_lock.acquire(blocking=False):
                try:
                    self.handle_ok_popup()
                finally:
                    self._ok_scanner_lock.release()
            else:
                self.app.log("OK scanner busy; skipping this scan cycle.")

            for _ in range(40):
                if not self.running or not self.ok_scanner_running:
                    return
                time.sleep(0.25)

    def wait_for_roblox_focus(self):
        if self.check_focus():
            return True
            
        self.app.log("Waiting for Roblox... (Focus the game!)")
        while self.running:
            if self.check_focus():
                self.app.log("Roblox focus detected!")
                return True
            time.sleep(0.5)
        return False

    def check_focus(self):
        try:
            active_window = pywinctl.getActiveWindow()
            if active_window:
                title = active_window.title
                return "Roblox" in title
        except Exception:
            pass
        return False

    def get_cursor_pos(self):
        return self._mouse.position

    def smooth_move(self, target_x, target_y, duration=0.15):
        with self.input_lock:
            try:
                start_x, start_y = self.get_cursor_pos()
            except Exception:
                return  
                
            dx = target_x - start_x
            dy = target_y - start_y
            distance = np.hypot(dx, dy)
            
            if distance == 0:
                return
            
            steps = max(6, int(distance / random.randint(15, 30)))
            sleep_per_step = duration / steps

            for i in range(1, steps + 1):
                if not self.running:
                    break
                t = i / steps
                t = t * (2 - t)  
                
                current_x = int(start_x + dx * t)
                current_y = int(start_y + dy * t)
                
                RobloxInputDriver.move_to(current_x, current_y)
                time.sleep(sleep_per_step)
                
            RobloxInputDriver.move_to(target_x, target_y)
            time.sleep(0.015)

    def human_click(self, x, y, duration=0.15):
        with self.input_lock:
            self.smooth_move(x, y, duration=duration)
            RobloxInputDriver.click_at(x, y, duration=random.uniform(0.02, 0.04))

    def get_screen_size(self):
        """Returns the screen width and height using screeninfo."""
        try:
            for m in get_monitors():
                if m.is_primary:
                    return m.width, m.height
        except Exception:
            pass
        return 1920, 1080           

    def handle_ok_popup(self):
        """Scans the screen for an 'Ok' button and clicks it if found."""
        try:
            screen_w, screen_h = self.get_screen_size()
                                                                                  
            left = int(screen_w * 0.3)
            top = int(screen_h * 0.3)
            right = int(screen_w * 0.7)
            bottom = int(screen_h * 0.7)
            center_region = [left, top, right, bottom]
            
            results = self.utils.get_text_from_region(center_region, upscale=1)
            for bbox, text, conf in results:
                if text.strip() == "Ok":
                    cx = center_region[0] + int(np.mean([p[0] for p in bbox]))
                    cy = center_region[1] + int(np.mean([p[1] for p in bbox]))
                    self.app.log(f"Detected 'Ok' popup at ({cx}, {cy}). Clicking...")
                    
                    with self.input_lock:
                        old_x, old_y = self.get_cursor_pos()
                        self.human_click(cx, cy, duration=0.08)
                        time.sleep(0.1)
                        RobloxInputDriver.move_to(old_x, old_y)
                    return True
        except Exception as e:
            self.app.log(f"Error checking for 'Ok' popup: {e}")
        return False

    def main_loop(self):
        """To be overridden by subclasses"""
        pass