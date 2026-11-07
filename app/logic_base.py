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
        self.ok_busy = threading.Event()
        self.walking = False
        self._global_ok_active = False
        self._global_ok_thread = None
        self.popup_up = False
        self._pp_backoff = {}

    def warn_if_roblox_admin(self):
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
        old = [t for t in (getattr(self, "thread", None), getattr(self, "ok_scanner_thread", None))
               if t is not None and t.is_alive() and t is not threading.current_thread()]
        if not self.running and old:
            if getattr(self, "_start_waiting", False):
                return
            self._start_waiting = True
            self.app.log("Waiting for the last run to finish stopping...")

            def later():
                for t in old:
                    t.join(timeout=20)
                self._start_waiting = False
                if any(t.is_alive() for t in old):
                    self.app.log("The last run is still busy - press Start again in a moment.")
                    return
                self.start()
                sync = getattr(self.app, "_sync_start_btn", None)
                if sync:
                    self.app.root.after(0, sync)
            threading.Thread(target=later, daemon=True).start()
            return
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
            self.thread = threading.Thread(target=self._run_main_loop, daemon=True)
            self.thread.start()
            self.app.log("Macro thread started")

    def _run_main_loop(self):
        try:
            self.main_loop()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.app.log(f"Macro error: {e} - stopped.")
        finally:
            self.running = False
            self.ok_scanner_running = False
            self._release_keys()

    @staticmethod
    def _release_keys():
        try:
            from utils import release_all_keys
            release_all_keys()
        except Exception:
            pass

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
        self._release_keys()
        self.app.log("Macro stopped")

    def start_global_ok_scanner(self):
        if self._global_ok_active:
            return
        self._global_ok_active = True
        self._global_ok_thread = threading.Thread(target=self._global_ok_loop, daemon=True)
        self._global_ok_thread.start()
        self.app.log("Always-Click-OK: Enabled")

    def stop_global_ok_scanner(self):
        self._global_ok_active = False
        self.app.log("Always-Click-OK: Disabled")

    @staticmethod
    def _ok_wait(took):
        return min(10.0, max(1.0, took * 10))

    def _global_ok_loop(self):
        while self._global_ok_active:
            took = 0.0
            if self._ok_scanner_lock.acquire(blocking=False):
                t0 = time.perf_counter()
                try:
                    self.handle_ok_popup()
                except Exception as e:
                    self.app.log(f"Always-OK error: {e}")
                finally:
                    self._ok_scanner_lock.release()
                took = time.perf_counter() - t0
            end = time.perf_counter() + self._ok_wait(took)
            while time.perf_counter() < end:
                if not self._global_ok_active:
                    return
                time.sleep(0.25)

    def _ok_scanner_loop(self):
        while self.running and self.ok_scanner_running:
            took = 0.0
            if self._ok_scanner_lock.acquire(blocking=False):
                t0 = time.perf_counter()
                try:
                    self.handle_ok_popup(fast=self.walking)
                finally:
                    self._ok_scanner_lock.release()
                took = time.perf_counter() - t0

            end = time.perf_counter() + self._ok_wait(took)
            while time.perf_counter() < end:
                if not self.running or not self.ok_scanner_running:
                    return
                if self.walking:
                    time.sleep(0.25)
                    break
                time.sleep(0.25)

    def remember_roblox(self):
        from utils import foreground_roblox, roblox_windows
        self._roblox_hwnd = foreground_roblox() or next((h for h, _ in roblox_windows()), 0)

    def force_focus_on(self):
        return bool(self.app.settings.get("force_roblox_focus", True))

    def wait_focus_for_test(self, seconds=10):
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
                time.sleep(0.4)
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
            RobloxInputDriver.glide_click(x, y, duration=random.uniform(0.02, 0.04), glide=max(0.25, duration))

    def get_screen_size(self):
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
    OK_SEARCH_PAD = 60
    OK_MATCH_THRESHOLD = 0.80

    def _ok_template_path(self):
        from settings import get_base_path
        return os.path.join(get_base_path(), self.OK_TEMPLATE_FILE)

    def capture_ok_template(self, region):
        try:
            if region[2] - region[0] < 5 or region[3] - region[1] < 5:
                return False
            img = self.utils.capture_screen_bgr(region)
            cv2.imwrite(self._ok_template_path(), img)
            self._ok_template = None
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
            return self._match_on_roblox(frame, tpl, (sx, sy))

        if not any(self.app.settings.get("regions", {}).get("ok_scan_area") or [0]):
            search = self._ok_button_box(self.OK_SEARCH_PAD) or search
            sx, sy = search[0], search[1]
        for bbox, text, conf in self.utils.get_text_from_region(search, upscale=2):
            if text.strip().lower() == "ok":
                return (sx + int(np.mean([p[0] for p in bbox])),
                        sy + int(np.mean([p[1] for p in bbox])), conf)
        return None

    def resolve_ok_click(self, hit):
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

    def popups(self):
        lst = self.app.settings.settings.setdefault("popups", [])
        for pp in lst:
            pp.setdefault("name", "Pop up")
            pp.setdefault("enabled", True)
            pp.setdefault("click", [0, 0])
            pp.setdefault("area", [0, 0, 0, 0])
            steps = pp.setdefault("steps", [])
            old = self.popup_click_path(pp)
            if not steps and os.path.exists(old):
                st = self.new_step(pp)
                try:
                    os.replace(old, self.step_path(pp, st))
                except OSError:
                    steps.remove(st)
            for st in steps:
                st.setdefault("click", [0, 0])
                st.setdefault("wait", 1.0)
        return lst

    @staticmethod
    def popup_area(pp):
        a = pp.get("area") or [0, 0, 0, 0]
        return [int(v) for v in a] if a[2] > a[0] and a[3] > a[1] else None

    @staticmethod
    def popup_path(pp):
        from settings import get_base_path
        return os.path.join(get_base_path(), "popups", f"{pp['id']}.png")

    def add_popup(self, name="Pop up"):
        import uuid
        pp = {"id": uuid.uuid4().hex[:8], "name": name, "enabled": True, "click": [0, 0], "area": [0, 0, 0, 0]}
        self.popups().append(pp)
        self.app.settings.save()
        return pp

    def remove_popup(self, pp):
        lst = self.popups()
        if pp in lst:
            lst.remove(pp)
            self.app.settings.save()
        for path in [self.popup_path(pp), self.popup_click_path(pp)] + \
                [self.step_path(pp, st) for st in pp.get("steps", [])]:
            try:
                os.remove(path)
            except OSError:
                pass

    def capture_popup(self, pp, region):
        if region[2] - region[0] < 5 or region[3] - region[1] < 5:
            return False
        img = self.utils.capture_screen_bgr(region)
        if img is None or not img.size:
            return False
        os.makedirs(os.path.dirname(self.popup_path(pp)), exist_ok=True)
        getattr(self, "_popup_tpls", {}).pop(pp["id"], None)
        return cv2.imwrite(self.popup_path(pp), img)

    @staticmethod
    def popup_click_path(pp):
        from settings import get_base_path
        return os.path.join(get_base_path(), "popups", f"{pp['id']}_click.png")

    @staticmethod
    def step_path(pp, st):
        from settings import get_base_path
        return os.path.join(get_base_path(), "popups", f"{pp['id']}_{st['id']}.png")

    def new_step(self, pp):
        import uuid
        st = {"id": uuid.uuid4().hex[:6], "click": [0, 0], "wait": 1.0}
        pp.setdefault("steps", []).append(st)
        self.app.settings.save()
        return st

    def remove_step(self, pp, st):
        if st in pp.get("steps", []):
            pp["steps"].remove(st)
            self.app.settings.save()
        try:
            os.remove(self.step_path(pp, st))
        except OSError:
            pass

    def has_step_picture(self, pp, st):
        return os.path.exists(self.step_path(pp, st))

    def capture_step_picture(self, pp, st, region):
        if region[2] - region[0] < 5 or region[3] - region[1] < 5:
            return False
        img = self.utils.capture_screen_bgr(region)
        if img is None or not img.size:
            return False
        os.makedirs(os.path.dirname(self.step_path(pp, st)), exist_ok=True)
        return cv2.imwrite(self.step_path(pp, st), img)

    def find_step_picture(self, pp, st, fast=False, seconds=3.0):
        img = cv2.imread(self.step_path(pp, st)) if self.has_step_picture(pp, st) else None
        if img is None:
            return None
        tpl = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        region = self._popup_search_region(fast)
        end = time.time() + seconds
        while True:
            frame = cv2.cvtColor(self.utils.capture_screen_bgr(region), cv2.COLOR_BGR2GRAY)
            hit = self._match_on_roblox(frame, tpl, region[:2])
            if hit:
                return hit[0], hit[1]
            if time.time() >= end:
                return None
            time.sleep(0.25)

    def run_popup(self, pp, found_xy, fast=False):
        steps = pp.get("steps") or []
        if not steps:
            spot = tuple(pp["click"]) if any(pp["click"]) else tuple(found_xy)
            self.app.log(f"Pop up '{pp['name']}': clicking {spot}" + ("" if any(pp["click"]) else " (where it was found)"))
            return self._click_ok(*spot) is not False
        for n, st in enumerate(steps, start=1):
            time.sleep(max(0.0, float(st.get("wait") or 0)))
            if self.has_step_picture(pp, st):
                hit = self.find_step_picture(pp, st, fast)
                if not hit:
                    self.app.log(f"Pop up '{pp['name']}': step {n}'s picture isn't on screen - stopped.")
                    return False
                spot = tuple(st["click"]) if any(st["click"]) else hit
            elif any(st["click"]):
                spot = tuple(st["click"])
            else:
                self.app.log(f"Pop up '{pp['name']}': step {n} has no picture and no click spot - skipped.")
                continue
            self.app.log(f"Pop up '{pp['name']}': step {n} - clicking {spot}")
            if self._click_ok(*spot) is False:
                return False
        return True

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
        if fast:
            return list(self.get_roblox_window_region())
        m = self.utils.sct.monitors[0]
        return [m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"]]

    def _match_on_roblox(self, frame, tpl, origin, threshold=None):
        if tpl is None or tpl.shape[0] > frame.shape[0] or tpl.shape[1] > frame.shape[1]:
            return None
        if threshold is None:
            threshold = float(self.app.settings.get("ok_match_threshold", self.OK_MATCH_THRESHOLD))
        from utils import roblox_window_at
        res = cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED)
        th, tw = tpl.shape[:2]
        for _ in range(8):
            _, val, _, loc = cv2.minMaxLoc(res)
            if val < threshold:
                return None
            x, y = origin[0] + loc[0] + tw // 2, origin[1] + loc[1] + th // 2
            if roblox_window_at(x, y) != 0:
                return x, y, val
            res[max(0, loc[1] - th // 2):loc[1] + th // 2 + 1, max(0, loc[0] - tw // 2):loc[0] + tw // 2 + 1] = -1
        return None

    def find_popup(self, pp, frame=None, origin=None):
        tpl = self._popup_tpl(pp)
        if tpl is None:
            return None
        if frame is None:
            region = self.popup_area(pp) or self._popup_search_region()
            frame = cv2.cvtColor(self.utils.capture_screen_bgr(region), cv2.COLOR_BGR2GRAY)
            origin = region[:2]
        return self._match_on_roblox(frame, tpl, origin)

    def find_custom_popup(self, fast=False):
        ready = [pp for pp in self.popups() if pp["enabled"] and self.has_popup_picture(pp)]
        if not ready:
            return None
        shared = None
        for pp in ready:
            own = self.popup_area(pp)
            if own:
                hit = self.find_popup(pp)
            else:
                if shared is None:
                    region = self._popup_search_region(fast)
                    shared = (cv2.cvtColor(self.utils.capture_screen_bgr(region), cv2.COLOR_BGR2GRAY), region[:2])
                hit = self.find_popup(pp, *shared)
            if hit:
                return (pp,) + hit
        return None

    def test_popup(self, pp):
        if not self.has_popup_picture(pp):
            self.app.log(f"Pop up '{pp['name']}': capture its picture first.")
            return
        hit = self.find_popup(pp)
        if not hit:
            area, tpl = self.popup_area(pp), self._popup_tpl(pp)
            if area and tpl is not None and (area[2] - area[0] < tpl.shape[1] or area[3] - area[1] < tpl.shape[0]):
                self.app.log(f"Pop up '{pp['name']}': its scan area is smaller than its picture - set a bigger area.")
            else:
                self.app.log(f"Pop up '{pp['name']}': NOT " + ("in its scan area" if area else "on screen")
                             + " (open it, then Test).")
            return
        self.app.log(f"Pop up '{pp['name']}': found [match {hit[2]:.2f}].")
        self.run_popup(pp, (hit[0], hit[1]))

    def _mark_popup_seen(self, t_scan):
        clean = getattr(self, "_popup_clean_at", None)
        self._popup_since = (clean + t_scan) / 2 if clean and 0 < t_scan - clean < 3.0 else t_scan

    def handle_ok_popup(self, fast=False):
        t_scan = time.perf_counter()
        try:
            other = None
            hit = self.find_ok_button(fast)
            if not hit:
                other = self.find_custom_popup(fast)
            self.popup_up = bool(hit or other)
            if not hit and not other:
                self._popup_clean_at = t_scan
                self._pp_backoff = {}
                return False
            self._mark_popup_seen(t_scan)
            if other:
                pp, fx, fy, score = other
                if self._popup_backoff(pp.get("id", pp.get("name")), fx, fy):
                    return False
                self.app.log(f"Pop up '{pp['name']}' found [match {score:.2f}].")
                self.ok_busy.set()
                try:
                    if not self.run_popup(pp, (fx, fy), fast):
                        return False
                finally:
                    self.ok_busy.clear()
                self.popups_clicked = getattr(self, "popups_clicked", 0) + 1
                return True
            if hit:
                cx, cy, score = self.resolve_ok_click(hit)
                if self._popup_backoff("ok", cx, cy):
                    return False
                self.app.log(f"Found 'Ok' [match {score:.2f}]. Clicking at ({cx}, {cy})...")
                self.ok_busy.set()
                try:
                    if self._click_ok(cx, cy) is False:
                        return False
                finally:
                    self.ok_busy.clear()
                self.popups_clicked = getattr(self, "popups_clicked", 0) + 1
                if self.on_ok_clicked:
                    threading.Thread(target=self.on_ok_clicked, daemon=True).start()
                return True
        except Exception as e:
            self.app.log(f"Error checking for Ok popup: {e}")
        return False

    def _popup_backoff(self, kind, x, y):
        key, now = (kind, int(x) // 20, int(y) // 20), time.time()
        n, until = self._pp_backoff.get(key, (0, 0.0))
        if now < until:
            return True
        self._pp_backoff[key] = (n + 1, now + (min(30, 2 ** (n - 2)) if n >= 3 else 0))
        if n == 3:
            self.app.log("This pop up is still there after 3 clicks - trying less often. Check its click spot "
                         "on the Pop Up page.")
        return False

    def _click_ok(self, cx, cy):
        from utils import roblox_window_at
        from logic_events import EventWatcher
        target = roblox_window_at(cx, cy)
        if target == 0:
            if time.time() - getattr(self, "_covered_logged", 0) > 60:
                self._covered_logged = time.time()
                self.app.log("OK popup is covered by another window - not clicking (move the macro window away).")
            return False
        with RobloxInputDriver._lock:
            prev = ctypes.windll.user32.GetForegroundWindow()
            old_x, old_y = self.get_cursor_pos()
            if target > 0 and prev != target:
                EventWatcher.focus_window(target, timeout=1.0)
                time.sleep(0.15)
            self.human_click(cx, cy, duration=0.15)
            RobloxInputDriver.move_to(old_x, old_y)
            from utils import roblox_windows
            if prev and prev != ctypes.windll.user32.GetForegroundWindow() and prev in [h for h, _ in roblox_windows()]:
                time.sleep(0.2)
                EventWatcher.focus_window(prev, timeout=1.0)
        return True

    def setup_problems(self):
        return []

    def main_loop(self):
        pass