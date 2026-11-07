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
from utils import SpatialUtils, RobloxInputDriver, is_roblox_title
from settings import get_base_path

TEMPLATE_DIR = os.path.join(get_base_path(), "smart_templates")

DEFAULT_MOVE = {
    "enabled": True, "name": "", "key": "", "priority": 1,
    "repeat": 1, "repeat_delay": 0.15, "cooldown": 0.0,
    "mouse_mode": "none", "x": 0, "y": 0, "click": False, "m1_delay": 0.3,
    "click_btn": "m2",
    "after_click": 0.1,
    "delay_before": 0.0, "delay_after": 0.0,
    "box": None,
    "ready_at": 0.0,
}

MEDITATION_DEFAULT = {
    "enabled": False, "region": [0, 0, 0, 0],
    "out": "weapon",
    "weapon_key": "r", "grimoire_key": "g", "key": "n", "max_wait": 90,
    "below": 5,
    "stuck_after": 20,
    "key_delay": 1.0,
    "waits": {},
}

ANTI_SHAKE_DEFAULT = {"enabled": False, "every": 30, "key": ",", "between": 1.0, "after": 0.5,
                      "check_region": [0, 0, 0, 0]}
ANTI_SHAKE_REF = os.path.join(TEMPLATE_DIR, "anti_shake_skilltree.png")

MANA_SKIN_DEFAULT = {"enabled": False, "every": 300, "between": 1.0}
RESET_LAG_DEFAULT = {"enabled": False, "every": 30, "text": "Main Menu", "wait": 1.0}
RESET_LAG_PIC = os.path.join(TEMPLATE_DIR, "reset_lag_menu_button.png")

DEFAULT_SMART = {
    "hotkey": "f6",
    "only_when_focused": True,
    "rotation": {
        "enabled": True, "region": [0, 0, 0, 0], "slot_count": 8,
        "threshold": 0.85, "tick": 0.1, "cast_delay": 0.25, "moves": [],
    },
    "combos": {"enabled": False, "list": []},
    "items": {"enabled": False, "region": [0, 0, 0, 0], "list": []},
    "target": {
        "enabled": False, "creature": "Creature 1", "creatures": {},
        "found_steps": [], "lost_steps": [],
        "start_delay": 0.5,
        "poll": 0.25, "seen_after": 2, "lost_after": 1.5,
    },
}


LOADOUT_SECTIONS = ("rotation", "combos", "items", "target")
DEFAULT_LOADOUT = "Default"


def loadout_dir(name):
    safe = re.sub(r'[<>:"/\\|?*]', "_", name).strip() or "_"
    return os.path.join(TEMPLATE_DIR, safe)


