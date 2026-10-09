import os
import re
import copy
import glob
import shutil
import time
import threading
import difflib
import cv2
import numpy as np
import keyboard
import pywinctl
from pynput.mouse import Button, Controller as MouseController
from utils import SpatialUtils, RobloxInputDriver
from settings import get_base_path

TEMPLATE_DIR = os.path.join(get_base_path(), "smart_templates")

DEFAULT_MOVE = {
    "enabled": True, "name": "", "key": "", "priority": 1,
    "repeat": 1, "repeat_delay": 0.15, "cooldown": 0.0,
    "mouse_mode": "none", "x": 0, "y": 0, "hold_click": 0.0,
    # one cast:  move mouse -> delay_before -> press key -> delay_after -> next move
    "delay_before": 0.0, "delay_after": 0.0,
}

DEFAULT_SMART = {
    "hotkey": "f6",
    "only_when_focused": True,
    "rotation": {
        "enabled": True, "region": [0, 0, 0, 0], "slot_count": 8,
        "threshold": 0.85, "tick": 0.1, "cast_delay": 0.25, "moves": [],
    },
    "combos": {"enabled": False, "list": []},   # only one of rotation / combos runs at a time
    "items": {"enabled": False, "region": [0, 0, 0, 0], "list": []},
}


# A loadout is a saved build: these sections + its own snapshot folder. Hotkey / focus stay global.
LOADOUT_SECTIONS = ("rotation", "combos", "items")
DEFAULT_LOADOUT = "Default"


def loadout_dir(name):
    safe = re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "_"
    return os.path.join(TEMPLATE_DIR, safe)


