import ctypes
import os
import threading
import cv2
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
        self.on_ok_clicked = None
        # Set while an OK popup is being clicked: a route walk pauses (keys up, clock stopped) until it's done.
        self.ok_busy = threading.Event()
        self.walking = False          # a route is being walked: look for OK every second instead of every 10
        # Global always-on OK scanner (runs even when macro is stopped/paused)
        self._global_ok_active = False
        self._global_ok_thread = None

    def _sleep(self, seconds, granularity=0.05):
        end = time.time() + seconds
        while time.time() < end:
            if not self.test_running:
                return False
            time.sleep(min(granularity, end - time.time()))
        return True

    def warn_if_roblox_admin(self):
        """Tell the user (log + pop-up) when Roblox runs as administrator: no key would reach it."""
        from utils import roblox_admin_problem
        msg = roblox_admin_problem()
        if not msg:
            return False
        self.app.log("" + msg.split("\n")[0])
        try:
            from tkinter import messagebox
            self.app.root.after(0, lambda: messagebox.showwarning("Roblox runs as administrator", msg,
                                                                  parent=self.app.root))
        except Exception:
            pass
        return True

    def start(self):
        if not self.running:
            threading.Thread(target=self.warn_if_roblox_admin, daemon=True).start()
            try:
                self.remember_roblox()
            except Exception:
                self._roblox_hwnd = 0
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

    def start_global_ok_scanner(self):
        """Start the always-on OK clicker that runs regardless of macro state."""
        if self._global_ok_active:
            return
        self._global_ok_active = True
        self._global_ok_thread = threading.Thread(target=self._global_ok_loop, daemon=True)
        self._global_ok_thread.start()
        self.app.log("Always-Click-OK: Enabled")

    def stop_global_ok_scanner(self):
        """Stop the always-on OK clicker."""
        self._global_ok_active = False
        self.app.log("Always-Click-OK: Disabled")

    def _global_ok_loop(self):
        """Continuously scan and click OK popups, independent of macro state."""
        while self._global_ok_active:
            if self._ok_scanner_lock.acquire(blocking=False):
                try:
                    self.handle_ok_popup()
                except Exception as e:
                    self.app.log(f"Always-OK error: {e}")
                finally:
                    self._ok_scanner_lock.release()
            # Poll every ~10 seconds
            for _ in range(40):
                if not self._global_ok_active:
                    return
                time.sleep(0.25)

    def _ok_scanner_loop(self):
        while self.running and self.ok_scanner_running:
            if self._ok_scanner_lock.acquire(blocking=False):
                try:
                    self.handle_ok_popup()
                finally:
                    self._ok_scanner_lock.release()
            else:
                self.app.log("OK scanner busy; skipping this scan cycle.")

            for i in range(40):
                if not self.running or not self.ok_scanner_running:
                    return
                if self.walking and i >= 4:            # mid-route: a popup freezes you, so catch it fast
                    break
                time.sleep(0.25)

    def remember_roblox(self):
        """The Roblox window this macro plays in: the one in front now (else the first one open)."""
        from utils import foreground_roblox, roblox_windows
        self._roblox_hwnd = foreground_roblox() or next((h for h, _ in roblox_windows()), 0)

    def force_focus_on(self):
        return bool(self.app.settings.get("force_roblox_focus", True))

    def wait_for_roblox_focus(self):
        if self.check_focus():
            return True
        if self.running and self.force_focus_on():
            # Keep Roblox in focus: bring the macro's Roblox window back to the front instead of waiting
            from utils import focus_roblox
            if not getattr(self, "_roblox_hwnd", 0):
                self.remember_roblox()
            if focus_roblox(getattr(self, "_roblox_hwnd", 0)) and self.check_focus():
                self.app.log("Brought Roblox back to the front.")
                return True
        self.app.log("Waiting for Roblox... (Focus the game!)")
        last_try = time.time()
        while self.running:
            if self.check_focus():
                self.app.log("Roblox focus detected!")
                return True
            if self.force_focus_on() and time.time() - last_try > 2.0:
                from utils import focus_roblox
                last_try = time.time()
                if focus_roblox(getattr(self, "_roblox_hwnd", 0)) and self.check_focus():
                    return True
            time.sleep(0.5)
        return False

    def check_focus(self):
        try:
            active_window = pywinctl.getActiveWindow()
            if active_window:
                from utils import is_roblox_title
                return is_roblox_title(active_window.title)
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

            was_running = self.running
            for i in range(1, steps + 1):
                if was_running and not self.running:
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

    def _find_button_cluster(self, hits, min_cluster=30, proximity=20):
        if not hits:
            return None
        clusters = []
        for x, y in hits:
            placed = False
            for cluster in clusters:
                cx, cy = cluster["cx"], cluster["cy"]
                if abs(x - cx) <= proximity and abs(y - cy) <= proximity:
                    cluster["points"].append((x, y))
                    cluster["cx"] = int(np.mean([p[0] for p in cluster["points"]]))
                    cluster["cy"] = int(np.mean([p[1] for p in cluster["points"]]))
                    placed = True
                    break
            if not placed:
                clusters.append({"points": [(x, y)], "cx": x, "cy": y})
        best = max(clusters, key=lambda c: len(c["points"]))
        if len(best["points"]) >= min_cluster:
            return (best["cx"], best["cy"])
        return None

    def get_roblox_window_region(self):
        try:
            import pywinctl
            from utils import is_roblox_title
            # the GAME window only (title exactly 'Roblox') - not Roblox Account Manager / a browser tab
            windows = [w for w in pywinctl.getAllWindows() if is_roblox_title(w.title)]
            if windows:
                active = pywinctl.getActiveWindow()
                w = active if active and is_roblox_title(active.title) else windows[0]
                return [w.left, w.top, w.left + w.width, w.top + w.height]
        except Exception:
            pass
        screen_w, screen_h = self.get_screen_size()
        return [0, 0, screen_w, screen_h]

    OK_TEMPLATE_FILE = "ok_template.png"
    OK_SEARCH_PAD = 60        # px of slack around the saved area (popup may shift slightly)
    OK_MATCH_THRESHOLD = 0.80

    def _ok_template_path(self):
        from settings import get_base_path
        return os.path.join(get_base_path(), self.OK_TEMPLATE_FILE)

    def capture_ok_template(self, region):
        """Screenshot the selected OK button area and save it as the match template."""
        try:
            if region[2] - region[0] < 5 or region[3] - region[1] < 5:
                return False
            img = self.utils.capture_screen_bgr(region)
            cv2.imwrite(self._ok_template_path(), img)
            self._ok_template = None  # force reload
            return True
        except Exception as e:
            self.app.log(f"Error saving OK template: {e}")
            return False

    def _load_ok_template(self):
        tpl = getattr(self, "_ok_template", None)
        if tpl is None:
            path = self._ok_template_path()
            if os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    tpl = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self._ok_template = tpl
        return tpl

    def get_ok_search_region(self):
        """Area the OK detector scans. Uses the user-set 'ok_scan_area' if present, otherwise the whole
        screen (every monitor) once the OK button is captured. None = not set up."""
        regions = self.app.settings.get("regions", {})
        scan = regions.get("ok_scan_area", [0, 0, 0, 0])
        if scan and any(v != 0 for v in scan):
            return list(scan)
        if self._ok_button_box():
            m = self.utils.sct.monitors[0]
            return [m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"]]
        return None

    def _ok_button_box(self, pad=0):
        btn = self.app.settings.get("regions", {}).get("ok_button", [0, 0, 0, 0])
        if not (btn and any(v != 0 for v in btn)):
            return None
        return [max(0, btn[0] - pad), max(0, btn[1] - pad), btn[2] + pad, btn[3] + pad]

    def find_ok_button(self):
        """Look for the OK button only inside the OK scan area. Returns (x, y, score) or None.
        Uses grayscale template matching on a small crop — much cheaper than OCR on the whole window."""
        search = self.get_ok_search_region()
        if not search:
            if not getattr(self, "_ok_region_warned", False):
                self.app.log("OK detection not set up — capture the OK button on the OK Popup page.")
                self._ok_region_warned = True
            return None
        sx, sy = search[0], search[1]
        frame = cv2.cvtColor(self.utils.capture_screen_bgr(search), cv2.COLOR_BGR2GRAY)

        tpl = self._load_ok_template()
        if tpl is not None and tpl.shape[0] <= frame.shape[0] and tpl.shape[1] <= frame.shape[1]:
            res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= float(self.app.settings.get("ok_match_threshold", self.OK_MATCH_THRESHOLD)):
                th, tw = tpl.shape[:2]
                return (sx + max_loc[0] + tw // 2, sy + max_loc[1] + th // 2, max_val)
            return None

        # No template image: fall back to OCR, but only near the captured button (reading the whole screen is heavy)
        if not any(self.app.settings.get("regions", {}).get("ok_scan_area") or [0]):
            search = self._ok_button_box(self.OK_SEARCH_PAD) or search
            sx, sy = search[0], search[1]
        for bbox, text, conf in self.utils.get_text_from_region(search, upscale=2):
            if text.strip().lower() == "ok":
                return (sx + int(np.mean([p[0] for p in bbox])),
                        sy + int(np.mean([p[1] for p in bbox])), conf)
        return None

    def resolve_ok_click(self, hit):
        """Swap the detected position for the user's fixed click spot, if one is set."""
        pos = self.app.settings.get("regions", {}).get("ok_click_pos", [0, 0])
        if pos and len(pos) == 2 and any(v != 0 for v in pos):
            return (pos[0], pos[1], hit[2])
        return hit

    def test_ok_popup(self):
        self.app.log("Testing OK popup detection...")
        hit = self.find_ok_button()
        if not hit:
            self.app.log("Test: 'Ok' not found in the OK scan area.")
            return
        cx, cy, score = self.resolve_ok_click(hit)
        self.app.log(f"Test: Found 'Ok' [match {score:.2f}]. Moving and clicking at ({cx}, {cy}).")
        self.utils.mouse_move(cx, cy)
        time.sleep(0.5)
        RobloxInputDriver.click_at(cx, cy, duration=0.035)

    def handle_ok_popup(self):
        try:
            hit = self.find_ok_button()
            if hit:
                cx, cy, score = self.resolve_ok_click(hit)
                self.app.log(f"Found 'Ok' [match {score:.2f}]. Clicking at ({cx}, {cy})...")
                self.ok_busy.set()                     # a route walk pauses until this is done
                try:
                    if self._click_ok(cx, cy) is False:
                        return False
                finally:
                    self.ok_busy.clear()
                if self.on_ok_clicked:
                    threading.Thread(target=self.on_ok_clicked, daemon=True).start()
                return True
        except Exception as e:
            self.app.log(f"Error checking for Ok popup: {e}")
        return False

    def _click_ok(self, cx, cy):
        # Hold the shared input lock for the whole thing (a running rotation waits), and remember
        # which window had focus: clicking OK in ANOTHER Roblox window makes Windows switch to it,
        # so afterwards we switch back or the macro keeps pressing keys in the wrong window.
        from utils import roblox_window_at
        from logic_events import EventWatcher
        target = roblox_window_at(cx, cy)
        if target == 0:
            # something else covers that spot (e.g. this macro's own window): clicking would hit IT -
            # that's how an OK click could press a button of the macro. Skip; it's tried again later.
            self.app.log("OK popup is covered by another window - not clicking (move the macro window away).")
            return False
        with RobloxInputDriver._lock:
            prev = ctypes.windll.user32.GetForegroundWindow()
            old_x, old_y = self.get_cursor_pos()
            if target > 0 and prev != target:
                EventWatcher.focus_window(target, timeout=1.0)   # bring it to the front first: then ONE click is enough
                time.sleep(0.15)
            self.human_click(cx, cy, duration=0.15)
            RobloxInputDriver.move_to(old_x, old_y)
            # back to the Roblox window that was in front (multi-window) - never to a non-Roblox window
            # like the macro itself, or the game would lose focus and the macro would wait
            from utils import roblox_windows
            if prev and prev != ctypes.windll.user32.GetForegroundWindow() and prev in [h for h, _ in roblox_windows()]:
                time.sleep(0.2)
                EventWatcher.focus_window(prev, timeout=1.0)
        return True

    def main_loop(self):
        """To be overridden by subclasses"""
        pass