class SmartMacroLogic:

    def __init__(self, app):
        self.app = app
        self.utils = SpatialUtils()
        self.running = False
        self._threads = []
        self._combo_hooks = []
        self._combo_busy = threading.Lock()
        self._templates = {}
        self.cast_count = {}
        self.last_cast = {}
        self._still = {}
        self._still_warned = {}
        self._testing = False

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

    def loadouts(self):
        st = self.app.settings.settings
        if not st.get("skill_loadouts"):
            st["skill_loadouts"] = {DEFAULT_LOADOUT: self._snapshot_sections()}
            st["skill_active_loadout"] = DEFAULT_LOADOUT
            os.makedirs(loadout_dir(DEFAULT_LOADOUT), exist_ok=True)
            for f in glob.glob(os.path.join(TEMPLATE_DIR, "slot_*.png")):
                shutil.move(f, os.path.join(loadout_dir(DEFAULT_LOADOUT), os.path.basename(f)))
            self.app.settings.save()
        return st["skill_loadouts"]

    def _fill_section(self, k, v):
        cur = self.cfg.get(k)
        if isinstance(cur, dict) and isinstance(v, dict):
            cur.clear()
            cur.update(v)
        else:
            self.cfg[k] = v

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
        saved = copy.deepcopy(self.loadouts()[name])
        for k in LOADOUT_SECTIONS:
            saved.setdefault(k, copy.deepcopy(DEFAULT_SMART[k]))
        for k, v in saved.items():
            self._fill_section(k, v)
        self.app.settings.settings["skill_active_loadout"] = name
        self._templates.clear()
        self.app.settings.save()
        return True

    def new_loadout(self, name):
        if not name or name in self.loadouts():
            return False
        self._store_active()
        fresh = {k: copy.deepcopy(DEFAULT_SMART[k]) for k in LOADOUT_SECTIONS}
        self.loadouts()[name] = copy.deepcopy(fresh)
        for k, v in fresh.items():
            self._fill_section(k, v)
        dst = loadout_dir(name)
        if os.path.isdir(dst):
            shutil.rmtree(dst, ignore_errors=True)
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
        if was_active:
            first = next(iter(lo))
            for k, v in copy.deepcopy(lo[first]).items():
                self._fill_section(k, v)
            self.app.settings.settings["skill_active_loadout"] = first
            self._templates.clear()
        self.app.settings.save()
        return True

    def template_path(self, slot):
        return os.path.join(loadout_dir(self.active_loadout()), f"slot_{slot}.png")

    def setup_problems(self):
        rot = self.cfg["rotation"]
        out = []
        if rot.get("enabled") and not any(m.get("enabled", True) and m.get("key") for m in self.moves()):
            out.append({"id": "skill_no_keys", "block": False, "short": "No slot has a key", "go": ("Rotation", "skill_slots"),
                        "text": "Rotation is on but no slot has a key yet - type each move's key on its slot (Rotation page)."})
        if self.target_on():
            if not rot.get("enabled"):
                out.append({"id": "skill_target_rot", "block": True, "short": "Target needs Rotation on",
                            "go": ("Target", "skill_target_on"),
                            "text": "Target is on, but it decides when the Rotation casts - turn Rotation on too."})
            if not (self.creature().get("color1")):
                out.append({"id": "skill_target_color", "block": True, "short": "No creature colour picked",
                            "go": ("Target", "skill_target_c1"),
                            "text": f"Target is on but '{self.target()['creature']}' has no colour picked (Target page)."})
        return out

    def target(self):
        return self.cfg["target"]

    def target_on(self):
        return bool(self.target().get("enabled"))

    def creature(self, name=None):
        from creature import DEFAULT_CREATURE
        t = self.target()
        name = name or t.get("creature") or "Creature 1"
        c = t.setdefault("creatures", {}).setdefault(name, copy.deepcopy(DEFAULT_CREATURE))
        for k, v in DEFAULT_CREATURE.items():
            c.setdefault(k, copy.deepcopy(v))
        return c

    def _target_settings(self):
        t = self.target()
        return {"creature": self.creature(), "poll": t.get("poll", 0.25), "seen_after": t.get("seen_after", 2),
                "lost_after": t.get("lost_after", 1.5)}

    def make_watcher(self):
        from creature import CreatureWatcher
        return CreatureWatcher(lambda r: self.utils.capture_screen_bgr(r), self._target_settings,
                               lambda: self.running, self._roblox_region, self.app.log)

    def test_target(self):
        w = self.make_watcher()
        ok, pos, info = w.look()
        name = self.target().get("creature")
        said = (f"Target '{name}': FOUND at {pos} ({info.get('how') or str(info.get('px', 0)) + ' px of colour 1'})" if ok
                else f"Target '{name}': not found - {info.get('why', '?')}")
        self.app.log(said)
        return (info.get("box") if ok else None), said

    def aims_at_target(self):
        t = self.target()
        steps = [st for c in self.cfg["combos"]["list"] for st in c.get("steps", [])] + \
            list(t.get("found_steps") or []) + list(t.get("lost_steps") or [])
        return any(m.get("mouse_mode") == "target" for m in self.moves() + steps)

    def target_pos(self):
        w = getattr(self, "_watcher", None)
        if w is None:
            return None
        if w.pos is not None and time.time() - getattr(w, "_last_hit", 0) <= 0.35:
            return w.pos
        try:
            ok, pos, _ = w.look()
        except Exception:
            return None
        if ok:
            w.pos, w._last_hit = pos, time.time()
            return pos
        return None

    def _target_step(self):
        w = self._watcher
        t = self.target()
        if not w.seen:
            if self._target_state == "fighting":
                self._target_state = "waiting"
                self.app.log("Target gone - stopped casting.")
                if t.get("lost_steps"):
                    self._sequence(self.play_steps, t["lost_steps"], "Target gone", lambda: True)
                self.app.log("Waiting for the target...")
            self._wait(max(0.05, float(t.get("poll", 0.25) or 0.25)))
            return False
        if self._target_state == "waiting":
            self._target_state = "fighting"
            self.app.log(f"Target '{t.get('creature')}' found at {w.pos}.")
            still_here = lambda: w.seen
            if t.get("found_steps"):
                self._sequence(self.play_steps, t["found_steps"], "Target found", still_here)
            if w.seen:
                self._wait(max(0.0, float(t.get("start_delay", 0.5) or 0)))
            return False
        return True

    def play_steps(self, steps, label, alive=lambda: True):
        go = lambda: self.running and alive()
        for num, step in enumerate(steps or [], start=1):
            if not go():
                return False
            self._aim(step.get("mouse_mode", "none"), step.get("x", 0), step.get("y", 0), step.get("aim_wait", 0.1))
            n = max(1, int(step.get("repeat", 1) or 1))
            for i in range(n):
                if not go():
                    return False
                wait = max(0.08, float(step.get("delay", 0) or 0))
                with RobloxInputDriver._lock:
                    self._press(step.get("key", ""))
                self.app.log(f"{label}: step {num} pressed {step.get('key', '')}" + (f" ({i + 1}/{n})" if n > 1 else ""))
                end = time.time() + wait
                while go() and time.time() < end:
                    time.sleep(0.02)
                if self.migrate_click(step).get("click") and go():
                    self._click(step.get("click_btn", "m2"))
                    self._wait(max(0.02, float(step.get("after_click", 0.1) or 0)))
        return True

    def moves(self):
        rot = self.cfg["rotation"]
        moves = rot["moves"]
        n = max(1, min(10, int(rot["slot_count"])))
        rot["slot_count"] = n
        while len(moves) < n:
            m = dict(DEFAULT_MOVE)
            m["key"] = str((len(moves) + 1) % 10)
            m["priority"] = len(moves) + 1
            moves.append(m)
        for m in moves:
            if "delay_before" not in m:
                m["delay_before"] = float(m.get("aim_wait", 0.1)) if m.get("mouse_mode", "none") != "none" else 0.0
                m["delay_after"] = float(m.get("anim") or 0)
            self.migrate_click(m)
            for old in ("aim_wait", "anim", "require_slot", "require_count"):
                m.pop(old, None)
            for k, v in DEFAULT_MOVE.items():
                m.setdefault(k, v)
        return moves[:n]

    def slot_cells(self):
        x1, y1, x2, y2 = self.cfg["rotation"]["region"]
        n = max(1, min(10, int(self.cfg["rotation"]["slot_count"])))
        if x2 - x1 < n or y2 <= y1:
            return []
        w = (x2 - x1) / n
        return [[int(x1 + i * w), y1, int(x1 + (i + 1) * w), y2] for i in range(n)]

    def clear_drawn_boxes(self, save=True):
        for m in self.cfg["rotation"].get("moves", []):
            m["box"] = None
        self._templates.clear()
        if save:
            self.app.settings.save()

    CENTER_X, CENTER_TOP, CENTER_BOTTOM = 0.15, 0.22, 0.12

    @classmethod
    def center_of(cls, box):
        x1, y1, x2, y2 = box
        w, h = x2 - x1, y2 - y1
        return [int(x1 + w * cls.CENTER_X), int(y1 + h * cls.CENTER_TOP),
                int(x2 - w * cls.CENTER_X), int(y2 - h * cls.CENTER_BOTTOM)]

    def _full_boxes(self):
        rot = self.cfg["rotation"]
        found = rot.get("slot_boxes") if rot.get("slot_boxes_for") == list(rot["region"]) else None
        out = []
        for i, (cx1, cy1, cx2, cy2) in enumerate(self.slot_cells()):
            if found and i < len(found):
                out.append([int(v) for v in found[i]])
            else:
                side = min(cx2 - cx1, cy2 - cy1)
                mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
                out.append([mx - side // 2, my - side // 2, mx - side // 2 + side, my - side // 2 + side])
        return out

    def slot_regions(self):
        cells = self.slot_cells()
        if not cells:
            return []
        rot = self.cfg["rotation"]
        found = rot.get("slot_boxes") if rot.get("slot_boxes_for") == list(rot["region"]) else None
        moves = rot.get("moves", [])
        out = []
        for i, (cx1, cy1, cx2, cy2) in enumerate(cells):
            own = moves[i].get("box") if i < len(moves) else None
            if own and own[2] > own[0] and own[3] > own[1]:
                out.append([int(v) for v in own])
            elif found and i < len(found):
                out.append(self.center_of([int(v) for v in found[i]]))
            else:
                side = min(cx2 - cx1, cy2 - cy1)
                mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
                out.append(self.center_of([mx - side // 2, my - side // 2, mx - side // 2 + side, my - side // 2 + side]))
        return out

    @staticmethod
    def inner_box(img):
        try:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mask = cv2.inRange(g, 30, 62)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            n, _, st, _ = cv2.connectedComponentsWithStats(mask)
            if n <= 1:
                return None
            i = 1 + int(np.argmax(st[1:, 4]))
            x, y, w, h, a = (int(v) for v in st[i])
            H, W = g.shape
            if w < W * 0.45 or h < H * 0.45 or a < w * h * 0.4:
                return None
            m = 2
            x, y = max(0, x - m), max(0, y - m)
            return x, y, min(W - x, w + 2 * m), min(H - y, h + 2 * m)
        except Exception:
            return None

    def capture_templates(self, slots=None):
        regions = self.slot_regions()
        if not regions:
            return 0
        rot = self.cfg["rotation"]
        if rot.get("slot_boxes_for") != list(rot["region"]):
            rot["slot_boxes"], rot["slot_boxes_for"] = self._full_boxes(), list(rot["region"])
        boxes = rot["slot_boxes"]
        full = self._full_boxes()
        while len(boxes) < len(regions):
            boxes.append(list(full[len(boxes)]))
        moves = rot.get("moves", [])
        os.makedirs(loadout_dir(self.active_loadout()), exist_ok=True)
        x1, y1, x2, y2 = rot["region"]
        bar1 = self.utils.capture_screen_bgr([x1, y1, x2, y2])
        time.sleep(0.3)
        bar2 = self.utils.capture_screen_bgr([x1, y1, x2, y2])
        done = 0
        for i, r in enumerate(regions, start=1):
            if slots and i not in slots:
                continue
            own = i - 1 < len(moves) and moves[i - 1].get("box")
            if not own:
                cell = self.slot_cells()[i - 1]
                full = self.utils.capture_screen_bgr(cell)
                b = self.inner_box(full) if full is not None and full.size else None
                if b:
                    x, y, w, h = b
                    full_box = [cell[0] + x, cell[1] + y, cell[0] + x + w, cell[1] + y + h]
                    boxes[i - 1] = list(full_box)
                    r = self.center_of(full_box)
            img = self.utils.capture_screen_bgr(r)
            if img is not None and img.size:
                if (bar1 is not None and bar2 is not None and x1 <= r[0] and r[2] <= x2 and y1 <= r[1] and r[3] <= y2
                        and self.changed(bar1[r[1] - y1:r[3] - y1, r[0] - x1:r[2] - x1],
                                         bar2[r[1] - y1:r[3] - y1, r[0] - x1:r[2] - x1])):
                    self.app.log(f"Slot {i}: it's still counting down - retake its snapshot once it's ready.")
                cv2.imwrite(self.template_path(i), img)
                if i - 1 < len(moves):
                    moves[i - 1]["snap_center"] = not own
                done += 1
        self._templates.clear()
        self.app.settings.save()
        return done

    def has_template(self, slot):
        return os.path.exists(self.template_path(slot))

    def _template(self, slot):
        if slot not in self._templates:
            img = cv2.imread(self.template_path(slot)) if self.has_template(slot) else None
            moves = self.cfg["rotation"].get("moves", [])
            m = moves[slot - 1] if 0 < slot <= len(moves) else {}
            if img is not None and not m.get("box") and not m.get("snap_center"):
                full = self._full_boxes()
                h, w = img.shape[:2]
                if 0 < slot <= len(full):
                    fw, fh = full[slot - 1][2] - full[slot - 1][0], full[slot - 1][3] - full[slot - 1][1]
                    if fh > 0 and w > h * fw / fh * 1.15:
                        keep = max(1, int(h * fw / fh))
                        img = img[:, (w - keep) // 2:(w - keep) // 2 + keep]
                        h, w = img.shape[:2]
                x1, y1, x2, y2 = self.center_of([0, 0, w, h])
                img = img[y1:y2, x1:x2]
            self._templates[slot] = img
        return self._templates[slot]

    def slot_score(self, slot, frame, around=None):
        if around is not None:
            v = self.search(around, self._template(slot))
            if v is not None:
                return v
        return self.compare(frame, self._template(slot))

    SCALES = (1.0, 0.9, 1.1, 0.8, 1.25)

    @staticmethod
    def search(area, tpl):
        if tpl is None or area is None or not area.size:
            return None
        a = cv2.GaussianBlur(cv2.cvtColor(area, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        b0 = cv2.GaussianBlur(cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        best = None
        for sc in SmartMacroLogic.SCALES:
            b = b0 if sc == 1.0 else cv2.resize(b0, None, fx=sc, fy=sc)
            h, w = b.shape
            if h > a.shape[0] or w > a.shape[1] or b.std() <= 1:
                continue
            res = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
            _, corr, _, (x, y) = cv2.minMaxLoc(res)
            if best is None or corr > best[0]:
                best = (float(corr), a[y:y + h, x:x + w], b)
        if best is None:
            return None
        corr, win, b = best
        bright = 1.0 - min(1.0, abs(win.mean() - b.mean()) / max(b.mean(), 1.0))
        return min(corr, bright)

    @staticmethod
    def compare(frame, tpl):
        if tpl is None or frame is None or not frame.size:
            return None
        if frame.shape[:2] != tpl.shape[:2]:
            frame = cv2.resize(frame, (tpl.shape[1], tpl.shape[0]))
        a = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        b = cv2.GaussianBlur(cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        h, w = b.shape
        my, mx = max(1, h // 12), max(1, w // 12)
        inner = b[my:h - my, mx:w - mx]
        if inner.size and inner.std() > 1:
            corr = float(cv2.matchTemplate(a, inner, cv2.TM_CCOEFF_NORMED).max())
        else:
            corr = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0][0])
        bright = 1.0 - min(1.0, abs(a.mean() - b.mean()) / max(b.mean(), 1.0))
        return min(corr, bright)

    @staticmethod
    def _slot_row(boxes, bottom_aligned):
        best = []
        for b in boxes:
            ref = b[1] + b[3] if bottom_aligned else b[1] + b[3] / 2
            row = sorted(o for o in boxes
                         if abs((o[1] + o[3] if bottom_aligned else o[1] + o[3] / 2) - ref) < max(6, b[3] * 0.2)
                         and abs(o[2] - b[2]) < b[2] * 0.25)
            ded = []
            for o in row:
                if not ded or o[0] - ded[-1][0] > o[2] * 0.5:
                    ded.append(o)
            if len(ded) >= 3:
                gaps = np.diff([o[0] for o in ded])
                if gaps.min() > b[2] * 0.8 and gaps.std() < gaps.mean() * 0.15 and len(ded) > len(best):
                    best = ded
        return best

    @classmethod
    def find_hotbar_slots(cls, img_bgr):
        H, W = img_bgr.shape[:2]
        y0 = int(H * 0.55)
        gray = cv2.cvtColor(img_bgr[y0:], cv2.COLOR_BGR2GRAY)
        best = []
        for lo, hi in ((30, 62), (34, 56)):
            _, _, stats, _ = cv2.connectedComponentsWithStats(cv2.inRange(gray, lo, hi), connectivity=4)
            boxes = [(int(x), int(y) + y0, int(w), int(h)) for x, y, w, h, _ in stats[1:]
                     if W * 0.025 <= w <= W * 0.09 and 0.6 <= w / h <= 1.6]
            row = cls._slot_row(boxes, bottom_aligned=True)
            if len(row) > len(best):
                pad = lambda b: (b[0] - max(1, round(b[2] * 0.05)), b[1] - max(1, round(b[3] * 0.05)),
                                 b[2] + 2 * max(1, round(b[2] * 0.05)), b[3] + 2 * max(1, round(b[3] * 0.05)))
                best = [pad(b) for b in row]
        for t in (22, 28, 34):
            mask = cv2.morphologyEx(cv2.inRange(gray, t, 255), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
            boxes = [(int(x), int(y) + y0, int(w), int(h)) for x, y, w, h, _ in stats[1:]
                     if W * 0.025 <= w <= W * 0.09 and 0.6 <= w / h <= 1.5]
            row = cls._slot_row(boxes, bottom_aligned=True)
            if len(row) > len(best):
                best = row
        if len(best) < 3:
            edges = cv2.dilate(cv2.Canny(gray, 40, 120), np.ones((3, 3), np.uint8))
            cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            boxes = []
            for c in cnts:
                x, y, w, h = cv2.boundingRect(c)
                if W * 0.02 <= w <= W * 0.09 and 0.75 <= w / h <= 1.3:
                    boxes.append((x, y + y0, w, h))
            best = cls._slot_row(boxes, bottom_aligned=False)
        if not best:
            return []
        side = int(np.median([b[2] for b in best]))
        bottom = int(np.median([b[1] + b[3] for b in best]))
        out = []
        for x, _, w, _ in best:
            y = bottom - side
            inner = cv2.cvtColor(img_bgr[y + side // 5:y + side * 4 // 5, x + w // 5:x + w * 4 // 5],
                                 cv2.COLOR_BGR2GRAY)
            out.append((x, y, w, side, bool(inner.size and inner.std() > 10)))
        return out

    def auto_find_hotbar(self):
        try:
            import pywinctl
            win = pywinctl.getActiveWindow()
        except Exception:
            win = None
        if not win or not is_roblox_title(win.title):
            self.app.log("Auto-find: click into the Roblox window first.")
            return None
        reg = [win.left, win.top, win.left + win.width, win.top + win.height]
        img = self.utils.capture_screen_bgr(reg)
        slots = self.find_hotbar_slots(img) if img is not None else []
        if not slots:
            self.app.log("Auto-find: couldn't see the hotbar - set it with Hotbar region instead.")
            return None
        filled = max((i for i, s in enumerate(slots, start=1) if s[4]), default=0)
        if not filled:
            self.app.log("Auto-find: the hotbar looks empty.")
            return None
        n = min(10, filled)
        pitch = (slots[-1][0] - slots[0][0]) / max(1, len(slots) - 1) if len(slots) > 1 else slots[0][2]
        x1 = reg[0] + slots[0][0] - (pitch - slots[0][2]) / 2
        top = reg[1] + min(s[1] for s in slots[:n])
        bottom = reg[1] + max(s[1] + s[3] for s in slots[:n])
        rot = self.cfg["rotation"]
        rot["region"] = [int(x1), int(top), int(x1 + pitch * n), int(bottom)]
        rot["slot_count"] = n
        rot["slot_boxes"] = [[reg[0] + x, reg[1] + y, reg[0] + x + w, reg[1] + y + h] for x, y, w, h, _ in slots[:n]]
        rot["slot_boxes_for"] = list(rot["region"])
        self.clear_drawn_boxes(save=False)
        self.moves()
        self.app.settings.save()
        self.app.log(f"Auto-find: hotbar found ({len(slots)} slots, using the {n} filled one(s)).")
        return n, len(slots)

    def slot_threshold(self, slot):
        moves = self.moves()
        own = float(moves[slot - 1].get("ready_at") or 0) if 0 < slot <= len(moves) else 0
        return own if own > 0 else float(self.cfg["rotation"]["threshold"])

    def slot_image(self, slot):
        regions = self.slot_regions()
        if not 0 < slot <= len(regions):
            return None
        return self.utils.capture_screen_bgr(regions[slot - 1])

    def wait_until_ready(self, slot, alive, timeout=60.0):
        end = time.time() + timeout
        prev = self.slot_image(slot)
        while alive() and time.time() < end:
            time.sleep(1.0)
            cur = self.slot_image(slot)
            score = self.compare(cur, prev)
            if score is not None and score >= 0.97:
                return cur
            prev = cur
        return None

    def auto_tune(self, slots=None, alive=lambda: True):
        results = {}
        if not self.slot_regions():
            return results
        os.makedirs(loadout_dir(self.active_loadout()), exist_ok=True)

        def sample(slot, n, gap):
            vals = []
            for _ in range(n):
                v = self.slot_score(slot, self.slot_image(slot))
                if v is not None:
                    vals.append(v)
                time.sleep(gap)
            return vals

        for slot, m in enumerate(self.moves(), start=1):
            if slots and slot not in slots:
                continue
            if not alive():
                break
            name = m["name"] or f"slot {slot}"
            if not m["key"]:
                results[slot] = ("skip", "no key")
                continue
            self.app.log(f"Auto-tune {name}: waiting for it to be ready…")
            ready_img = self.wait_until_ready(slot, alive)
            if ready_img is None:
                results[slot] = ("busy", "never stopped changing")
                self.app.log(f"Auto-tune {name}: its icon never stopped changing (animated?) - set 'Ready at' by hand")
                continue
            cv2.imwrite(self.template_path(slot), ready_img)
            self._templates.pop(slot, None)
            ready = sample(slot, 6, 0.1)
            lo = min(ready) if ready else 0.0
            with RobloxInputDriver._lock:
                self._press(m["key"])
            time.sleep(max(0.6, float(self.cfg["rotation"]["cast_delay"])))
            cd = sample(slot, 5, 0.1)
            hi = max(cd) if cd else lo
            if lo - hi < 0.06:
                results[slot] = ("same", f"ready {lo:.2f} / after cast {hi:.2f}")
                self.app.log(f"Auto-tune {name}: nothing changed after pressing {m['key']} - did it cast? "
                             "(no target / wrong key?) Give it a manual Cooldown instead")
                continue
            thr = round(hi + (lo - hi) * 0.5, 2)
            m["ready_at"] = thr
            results[slot] = ("ok", f"ready {lo:.2f} / cd {hi:.2f} → {thr:.2f}")
            self.app.log(f"Auto-tune {name}: ready {lo:.2f}, cooldown {hi:.2f} → Ready at {thr:.2f}")
        self.app.settings.save()
        return results

    def read_slots(self):
        regions = self.slot_regions()
        if not regions:
            return {}
        pad = max(8, int(max(r[2] - r[0] for r in regions) * 0.4))
        x1 = max(0, min(r[0] for r in regions) - pad); y1 = max(0, min(r[1] for r in regions) - pad)
        x2 = max(r[2] for r in regions) + pad; y2 = max(r[3] for r in regions) + pad
        bar = self.utils.capture_screen_bgr([x1, y1, x2, y2])
        out = {}
        for i, r in enumerate(regions, start=1):
            crop = around = None
            if bar is not None:
                crop = bar[r[1] - y1:r[3] - y1, r[0] - x1:r[2] - x1]
                around = bar[max(0, r[1] - pad - y1):r[3] + pad - y1, max(0, r[0] - pad - x1):r[2] + pad - x1]
            out[i] = self.slot_score(i, crop, around)
            self._track_still(i, crop)
        self._check_hotbar_moved(out)
        return out

    def _check_hotbar_moved(self, scores):
        vals = [v for v in scores.values() if v is not None]
        if not vals or max(vals) >= 0.3:
            self._lost_since = None
            return
        now = time.time()
        if getattr(self, "_lost_since", None) is None:
            self._lost_since = now
        elif now - self._lost_since > 10 and now - getattr(self, "_lost_warned", 0) > 120:
            self._lost_warned = now
            self.app.log("None of the slots look like their snapshots - the hotbar moved or changed size "
                         "(window size / display scaling?). Press Auto find hotbar, then retake the snapshots.")

    STILL_READY = 2.5

    @staticmethod
    def changed(a, b):
        if a is None or b is None or a.shape != b.shape or not a.size:
            return True
        d = cv2.absdiff(cv2.GaussianBlur(a, (3, 3), 0), cv2.GaussianBlur(b, (3, 3), 0)).max(axis=2)
        return float((d > 40).mean()) > 0.003

    def _track_still(self, slot, crop):
        prev = self._still.get(slot)
        if crop is None or not crop.size:
            self._still.pop(slot, None)
        elif prev is None or self.changed(crop, prev[0]):
            self._still[slot] = (crop.copy(), time.time())

    def still_for(self, slot):
        prev = self._still.get(slot)
        return time.time() - prev[1] if prev else 0.0

    def is_ready(self, slot, move, scores):
        score = scores.get(slot)
        if score is not None:
            if score >= self.slot_threshold(slot):
                return True
            if self.still_for(slot) >= self.STILL_READY:
                if time.time() - self._still_warned.get(slot, 0) > 120:
                    self._still_warned[slot] = time.time()
                    self.app.log(f"{move['name'] or 'Slot ' + str(slot)}: doesn't match its snapshot but isn't "
                                 "counting down - treating it as ready. Retake its snapshot while it's ready.")
                return True
            return False
        cd = float(move["cooldown"] or 0)
        return cd > 0 and time.time() - self.last_cast.get(slot, 0) >= cd

    def toggle(self):
        self.stop() if self.running else self.start()

    def _warn_if_roblox_admin(self):
        from utils import roblox_admin_problem
        msg = roblox_admin_problem()
        if not msg:
            return
        self.app.log("Roblox is running as administrator - the macro's keys can't reach it.")
        try:
            from tkinter import messagebox
            self.app.root.after(0, lambda: messagebox.showwarning("Roblox runs as administrator", msg,
                                                                  parent=self.app.root))
        except Exception:
            pass

    def start(self):
        if self.running:
            return
        old = [t for t in getattr(self, "_threads", []) if t.is_alive() and t is not threading.current_thread()]
        if old:
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
                else:
                    self.start()
            threading.Thread(target=later, daemon=True).start()
            return
        self.running = True
        self._last_shake = self._last_mana_skin = self._last_reset_lag = 0
        ok = self._popup_logic()
        if ok is not None:
            ok.popup_up = False
        threading.Thread(target=self._warn_if_roblox_admin, daemon=True).start()
        from utils import foreground_roblox, roblox_windows
        self._roblox_hwnd = foreground_roblox() or next((h for h, _ in roblox_windows()), 0)
        cfg = self.cfg
        self._threads = []
        parts = []
        self._watcher = None
        if self.target_on() or self.aims_at_target():
            self._watcher = self.make_watcher()
            self._watcher.start()
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
        self._spawn(self._ok_loop)
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
        try:
            from utils import release_all_keys
            release_all_keys()
        except Exception:
            pass
        self.app.log("Stopped")
        self.app.on_state_change(False)

    def _ok_loop(self):
        ok = getattr(getattr(self.app, "ok_page", None), "logic", None)
        if ok is None:
            return
        while self.running:
            self._wait_not_busy()
            took = 0.0
            if ok._ok_scanner_lock.acquire(blocking=False):
                t0 = time.perf_counter()
                try:
                    ok.handle_ok_popup()
                except Exception as e:
                    self.app.log(f"OK check error: {e}")
                finally:
                    ok._ok_scanner_lock.release()
                took = time.perf_counter() - t0
            end = time.perf_counter() + ok._ok_wait(took)
            while time.perf_counter() < end:
                if not self.running:
                    return
                time.sleep(0.25)

    def _sequence(self, fn, *a):
        busy = self.__dict__.setdefault("_busy", threading.Event())
        busy.set()
        try:
            return fn(*a)
        finally:
            busy.clear()

    def _wait_not_busy(self):
        busy = self.__dict__.get("_busy")
        while self.running and busy is not None and busy.is_set():
            time.sleep(0.1)

    def _spawn(self, fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        self._threads = [x for x in self._threads if x.is_alive()] + [t]

    def _focused(self):
        if not self.cfg.get("only_when_focused", True):
            return True
        try:
            w = pywinctl.getActiveWindow()
            if w and is_roblox_title(w.title):
                return True
        except Exception:
            return True
        if self.running and self.app.settings.get("force_roblox_focus", True)                 and time.time() - getattr(self, "_focus_try", 0) > 2.0:
            self._focus_try = time.time()
            from utils import focus_roblox
            if focus_roblox(getattr(self, "_roblox_hwnd", 0)):
                self.app.log("Brought Roblox back to the front.")
                return True
        return False

    def _wait(self, seconds):
        end = time.time() + seconds
        while self.running and time.time() < end:
            time.sleep(min(0.02, max(0.0, end - time.time())))
        return self.running

    @staticmethod
    def migrate_click(d):
        if "click" not in d:
            d["click"] = float(d.get("hold_click") or 0) > 0 or d.get("mouse_mode") == "click"
        if d.get("mouse_mode") == "click":
            d["mouse_mode"] = "move"
        d.pop("hold_click", None)
        d.setdefault("click_btn", "m2")
        if not d.get("m1_v2"):
            if float(d.get("m1_delay", 0.15) or 0) == 0.15:
                d["m1_delay"] = 0.3
            d["m1_v2"] = True
        return d

    def _aim(self, mode, x, y, wait=0.1):
        if mode == "target":
            pos = self.target_pos()
            if pos is None:
                if time.time() - getattr(self, "_no_target_logged", 0) > 10:
                    self._no_target_logged = time.time()
                    self.app.log("Aim at target: no target on screen - casting where the mouse is.")
                return
            RobloxInputDriver.glide_to(int(pos[0]), int(pos[1]))
        elif mode in ("move", "click"):
            RobloxInputDriver.glide_to(int(x), int(y))
        else:
            return
        if wait:
            self._wait(float(wait))

    def _m1_after(self, d):
        if self.migrate_click(d).get("click"):
            time.sleep(max(0.0, float(d.get("m1_delay", 0.3) or 0)))
            self._click(d.get("click_btn", "m2"))
            time.sleep(max(0.0, float(d.get("after_click", 0.1) or 0)))

    @staticmethod
    def click_name(d):
        return "M1" if d.get("click_btn", "m2") == "m1" else "M2"

    def _click(self, btn="m1"):
        button = Button.right if btn == "m2" else Button.left
        mouse = MouseController()
        with RobloxInputDriver._lock:
            mouse.press(button)
            time.sleep(0.04)
            mouse.release(button)

    def use_item(self, item):
        with RobloxInputDriver._lock:
            self._press(item["key"])
            if item.get("click", True):
                time.sleep(max(0.05, float(item.get("click_delay", 0.3) or 0.3)))
                self._click()
        self.app.log(f"Item '{item['name']}' seen -> pressed {item['key']}" + (" + M1" if item.get("click", True) else ""))

    def _press(self, key):
        if not key:
            return
        keys = [k.strip() for k in str(key).split("+") if k.strip()] if len(str(key)) > 1 else [key]
        if len(keys) < 2:
            self.utils.send_key(keys[0] if keys else key, 0.04)
            return
        from utils import press_key
        held = []
        try:
            for k in keys[:-1]:
                press_key(k, True)
                held.append(k)
                time.sleep(0.05)
            self.utils.send_key(keys[-1], 0.05)
            time.sleep(0.05)
        finally:
            for k in reversed(held):
                press_key(k, False)

    def anti_shake(self):
        d = self.cfg["rotation"].setdefault("anti_shake", {})
        for k, v in ANTI_SHAKE_DEFAULT.items():
            d.setdefault(k, v)
        return d

    def mana_skin(self):
        d = self.cfg["rotation"].setdefault("mana_skin", {})
        for k, v in MANA_SKIN_DEFAULT.items():
            d.setdefault(k, v)
        return d

    def _ctrl_t(self):
        from utils import scan_key
        with RobloxInputDriver._lock:
            scan_key(0x1D, True)
            time.sleep(0.05)
            self._press("t")
            time.sleep(0.05)
            scan_key(0x1D, False)

    def do_mana_skin(self):
        d = self.mana_skin()
        self.app.log("Mana skin: Ctrl+T")
        self._ctrl_t()
        self._wait(max(0.0, float(d.get("between", 1.0) or 0)))
        self._ctrl_t()
        self._wait(0.5)
        self._last_mana_skin = time.time()

    def reset_lag(self):
        d = self.cfg["rotation"].setdefault("reset_lag", {})
        for k, v in RESET_LAG_DEFAULT.items():
            d.setdefault(k, v)
        return d

    def _roblox_region(self):
        try:
            w = pywinctl.getActiveWindow()
            if w and is_roblox_title(w.title):
                return [w.left, w.top, w.left + w.width, w.top + w.height]
        except Exception:
            pass
        return None

    def capture_reset_lag_button(self, region):
        img = self.utils.capture_screen_bgr(region)
        if img is None or img.size == 0 or min(img.shape[:2]) < 6:
            return False
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        return cv2.imwrite(RESET_LAG_PIC, img)

    def find_reset_lag_button(self):
        reg = self._roblox_region()
        tpl = cv2.imread(RESET_LAG_PIC) if os.path.exists(RESET_LAG_PIC) else None
        if reg is None or tpl is None:
            return None
        img = self.utils.capture_screen_bgr(reg)
        if img is None or img.shape[0] < tpl.shape[0] or img.shape[1] < tpl.shape[1]:
            return None
        res = cv2.matchTemplate(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY),
                                cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(res)
        return (reg[0] + x + tpl.shape[1] // 2, reg[1] + y + tpl.shape[0] // 2) if score >= 0.8 else None

    def find_reset_lag_text(self):
        want = self._norm(self.reset_lag().get("text") or "Main Menu")
        reg = self._roblox_region()
        if not want or reg is None:
            return None
        for box, text, conf in self.utils.get_text_from_region(reg, upscale=1):
            if want in self._norm(text):
                return (int(reg[0] + sum(p[0] for p in box) / 4), int(reg[1] + sum(p[1] for p in box) / 4))
        return None

    def _wait_any(self, seconds):
        end = time.time() + seconds
        while time.time() < end and self._reset_lag_alive():
            time.sleep(0.05)

    def _reset_lag_alive(self):
        return self.running or getattr(self, "_testing_reset_lag", False)

    def _find_for(self, find, seconds=3.0):
        end = time.time() + seconds
        while time.time() < end and self._reset_lag_alive():
            hit = find()
            if hit:
                return hit
            time.sleep(0.25)
        return None

    def do_reset_lag(self):
        d = self.reset_lag()
        wait = max(0.0, float(d.get("wait", 1.0) or 0))
        self._last_reset_lag = time.time()
        self.app.log("Reset lag: opening the menu...")
        hit = self._find_for(self.find_reset_lag_button)
        if not self._reset_lag_alive():
            return False
        if not hit:
            self.app.log("Reset lag: menu button not found (capture it on the Rotation page) - skipped.")
            return False
        RobloxInputDriver.glide_click(*hit)
        self._wait_any(wait)
        hit = self._find_for(self.find_reset_lag_text)
        if not self._reset_lag_alive():
            return False
        if not hit:
            self.app.log(f"Reset lag: '{d.get('text') or 'Main Menu'}' not found - skipped.")
            return False
        RobloxInputDriver.glide_click(*hit)
        self._wait_any(wait)
        ok = getattr(getattr(self.app, "ok_page", None), "logic", None)
        end = time.time() + 10.0
        while ok is not None and time.time() < end and self._reset_lag_alive():
            if ok.find_ok_button():
                if ok._ok_scanner_lock.acquire(timeout=5):
                    try:
                        ok.handle_ok_popup()
                    finally:
                        ok._ok_scanner_lock.release()
                self._wait_any(wait)
                hit = self._find_for(self.find_reset_lag_button)
                if hit and self._reset_lag_alive():
                    RobloxInputDriver.glide_click(*hit)
                    self.app.log("Reset lag: done (menu closed).")
                else:
                    self.app.log("Reset lag: done (menu button not found to close the menu).")
                return True
            time.sleep(0.25)
        self.app.log("Reset lag: the OK didn't show up (or the OK button isn't captured on the Pop Up page).")
        return False

    def do_anti_shake(self):
        d = self.anti_shake()
        key = (d.get("key") or ",").strip() or ","
        self.app.log(f"Anti screen-shake: pressing '{key}' (camera reset)")
        with RobloxInputDriver._lock:
            self._press(key)
        self._wait(max(0.0, float(d.get("between", 1.0) or 0)))
        with RobloxInputDriver._lock:
            self._press(key)
        self._wait(max(0.0, float(d.get("after", 0.5) or 0)))
        for _ in range(2):
            if self.anti_shake_back_to_normal() is not False:
                break
            self.app.log("Anti screen-shake: in skill tree - pressing ',' once more.")
            with RobloxInputDriver._lock:
                self._press(key)
            self._wait(max(0.5, float(d.get("after", 0.5) or 0)))
        self._last_shake = time.time()

    def save_anti_shake_ref(self):
        r = self.anti_shake().get("check_region") or [0, 0, 0, 0]
        if r[2] <= r[0] or r[3] <= r[1]:
            return False
        img = self.utils.capture_screen_bgr(r)
        if img is None or not img.size:
            return False
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        return bool(cv2.imwrite(ANTI_SHAKE_REF, img))

    def leave_skill_tree(self):
        if not self.anti_shake().get("enabled"):
            return False
        if time.time() - getattr(self, "_tree_check", 0) < 0.5:
            return False
        self._tree_check = time.time()
        if self.in_skill_tree() is not True:
            return False
        d = self.anti_shake()
        key = (d.get("key") or ",").strip() or ","
        self.app.log(f"Still in skill tree - pressing '{key}' before casting.")
        with RobloxInputDriver._lock:
            self._press(key)
        self._wait(max(0.5, float(d.get("after", 0.5) or 0)))
        return True

    def in_skill_tree(self):
        r = self.anti_shake().get("check_region") or [0, 0, 0, 0]
        if r[2] <= r[0] or r[3] <= r[1] or not os.path.exists(ANTI_SHAKE_REF):
            return None
        ref = cv2.imread(ANTI_SHAKE_REF)
        now = self.utils.capture_screen_bgr(r)
        if ref is None or now is None or not now.size:
            return None
        try:
            now = cv2.resize(now, (ref.shape[1], ref.shape[0]))
            diff = float(np.mean(np.abs(ref.astype(np.float32) - now.astype(np.float32))))
            if diff < 20 and self.popup_up(look=True):
                return None
            return diff < 20
        except Exception:
            return None

    def _popup_logic(self):
        return getattr(getattr(self.app, "ok_page", None), "logic", None)

    def popup_up(self, look=False):
        ok = self._popup_logic()
        if ok is None:
            return False
        if ok.ok_busy.is_set() or getattr(ok, "popup_up", False):
            return True
        if not look:
            return False
        try:
            return bool(ok.find_ok_button(fast=True) or ok.find_custom_popup(fast=True))
        except Exception:
            return False

    def anti_shake_back_to_normal(self):
        t = self.in_skill_tree()
        return None if t is None else not t

    def med(self):
        d = self.cfg["rotation"].setdefault("meditation", {})
        for k, v in MEDITATION_DEFAULT.items():
            d.setdefault(k, copy.deepcopy(v))
        return d

    def mana_reading(self):
        r = self.med()["region"]
        if not (r[2] > r[0] and r[3] > r[1]):
            return None
        img = self.utils.capture_screen_bgr(r)
        if img is None or not img.size:
            return None
        h = img.shape[0]
        band = cv2.cvtColor(img[int(h * 0.3):max(int(h * 0.3) + 1, int(h * 0.7))], cv2.COLOR_BGR2HSV)
        blue = ((band[:, :, 0] >= 95) & (band[:, :, 0] <= 112) & (band[:, :, 1] >= 70) & (band[:, :, 2] >= 140))
        cols = blue.mean(axis=0) >= 0.5
        n = len(cols)
        edge = max(1, n // 20)
        dim = ((band[:, :, 0] >= 95) & (band[:, :, 0] <= 112) & (band[:, :, 1] >= 70) & (band[:, :, 2] >= 35))
        grey = ((band[:, :, 1] < 60) & (band[:, :, 2] >= 15) & (band[:, :, 2] <= 150)).mean(axis=0) >= 0.5
        left_blue = cols[:edge].mean() >= 0.5
        if not left_blue:
            if (dim.mean(axis=0) >= 0.5)[:edge].mean() >= 0.5:
                return None
            if grey[:edge].mean() < 0.5:
                return None
        need = max(3, n // 50)
        fill, run = 0.0, 0
        for i, c in enumerate(cols.tolist() + [False]):
            if c:
                run += 1
            else:
                if run >= need or (run and i == run):
                    fill = i / n
                run = 0
        if left_blue and fill < 0.95:
            rest = grey[int(fill * n):]
            if rest.size and rest.mean() < 0.5:
                return None
        return fill, bool(left_blue), bool(cols[-edge:].mean() >= 0.5) or fill >= 0.97

    def mana_empty(self):
        r = self.mana_reading()
        if not r:
            return False
        below = max(0.0, float(self.med().get("below", 5) or 0)) / 100.0
        return (not r[1]) or r[0] <= below

    MANA_SLACK = 0.05
    MANA_LOOKS = 4

    def mana_really_low(self):
        if time.time() < getattr(self, "_mana_settle", 0):
            return False
        near = max(0.0, float(self.med().get("below", 5) or 0)) / 100.0 + self.MANA_SLACK
        for n in range(self.MANA_LOOKS + 1):
            if self.popup_up(look=True):
                self._mana_settle = time.time() + 1.0
                return False
            if n == self.MANA_LOOKS:
                break
            r = self.mana_reading()
            if r is None:
                return False
            if r[0] > near:
                if time.time() - getattr(self, "_mana_false_logged", 0) > 30:
                    self._mana_false_logged = time.time()
                    self.app.log(f"Mana read low, but it's really about {r[0] * 100:.0f}% - not meditating.")
                return False
            self._wait(0.3)
        return self.running

    def mana_full(self):
        r = self.mana_reading()
        return bool(r) and r[2]

    def meditation_steps(self):
        d = self.med()
        out = d.get("out", "weapon")
        away, back = [], []
        if out in ("weapon", "both"):
            away.append((d["weapon_key"], "store_weapon"))
        if out in ("grimoire", "both"):
            away.append((d["grimoire_key"], "store_grimoire"))
        if out in ("grimoire", "both"):
            back.append((d["grimoire_key"], "draw_grimoire"))
        if out in ("weapon", "both"):
            back.append((d["weapon_key"], "draw_weapon"))
        return {"away": away, "back": back}

    def med_wait(self, name):
        d = self.med()
        v = d.get("waits", {}).get(name)
        return max(0.0, float(v if v not in (None, "") else d.get("key_delay", 1.0)))

    def meditate(self):
        d = self.med()
        steps = self.meditation_steps()
        gap = lambda name: self.med_wait(name)
        self._same_slot, self._same_n = None, 0
        self.app.log("Mana empty → meditating…")
        self._wait(gap("start"))
        for k, name in steps["away"]:
            with RobloxInputDriver._lock:
                self._press(k)
            self._wait(gap(name))
        with RobloxInputDriver._lock:
            self._press(d["key"])
        self._wait(gap("sit"))
        busy = self.__dict__.get("_busy")
        if busy is not None:
            busy.clear()
        try:
            end = time.time() + float(d.get("max_wait", 90) or 90)
            best, best_t = 0.0, time.time()
            while self.running and time.time() < end and not self.mana_full():
                r = self.mana_reading()
                if r and r[0] > best + 0.005:
                    best, best_t = r[0], time.time()
                elif best >= 0.9 and time.time() - best_t > 4:
                    break
                self._wait(0.3)
        finally:
            if busy is not None:
                busy.set()
        if not self.running:
            return
        r = self.mana_reading()
        full = self.mana_full() or bool(r and r[0] >= 0.9)
        with RobloxInputDriver._lock:
            self._press(d["key"])
        self._wait(gap("stand"))
        for k, name in steps["back"]:
            if not self.running:
                return
            self.app.log(f"   taking out: {k.upper()}")
            with RobloxInputDriver._lock:
                self._press(k)
            self._wait(gap(name))
        self._same_slot, self._same_n = None, 0
        self.app.log("Mana full - back to the rotation." if full else
                     f"Meditation stopped after {int(float(d.get('max_wait', 90)))} s (mana didn't read as full).")

    def stuck_check(self, slot):
        d = self.med()
        limit = int(float(d.get("stuck_after", 20) or 0))
        if not d.get("enabled") or limit <= 0:
            return
        if slot != getattr(self, "_same_slot", None):
            self._same_slot, self._same_n = slot, 0
        self._same_n += 1
        if self._same_n < limit:
            return
        self._same_n = 0
        out = d.get("out", "weapon")
        keys = ([d["weapon_key"]] if out in ("weapon", "both") else []) +                ([d["grimoire_key"]] if out in ("grimoire", "both") else [])
        self.app.log(f"Same move {limit} times in a row - trying {' / '.join(k.upper() for k in keys)} one at a time.")
        for k in keys * 2:
            if not self.running:
                return
            with RobloxInputDriver._lock:
                self._press(k)
            self._wait(self.med_wait("stuck"))
            if self._casts_again(slot):
                self.app.log(f"   pressed {k.upper()} - casting works again.")
                return
            self.app.log(f"   pressed {k.upper()} - still not casting.")
        if not self._looks_seated():
            self.app.log("   still stuck, but it isn't meditating (mana isn't filling) - not pressing the "
                         f"meditation key ({d['key']}).")
            return
        self.app.log(f"   still stuck - pressing the meditation key ({d['key']}).")
        with RobloxInputDriver._lock:
            self._press(d["key"])
        self._wait(self.med_wait("stuck"))

    def _looks_seated(self):
        a = self.mana_reading()
        if a is None:
            return False
        self._wait(1.5)
        b = self.mana_reading()
        if b is None:
            return False
        return b[0] - a[0] >= 0.01 or (a[2] and b[2])

    def _casts_again(self, slot):
        moves = self.moves()
        if not 0 < slot <= len(moves) or not moves[slot - 1].get("key"):
            return False
        m = moves[slot - 1]
        with RobloxInputDriver._lock:
            self._press(m["key"])
        self._wait(max(float(m.get("delay_after") or 0), float(self.cfg["rotation"]["cast_delay"])))
        score = self.read_slots().get(slot)
        return score is not None and score < self.slot_threshold(slot)

    def pick_move(self, scores):
        best = None
        for slot, m in enumerate(self.moves(), start=1):
            if not m["enabled"] or not m["key"]:
                continue
            if not self.is_ready(slot, m, scores):
                continue
            if best is None or int(m["priority"]) < int(best[1]["priority"]):
                best = (slot, m)
        return best

    def timer_due_in(self, kind):
        d, last, unit = {"anti_shake": (self.anti_shake(), "_last_shake", 1),
                         "mana_skin": (self.mana_skin(), "_last_mana_skin", 1),
                         "reset_lag": (self.reset_lag(), "_last_reset_lag", 60)}[kind]
        if not self.running or not d.get("enabled"):
            return None
        default = 30 if kind == "anti_shake" else 0
        every = max(1.0, float(d.get("every") or default)) * unit
        since = getattr(self, last, 0)
        if not since:
            return every
        return max(0.0, every - (time.time() - since))

    def _rotation_loop(self):
        self.cast_count, self.last_cast, self._still = {}, {}, {}
        self._same_slot = None
        self._target_state = "waiting"
        if self.target_on() and getattr(self, "_watcher", None) is None:
            self._watcher = self.make_watcher()
            self._watcher.start()
        if self.target_on():
            self.app.log(f"Target on: waiting for '{self.target().get('creature')}' - nothing is cast until it's seen.")
        while self.running:
            try:
                rot = self.cfg["rotation"]
                if not self._focused():
                    self._wait(0.3); continue
                if self.med()["enabled"] and self.mana_empty() and self.mana_really_low():
                    self._sequence(self.meditate)
                    continue
                for d, last, run in ((self.mana_skin(), "_last_mana_skin", self.do_mana_skin),
                                     (self.reset_lag(), "_last_reset_lag", self.do_reset_lag)):
                    every = max(1.0, float(d.get("every") or 0)) * (60 if run == self.do_reset_lag else 1)
                    if d.get("enabled"):
                        if not getattr(self, last, 0):
                            setattr(self, last, time.time())
                        elif time.time() - getattr(self, last) >= every:
                            self._sequence(run)
                sh = self.anti_shake()
                if sh["enabled"]:
                    if not getattr(self, "_last_shake", 0):
                        self._last_shake = time.time()
                    elif time.time() - self._last_shake >= max(1.0, float(sh.get("every", 30) or 30)):
                        self._sequence(self.do_anti_shake)
                        continue
                if self.popup_up():
                    if not getattr(self, "_popup_wait_logged", False):
                        self.app.log("A pop up is on screen - waiting for it to be clicked before casting.")
                        self._popup_wait_logged = True
                    self._same_slot, self._same_n = None, 0
                    self._wait(0.2)
                    continue
                self._popup_wait_logged = False
                if self.leave_skill_tree():
                    continue
                if self.target_on() and getattr(self, "_watcher", None) is not None and not self._target_step():
                    self._same_slot, self._same_n = None, 0
                    continue
                pick = self.pick_move(self.read_slots())
                if not pick:
                    self._wait(float(rot["tick"])); continue
                slot, m = pick
                self._sequence(self.stuck_check, slot)
                for n in range(max(1, int(m["repeat"]))):
                    if not self.running:
                        return
                    with RobloxInputDriver._lock:
                        self._aim(m["mouse_mode"], m["x"], m["y"], 0)
                        self._wait(float(m.get("delay_before") or 0))
                        self._press(m["key"])
                        self._m1_after(m)
                    if n < int(m["repeat"]) - 1:
                        self._wait(max(0.05, float(m.get("repeat_delay") or 0.15)))
                self._wait(max(float(m.get("delay_after") or 0), float(rot["cast_delay"])))
                score = self.read_slots().get(slot)
                if score is not None and score >= self.slot_threshold(slot):
                    self.app.log(f"{m['name'] or 'Slot ' + str(slot)}: still ready, retrying")
                    continue
                self.last_cast[slot] = time.time()
                self._same_slot, self._same_n = None, 0
                self.cast_count[slot] = self.cast_count.get(slot, 0) + 1
                self.app.log(f"Cast {m['name'] or 'slot ' + str(slot)} [{m['key']}]")
            except Exception as e:
                self.app.log(f"Rotation error: {e}")
                self._wait(0.5)

    def _hook_combos(self):
        self._unhook_combos()
        for combo in self.cfg["combos"]["list"]:
            trig = (combo.get("trigger") or "").strip().lower()
            if not trig or not combo.get("enabled", True) or not combo.get("steps"):
                continue
            try:
                from utils import on_key
                h = on_key(trig, lambda e, c=combo: self._fire_combo(c),
                           suppress=not combo.get("passthrough", True))
                self._combo_hooks.append(h)
            except Exception as e:
                self.app.log(f"Combo hook error ({trig}): {e}")

    def _unhook_combos(self):
        from utils import remove_key
        for h in self._combo_hooks:
            remove_key(h)
        self._combo_hooks = []

    def _fire_combo(self, combo):
        if not self.running or not self._combo_busy.acquire(blocking=False):
            return
        threading.Thread(target=self._run_combo, args=(combo,), daemon=True).start()

    def _run_combo(self, combo):
        try:
            trig = (combo.get("trigger") or "").strip().lower()
            if not self._focused():
                self.app.log(f"Combo [{trig}]: skipped — Roblox isn't the focused window")
                return
            end = time.time() + 1.0
            while self.running and time.time() < end and keyboard.is_pressed(trig):
                time.sleep(0.01)
            time.sleep(0.03)
            self.play_steps(combo.get("steps", []), f"Combo [{trig}]")
        except Exception as e:
            self.app.log(f"Combo error: {e}")
        finally:
            time.sleep(0.05)
            self._combo_busy.release()

    @staticmethod
    def _norm(s):
        return "".join(ch for ch in s.lower() if ch.isalnum())

    def items_region(self):
        r = self.cfg["items"]["region"]
        return r if r[2] > r[0] and r[3] > r[1] else None

    def match_items(self, texts):
        hits = []
        for item in self.cfg["items"]["list"]:
            name = self._norm(item.get("name", ""))
            if not name or not item.get("key") or not item.get("enabled", True):
                continue
            for t in texts:
                t = self._norm(t)
                if name in t or difflib.SequenceMatcher(None, name, t).ratio() >= 0.8 or \
                        any(difflib.SequenceMatcher(None, name, t[i:i + len(name)]).ratio() >= 0.8
                            for i in range(0, max(1, len(t) - len(name) + 1))):
                    hits.append(item); break
        return hits

    def read_items(self):
        region = self.items_region()
        if not region:
            return []
        small = self.utils.capture_screen_bgr(region)
        prev = getattr(self, "_items_prev", None)
        if (prev is not None and small is not None and prev[0] is not None and prev[0].shape == small.shape
                and time.time() - prev[2] < 2.0 and float(cv2.absdiff(prev[0], small).mean()) < 2.0):
            return prev[1]
        res = self.utils.get_text_from_region(region)
        if self.utils.ocr_reader is False:
            self.app.log(self.utils.ocr_error or "Text reading (OCR) couldn't start.")
        texts = [text for _, text, conf in res if conf > 0.4]
        self._items_prev = (small, texts, time.time())
        return texts

    def _items_loop(self):
        showing, last_used = set(), {}
        while self.running:
            try:
                if not self._focused():
                    self._wait(0.3); continue
                self._wait_not_busy()
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