class SmartMacroLogic:
    """AFK skill rotation (image-based ready detection), skill combos and OCR item use.
    Each feature has its own enable switch; one master hotkey starts/stops them all."""

    def __init__(self, app):
        self.app = app
        self.utils = SpatialUtils()
        self.running = False
        self._threads = []
        self._combo_hooks = []
        self._combo_busy = threading.Lock()
        self._templates = {}
        self.cast_count = {}       # confirmed casts per slot (for the log)
        self.last_cast = {}        # slot -> time of its last cast (manual cooldowns)
        self._testing = False

    # ---------- config ----------
    @property
    def cfg(self):
        cfg = self.app.settings.get("smart_macro")
        if not cfg:
            import copy
            cfg = copy.deepcopy(DEFAULT_SMART)
            self.app.settings.settings["smart_macro"] = cfg
        for k, v in DEFAULT_SMART.items():
            if isinstance(v, dict):
                cfg.setdefault(k, {})
                for kk, vv in v.items():
                    cfg[k].setdefault(kk, vv)
            else:
                cfg.setdefault(k, v)
        return cfg

    # ---------- loadouts ----------
    def loadouts(self):
        """{name: saved sections}. The live config in "smart_macro" is always the ACTIVE loadout;
        the stored copy is refreshed whenever you switch away from it."""
        st = self.app.settings.settings
        if not st.get("skill_loadouts"):
            # First run: today's setup becomes "Default", and its snapshots move into its folder
            st["skill_loadouts"] = {DEFAULT_LOADOUT: self._snapshot_sections()}
            st["skill_active_loadout"] = DEFAULT_LOADOUT
            os.makedirs(loadout_dir(DEFAULT_LOADOUT), exist_ok=True)
            for f in glob.glob(os.path.join(TEMPLATE_DIR, "slot_*.png")):
                shutil.move(f, os.path.join(loadout_dir(DEFAULT_LOADOUT), os.path.basename(f)))
            self.app.settings.save()
        return st["skill_loadouts"]

    def active_loadout(self):
        names = self.loadouts()
        active = self.app.settings.settings.get("skill_active_loadout")
        return active if active in names else next(iter(names))

    def _snapshot_sections(self):
        return {k: copy.deepcopy(self.cfg[k]) for k in LOADOUT_SECTIONS}

    def _store_active(self):
        self.loadouts()[self.active_loadout()] = self._snapshot_sections()

    def switch_loadout(self, name):
        if name not in self.loadouts() or name == self.active_loadout():
            return False
        self._store_active()
        for k, v in copy.deepcopy(self.loadouts()[name]).items():
            self.cfg[k] = v
        self.app.settings.settings["skill_active_loadout"] = name
        self._templates.clear()
        self.app.settings.save()
        return True

    def new_loadout(self, name):
        """New loadout = copy of the current one (settings + snapshots), then switch to it."""
        if not name or name in self.loadouts():
            return False
        self._store_active()
        self.loadouts()[name] = self._snapshot_sections()
        src, dst = loadout_dir(self.active_loadout()), loadout_dir(name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        self.app.settings.settings["skill_active_loadout"] = name
        self._templates.clear()
        self.app.settings.save()
        return True

    def rename_loadout(self, old, new):
        lo = self.loadouts()
        if not new or new in lo or old not in lo:
            return False
        if old == self.active_loadout():
            self._store_active()
        lo[new] = lo.pop(old)
        if os.path.isdir(loadout_dir(old)):
            shutil.move(loadout_dir(old), loadout_dir(new))
        if self.app.settings.settings.get("skill_active_loadout") == old:
            self.app.settings.settings["skill_active_loadout"] = new
        self._templates.clear()
        self.app.settings.save()
        return True

    def delete_loadout(self, name):
        lo = self.loadouts()
        if name not in lo or len(lo) == 1:
            return False
        was_active = name == self.active_loadout()
        del lo[name]
        shutil.rmtree(loadout_dir(name), ignore_errors=True)
        if was_active:                               # load the next one without saving the deleted one
            first = next(iter(lo))
            for k, v in copy.deepcopy(lo[first]).items():
                self.cfg[k] = v
            self.app.settings.settings["skill_active_loadout"] = first
            self._templates.clear()
        self.app.settings.save()
        return True

    def template_path(self, slot):
        return os.path.join(loadout_dir(self.active_loadout()), f"slot_{slot}.png")

    def moves(self):
        rot = self.cfg["rotation"]
        moves = rot["moves"]
        n = max(1, min(10, int(rot["slot_count"])))
        rot["slot_count"] = n
        while len(moves) < n:
            m = dict(DEFAULT_MOVE)
            m["key"] = str((len(moves) + 1) % 10)  # slots 1-9 -> keys 1-9, slot 10 -> 0
            m["priority"] = len(moves) + 1
            moves.append(m)
        for m in moves:
            if "delay_before" not in m:          # settings from before the two delays existed
                m["delay_before"] = float(m.get("aim_wait", 0.1)) if m.get("mouse_mode", "none") != "none" else 0.0
                m["delay_after"] = float(m.get("anim") or 0)
            for old in ("aim_wait", "anim", "require_slot", "require_count"):
                m.pop(old, None)
            for k, v in DEFAULT_MOVE.items():
                m.setdefault(k, v)
        return moves[:n]

    def slot_regions(self):
        x1, y1, x2, y2 = self.cfg["rotation"]["region"]
        n = max(1, min(10, int(self.cfg["rotation"]["slot_count"])))
        if x2 - x1 < n or y2 <= y1:
            return []
        w = (x2 - x1) / n
        return [[int(x1 + i * w), y1, int(x1 + (i + 1) * w), y2] for i in range(n)]

    # ---------- templates ----------
    def capture_templates(self, slots=None):
        """Snapshot the given slots (default: all) as their READY image."""
        regions = self.slot_regions()
        if not regions:
            return 0
        os.makedirs(loadout_dir(self.active_loadout()), exist_ok=True)
        done = 0
        for i, r in enumerate(regions, start=1):
            if slots and i not in slots:
                continue
            img = self.utils.capture_screen_bgr(r)
            if img is not None and img.size:
                cv2.imwrite(self.template_path(i), img)
                done += 1
        self._templates.clear()
        return done

    def has_template(self, slot):
        return os.path.exists(self.template_path(slot))

    def _template(self, slot):
        if slot not in self._templates:
            img = cv2.imread(self.template_path(slot)) if self.has_template(slot) else None
            self._templates[slot] = img
        return self._templates[slot]

    def slot_score(self, slot, frame):
        tpl = self._template(slot)
        if tpl is None or frame is None or not frame.size:
            return None
        if frame.shape[:2] != tpl.shape[:2]:
            frame = cv2.resize(frame, (tpl.shape[1], tpl.shape[0]))
        a = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        b = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Normalised correlation catches layout (name text vs timer number);
        # mean brightness catches the darkened cooldown overlay.
        corr = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0][0])
        bright = 1.0 - min(1.0, abs(a.mean() - b.mean()) / max(b.mean(), 1.0))
        return min(corr, bright)

    def read_slots(self):
        """Return {slot: score or None} for every slot."""
        regions = self.slot_regions()
        if not regions:
            return {}
        x1, y1, x2, y2 = self.cfg["rotation"]["region"]
        bar = self.utils.capture_screen_bgr([x1, y1, x2, y2])
        out = {}
        for i, r in enumerate(regions, start=1):
            crop = bar[:, r[0] - x1:r[2] - x1]
            out[i] = self.slot_score(i, crop)
        return out

    def is_ready(self, slot, move, scores):
        score = scores.get(slot)
        if score is not None:
            # Snapshot wins: the screen reflects cooldown reduction from other casts,
            # a fixed manual timer would not.
            return score >= float(self.cfg["rotation"]["threshold"])
        # No snapshot: rely on the manual cooldown alone (none set = unconfigured, skip)
        cd = float(move["cooldown"] or 0)
        return cd > 0 and time.time() - self.last_cast.get(slot, 0) >= cd

    def toggle(self):
        self.stop() if self.running else self.start()

    def start(self):
        if self.running:
            return
        self.running = True
        cfg = self.cfg
        self._threads = []
        parts = []
        if cfg["rotation"]["enabled"]:
            if not self.slot_regions():
                self.app.log("Rotation: set the hotbar region first.")
            else:
                self._spawn(self._rotation_loop); parts.append("Rotation")
        if cfg["items"]["enabled"]:
            if not self.items_region():
                self.app.log("Items: set the hotbar region (Rotation page) or a scan area first.")
            else:
                self._spawn(self._items_loop); parts.append("Items")
        if cfg["combos"]["enabled"]:
            self._hook_combos(); parts.append("Combos")
        self.app.log(f"Running: {', '.join(parts) or 'nothing enabled'}")
        self.app.on_state_change(True)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self._unhook_combos()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads = []
        self.app.log("Stopped")
        self.app.on_state_change(False)

    def _spawn(self, fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        self._threads.append(t)

    def _focused(self):
        if not self.cfg.get("only_when_focused", True):
            return True
        try:
            w = pywinctl.getActiveWindow()
            return bool(w and "Roblox" in w.title)
        except Exception:
            return True

    def _wait(self, seconds):
        end = time.time() + seconds
        while self.running and time.time() < end:
            time.sleep(min(0.02, max(0.0, end - time.time())))
        return self.running

    def _aim(self, mode, x, y, wait=0.1):
        """Move (or click) the mouse to the move's spot, then wait so the game turns to it before the key.
        mode "none" = use wherever the mouse already is (no wait)."""
        if mode == "move":
            RobloxInputDriver.move_to(int(x), int(y))
        elif mode == "click":
            RobloxInputDriver.click_at(int(x), int(y), duration=0.04)
        else:
            return
        if wait:
            self._wait(float(wait))

    def _hold_click(self, seconds):
        """Hold left mouse at the current cursor position (after the key press)."""
        seconds = float(seconds or 0)
        if seconds <= 0:
            return
        mouse = MouseController()
        with RobloxInputDriver._lock:
            mouse.press(Button.left)
        try:
            end = time.time() + seconds
            while time.time() < end and (self.running or self._testing):
                time.sleep(0.02)
        finally:
            with RobloxInputDriver._lock:
                mouse.release(Button.left)

    def _click(self):
        """One left click (M1) wherever the mouse is."""
        mouse = MouseController()
        with RobloxInputDriver._lock:
            mouse.press(Button.left)
            time.sleep(0.04)
            mouse.release(Button.left)

    def use_item(self, item):
        """Item use = press its hotkey (equips it), short pause, then M1 to use it."""
        with RobloxInputDriver._lock:                    # not in the middle of the Event Notifier's /clear
            self._press(item["key"])
            if item.get("click", True):
                time.sleep(max(0.05, float(item.get("click_delay", 0.15) or 0.15)))
                self._click()
        self.app.log(f"Item '{item['name']}' seen -> pressed {item['key']}" + (" + M1" if item.get("click", True) else ""))

    def _press(self, key):
        if key:
            self.utils.send_key(key, 0.04)

    # ---------- rotation ----------
    def pick_move(self, scores):
        """Highest-priority enabled move that is ready."""
        best = None
        for slot, m in enumerate(self.moves(), start=1):
            if not m["enabled"] or not m["key"]:
                continue
            if not self.is_ready(slot, m, scores):
                continue
            if best is None or int(m["priority"]) < int(best[1]["priority"]):
                best = (slot, m)
        return best

    def _rotation_loop(self):
        self.cast_count, self.last_cast = {}, {}
        while self.running:
            try:
                rot = self.cfg["rotation"]
                if not self._focused():
                    self._wait(0.3); continue
                pick = self.pick_move(self.read_slots())
                if not pick:
                    self._wait(float(rot["tick"])); continue
                slot, m = pick
                for n in range(max(1, int(m["repeat"]))):
                    if not self.running:
                        return
                    # Same lock the Event Notifier holds while it hovers the chat / types /clear:
                    # a skill key pressed in the middle of that would land in the chat box.
                    with RobloxInputDriver._lock:
                        self._aim(m["mouse_mode"], m["x"], m["y"], 0)        # 1. move mouse (if it aims)
                        self._wait(float(m.get("delay_before") or 0))        # 2. delay before
                        self._press(m["key"])                                # 3. press
                        self._hold_click(m["hold_click"])
                    if n < int(m["repeat"]) - 1:
                        # gap between presses of a multi-use move (e.g. its 0.2 s anti-spam lockout)
                        self._wait(max(0.05, float(m.get("repeat_delay") or 0.15)))
                # 4. delay after (with a small floor so the icon has time to show its cooldown)
                self._wait(max(float(m.get("delay_after") or 0), float(rot["cast_delay"])))
                # Confirm the cast: a slot with a snapshot should no longer match it.
                score = self.read_slots().get(slot)
                if score is not None and score >= float(rot["threshold"]):
                    self.app.log(f"{m['name'] or 'Slot ' + str(slot)}: still ready, retrying")
                    continue
                self.last_cast[slot] = time.time()
                self.cast_count[slot] = self.cast_count.get(slot, 0) + 1
                self.app.log(f"Cast {m['name'] or 'slot ' + str(slot)} [{m['key']}]")
            except Exception as e:
                self.app.log(f"Rotation error: {e}")
                self._wait(0.5)

    # ---------- combos ----------
    def _hook_combos(self):
        self._unhook_combos()
        for combo in self.cfg["combos"]["list"]:
            trig = (combo.get("trigger") or "").strip().lower()
            if not trig or not combo.get("enabled", True) or not combo.get("steps"):
                continue
            try:
                h = keyboard.on_press_key(trig, lambda e, c=combo: self._fire_combo(c),
                                          suppress=not combo.get("passthrough", True))
                self._combo_hooks.append(h)
            except Exception as e:
                self.app.log(f"Combo hook error ({trig}): {e}")

    def _unhook_combos(self):
        for h in self._combo_hooks:
            try:
                keyboard.unhook(h)
            except Exception:
                pass
        self._combo_hooks = []

    def _fire_combo(self, combo):
        # Ignore re-triggers (key auto-repeat, or our own synthetic presses)
        if not self.running or not self._combo_busy.acquire(blocking=False):
            return
        threading.Thread(target=self._run_combo, args=(combo,), daemon=True).start()

    def _run_combo(self, combo):
        try:
            trig = (combo.get("trigger") or "").strip().lower()
            if not self._focused():
                self.app.log(f"Combo [{trig}]: skipped — Roblox isn't the focused window")
                return
            # Let go of the trigger first: if a step uses the same key, pressing it while you
            # still hold it gives the game "down, down, up" and the presses get swallowed.
            end = time.time() + 1.0
            while self.running and time.time() < end and keyboard.is_pressed(trig):
                time.sleep(0.01)
            time.sleep(0.03)
            for num, step in enumerate(combo.get("steps", []), start=1):
                if not self.running:
                    break
                # Each step: aim → (press the key → wait) N times, then the next step.
                # Waiting after EVERY press lets the skill's animation finish before pressing again.
                self._aim(step.get("mouse_mode", "none"), step.get("x", 0), step.get("y", 0), step.get("aim_wait", 0.1))
                n = max(1, int(step.get("repeat", 1) or 1))
                for i in range(n):
                    if not self.running:
                        break
                    with RobloxInputDriver._lock:            # not in the middle of the Event Notifier's /clear
                        self._press(step.get("key", ""))
                        self._hold_click(step.get("hold_click", 0))
                    self.app.log(f"Combo [{trig}]: step {num} pressed {step.get('key', '')}" + (f" ({i + 1}/{n})" if n > 1 else ""))
                    self._wait(max(0.08, float(step.get("delay", 0) or 0)))   # 0.08 s floor so taps stay separate
        except Exception as e:
            self.app.log(f"Combo error: {e}")
        finally:
            time.sleep(0.05)
            self._combo_busy.release()

    # ---------- items (OCR) ----------
    @staticmethod
    def _norm(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())

    def items_region(self):
        """The area where pickup messages like "Obtained Copper!" show up."""
        r = self.cfg["items"]["region"]
        return r if r[2] > r[0] and r[3] > r[1] else None

    def match_items(self, texts):
        """Items from the list whose name appears in any of the OCR'd lines."""
        hits = []
        for item in self.cfg["items"]["list"]:
            name = self._norm(item.get("name", ""))
            if not name or not item.get("key") or not item.get("enabled", True):
                continue
            for t in texts:
                t = self._norm(t)
                # "Copper" is inside "Obtained Copper!"; the ratio check forgives small OCR typos
                if name in t or difflib.SequenceMatcher(None, name, t).ratio() >= 0.8 or \
                        any(difflib.SequenceMatcher(None, name, t[i:i + len(name)]).ratio() >= 0.8
                            for i in range(0, max(1, len(t) - len(name) + 1))):
                    hits.append(item); break
        return hits

    def read_items(self):
        region = self.items_region()
        if not region:
            return []
        res = self.utils.get_text_from_region(region)
        if self.utils.ocr_reader is False:
            self.app.log(self.utils.ocr_error or "Text reading (OCR) couldn't start.")   # usually: Visual C++ missing
        return [text for _, text, conf in res if conf > 0.4]

    def _items_loop(self):
        """Press an item's key ONCE when its message appears; again only after it has gone away
        and its cooldown (seconds after the last use) is over."""
        showing, last_used = set(), {}
        while self.running:
            try:
                if not self._focused():
                    self._wait(0.3); continue
                hits = self.match_items(self.read_items())
                now = {id(i) for i in hits}
                for item in hits:
                    cd = float(item.get("cooldown") or 0)
                    if id(item) not in showing and time.time() - last_used.get(id(item), 0) >= cd:
                        self.use_item(item)
                        last_used[id(item)] = time.time()
                showing = now
                self._wait(0.05)
            except Exception as e:
                self.app.log(f"Items error: {e}")
                self._wait(0.5)
