import ctypes
import os
import threading
import cv2
import time
import random  
import numpy as np
import pywinctl
from pynput.mouse import Controller as MouseController
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
                    self.handle_ok_popup(fast=self.walking)
                finally:
                    self._ok_scanner_lock.release()

            for i in range(40):
                if not self.running or not self.ok_scanner_running:
                    return
                if self.walking:                       # mid-route: a pop up freezes you - catch it within ~0.3 s
                    time.sleep(0.25)
                    break
                time.sleep(0.25)

    def remember_roblox(self):
        """The Roblox window this macro plays in: the one in front now (else the first one open)."""
        from utils import foreground_roblox, roblox_windows
        self._roblox_hwnd = foreground_roblox() or next((h for h, _ in roblox_windows()), 0)

    def force_focus_on(self):
        return bool(self.app.settings.get("force_roblox_focus", True))

    def wait_focus_for_test(self, seconds=10):
        """Setup / test buttons: switch to Roblox by itself. One Roblox open -> straight to it. Several ->
        the one this macro used last, else click into the one you want (it's remembered)."""
        from utils import roblox_windows, focus_roblox
        if self.check_focus():
            self.remember_roblox()
            return True
        wins = [h for h, _ in roblox_windows()]
        last = getattr(self, "_roblox_hwnd", 0)
        target = wins[0] if len(wins) == 1 else (last if last in wins else 0)
        if target and focus_roblox(target):
            end = time.time() + 1.5
            while time.time() < end and not self.check_focus():
                time.sleep(0.05)
            if self.check_focus():
                self.app.log("Switched to Roblox.")
                time.sleep(0.4)                          # let Roblox take the mouse / keyboard
                return True
        if not wins:
            self.app.log("Roblox isn't open - open it first.")
            return False
        if len(wins) > 1 and not target:
            self.app.log(f"{len(wins)} Roblox windows are open - click into the one to use "
                         f"(within {seconds}s); it's remembered for next time.")
        else:
            self.app.log(f"Click into Roblox - it starts as soon as it's focused (within {seconds}s)...")
        end = time.time() + seconds
        while time.time() < end:
            if self.check_focus():
                self.remember_roblox()
                time.sleep(0.3)
                return True
            time.sleep(0.1)
        self.app.log("Roblox wasn't focused - cancelled. (Tip: press the test's hotkey while in Roblox - "
                     "see the Hotkeys tab.)")
        return False

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
        """Move -> wait (Click delay) -> click."""
        with self.input_lock:
            RobloxInputDriver.glide_click(x, y, duration=random.uniform(0.02, 0.04), glide=max(0.25, duration))

    def get_screen_size(self):
        """Returns the screen width and height using screeninfo."""
        try:
            for m in get_monitors():
                if m.is_primary:
                    return m.width, m.height
        except Exception:
            pass
        return 1920, 1080           

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

    def get_ok_search_region(self, fast=False):
        """Area the OK detector scans. Uses the user-set 'ok_scan_area' if present, otherwise the whole
        screen (every monitor) once the OK button is captured - or, fast (mid-route), just the Roblox window.
        None = not set up."""
        regions = self.app.settings.get("regions", {})
        scan = regions.get("ok_scan_area", [0, 0, 0, 0])
        if scan and any(v != 0 for v in scan):
            return list(scan)
        if self._ok_button_box() and fast:
            return list(self.get_roblox_window_region())
        if self._ok_button_box():
            m = self.utils.sct.monitors[0]
            return [m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"]]
        return None

    def _ok_button_box(self, pad=0):
        btn = self.app.settings.get("regions", {}).get("ok_button", [0, 0, 0, 0])
        if not (btn and any(v != 0 for v in btn)):
            return None
        return [max(0, btn[0] - pad), max(0, btn[1] - pad), btn[2] + pad, btn[3] + pad]

    def find_ok_button(self, fast=False):
        """Look for the OK button only inside the OK scan area. Returns (x, y, score) or None.
        Uses grayscale template matching on a small crop — much cheaper than OCR on the whole window."""
        search = self.get_ok_search_region(fast)
        if not search:
            if not getattr(self, "_ok_region_warned", False):
                self.app.log("OK detection not set up — capture the OK button on the Pop Up page.")
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
        RobloxInputDriver.glide_click(cx, cy, duration=0.035)

    # ---------- other pop ups: a picture of something only that pop up shows + where to click ----------
    def popups(self):
        """[{id, name, enabled, click: [x, y]}] - each has its picture in data/popups/<id>.png."""
        lst = self.app.settings.settings.setdefault("popups", [])
        for pp in lst:
            pp.setdefault("name", "Pop up")
            pp.setdefault("enabled", True)
            pp.setdefault("click", [0, 0])
        return lst

    @staticmethod
    def popup_path(pp):
        from settings import get_base_path
        return os.path.join(get_base_path(), "popups", f"{pp['id']}.png")

    def add_popup(self, name="Pop up"):
        import uuid
        pp = {"id": uuid.uuid4().hex[:8], "name": name, "enabled": True, "click": [0, 0]}
        self.popups().append(pp)
        self.app.settings.save()
        return pp

    def remove_popup(self, pp):
        lst = self.popups()
        if pp in lst:
            lst.remove(pp)
            self.app.settings.save()
        try:
            os.remove(self.popup_path(pp))
        except OSError:
            pass

    def capture_popup(self, pp, region):
        """Save what's inside the box as this pop up's picture (something only it shows, e.g. its title)."""
        if region[2] - region[0] < 5 or region[3] - region[1] < 5:
            return False
        img = self.utils.capture_screen_bgr(region)
        if img is None or not img.size:
            return False
        os.makedirs(os.path.dirname(self.popup_path(pp)), exist_ok=True)
        getattr(self, "_popup_tpls", {}).pop(pp["id"], None)
        return cv2.imwrite(self.popup_path(pp), img)

    def has_popup_picture(self, pp):
        return os.path.exists(self.popup_path(pp))

    def _popup_tpl(self, pp):
        cache = self.__dict__.setdefault("_popup_tpls", {})
        path = self.popup_path(pp)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        hit = cache.get(pp["id"])
        if hit is None or hit[0] != mtime:
            img = cv2.imread(path)
            hit = (mtime, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img is not None else None)
            cache[pp["id"]] = hit
        return hit[1]

    def _popup_search_region(self, fast=False):
        """The OK scan area if you set one, else every monitor (fast, mid-route: just the Roblox window)."""
        scan = self.app.settings.get("regions", {}).get("ok_scan_area", [0, 0, 0, 0])
        if scan and scan[2] > scan[0] and scan[3] > scan[1]:
            return list(scan)
        if fast:
            return list(self.get_roblox_window_region())
        m = self.utils.sct.monitors[0]
        return [m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"]]

    def find_popup(self, pp, frame=None, origin=None):
        """(x, y, score) where this pop up's picture is on screen, or None."""
        tpl = self._popup_tpl(pp)
        if tpl is None:
            return None
        if frame is None:
            region = self._popup_search_region()
            frame = cv2.cvtColor(self.utils.capture_screen_bgr(region), cv2.COLOR_BGR2GRAY)
            origin = region[:2]
        if tpl.shape[0] > frame.shape[0] or tpl.shape[1] > frame.shape[1]:
            return None
        _, val, _, loc = cv2.minMaxLoc(cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED))
        if val < float(self.app.settings.get("ok_match_threshold", self.OK_MATCH_THRESHOLD)):
            return None
        return origin[0] + loc[0] + tpl.shape[1] // 2, origin[1] + loc[1] + tpl.shape[0] // 2, val

    def find_custom_popup(self, fast=False):
        """The first enabled pop up (with a picture AND a click spot) that's on screen: (pp, x, y, score)."""
        ready = [pp for pp in self.popups() if pp["enabled"] and any(pp["click"]) and self.has_popup_picture(pp)]
        if not ready:
            return None
        region = self._popup_search_region(fast)
        frame = cv2.cvtColor(self.utils.capture_screen_bgr(region), cv2.COLOR_BGR2GRAY)
        for pp in ready:
            hit = self.find_popup(pp, frame, region[:2])
            if hit:
                return (pp,) + hit
        return None

    def test_popup(self, pp):
        """Look for this one pop up now; found -> click its spot."""
        if not self.has_popup_picture(pp):
            self.app.log(f"Pop up '{pp['name']}': capture its picture first.")
            return
        hit = self.find_popup(pp)
        if not hit:
            self.app.log(f"Pop up '{pp['name']}': NOT on screen (open it, then Test).")
            return
        if not any(pp["click"]):
            self.app.log(f"Pop up '{pp['name']}': found [match {hit[2]:.2f}] - set its click spot to click it.")
            return
        self.app.log(f"Pop up '{pp['name']}': found [match {hit[2]:.2f}] - clicking {tuple(pp['click'])}.")
        self._click_ok(*pp["click"])

    def _mark_popup_seen(self, t_scan):
        """A pop up was just found: it appeared somewhere between the last clean look and now, and the
        character has been frozen since then. A walk gives that time back too (see RouteNav._ok_pause)."""
        clean = getattr(self, "_popup_clean_at", None)
        self._popup_since = (clean + t_scan) / 2 if clean and 0 < t_scan - clean < 3.0 else t_scan

    def handle_ok_popup(self, fast=False):
        t_scan = time.perf_counter()
        try:
            other = None
            hit = self.find_ok_button(fast)
            if not hit:
                other = self.find_custom_popup(fast)
            if not hit and not other:
                self._popup_clean_at = t_scan
                return False
            self._mark_popup_seen(t_scan)
            if other:
                pp, _, _, score = other
                cx, cy = pp["click"]
                self.app.log(f"Pop up '{pp['name']}' found [match {score:.2f}]. Clicking at ({cx}, {cy})...")
                self.ok_busy.set()                     # a route walk pauses until this is done
                try:
                    if self._click_ok(cx, cy) is False:
                        return False
                finally:
                    self.ok_busy.clear()
                return True
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

    def setup_problems(self):
        """Things missing in the setup that the macro can't sort out by itself, checked when Start is pressed
        (settings / files only, nothing on screen): [{'id', 'text', 'block'}]. block = it can't run at all;
        the others can be ignored ('don't warn me again'). Each macro lists its own."""
        return []

    def main_loop(self):
        """To be overridden by subclasses"""
        pass