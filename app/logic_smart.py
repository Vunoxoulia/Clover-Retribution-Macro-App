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
    "mouse_mode": "none", "x": 0, "y": 0, "click": False, "m1_delay": 0.3,
    # one cast:  move mouse -> delay_before -> press key -> M2/M1 click (if ticked) -> delay_after -> next move
    "click_btn": "m2",        # which mouse button 'then click' uses (Items always use M1)
    "after_click": 0.1,       # keep the mouse still this long after the click, so the cast lands where it was aimed
    "delay_before": 0.0, "delay_after": 0.0,
    "box": None,              # a box the user drew for this slot (), else the automatic one
    "ready_at": 0.0,          # this slot's own match level for READY (0 = use the global one); Auto-tune sets it
}

# Meditation: when the mana bar runs out, put the weapon / grimoire away, meditate until it's full, take them out again
MEDITATION_DEFAULT = {
    "enabled": False, "region": [0, 0, 0, 0],   # region = the light-blue mana bar
    "out": "weapon",                            # what you fight with: weapon / grimoire / both
    "weapon_key": "r", "grimoire_key": "g", "key": "n", "max_wait": 90,
    "below": 5,                                 # meditate once mana is at or under this % (5 = basically empty)
    "key_delay": 1.0,                           # 'All waits' - the default for every step below
    # each step's own wait (missing = key_delay): before the first key, after each key
    "waits": {},
}

# Anti screen-shake: every N seconds press ',' → wait → ',' (resets the camera lock) between casts
ANTI_SHAKE_DEFAULT = {"enabled": False, "every": 30, "key": ",", "between": 1.0, "after": 0.5,
                      "check_region": [0, 0, 0, 0]}   # optional screenshot check: a spot that looks different in ','
ANTI_SHAKE_REF = os.path.join(TEMPLATE_DIR, "anti_shake_normal.png")

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

    def _fill_section(self, k, v):
        """Put a loadout's section into the live config IN PLACE (same dict object), so every page that
        holds on to it (e.g. Settings → match strictness) keeps editing the live one, not a dropped copy."""
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
        for k, v in copy.deepcopy(self.loadouts()[name]).items():
            self._fill_section(k, v)
        self.app.settings.settings["skill_active_loadout"] = name
        self._templates.clear()
        self.app.settings.save()
        return True

    def new_loadout(self, name):
        """New loadout = a fresh, empty save (default settings, no snapshots), then switch to it.
        The current loadout is saved first and stays as it was."""
        if not name or name in self.loadouts():
            return False
        self._store_active()
        fresh = {k: copy.deepcopy(DEFAULT_SMART[k]) for k in LOADOUT_SECTIONS}
        self.loadouts()[name] = copy.deepcopy(fresh)
        for k, v in fresh.items():
            self._fill_section(k, v)
        dst = loadout_dir(name)
        if os.path.isdir(dst):                           # leftovers from an old loadout with this name
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
        if was_active:                               # load the next one without saving the deleted one
            first = next(iter(lo))
            for k, v in copy.deepcopy(lo[first]).items():
                self._fill_section(k, v)
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
            self.migrate_click(m)
            for old in ("aim_wait", "anim", "require_slot", "require_count"):
                m.pop(old, None)
            for k, v in DEFAULT_MOVE.items():
                m.setdefault(k, v)
        return moves[:n]

    def slot_cells(self):
        """The hotbar region cut into equal cells (one per slot) - includes the gaps between boxes."""
        x1, y1, x2, y2 = self.cfg["rotation"]["region"]
        n = max(1, min(10, int(self.cfg["rotation"]["slot_count"])))
        if x2 - x1 < n or y2 <= y1:
            return []
        w = (x2 - x1) / n
        return [[int(x1 + i * w), y1, int(x1 + (i + 1) * w), y2] for i in range(n)]

    def clear_drawn_boxes(self, save=True):
        """Forget every drawn box, so all slots use the automatic box again."""
        for m in self.cfg["rotation"].get("moves", []):
            m["box"] = None
        self._templates.clear()
        if save:
            self.app.settings.save()

    # Only the MIDDLE of a hotbar box is compared: its edges carry the gold / silver / bronze clovers of a
    # move that isn't maxed yet, and a new clover there would make a 'ready' slot look different.
    CENTER_X, CENTER_TOP, CENTER_BOTTOM = 0.15, 0.22, 0.12

    @classmethod
    def center_of(cls, box):
        x1, y1, x2, y2 = box
        w, h = x2 - x1, y2 - y1
        return [int(x1 + w * cls.CENTER_X), int(y1 + h * cls.CENTER_TOP),
                int(x2 - w * cls.CENTER_X), int(y2 - h * cls.CENTER_BOTTOM)]

    def _full_boxes(self):
        """Each slot's WHOLE automatic box (before taking its middle)."""
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
        """What each slot's picture is taken of - only the INSIDE of its hotbar box, not the gaps around it:
        1. a box you drew yourself for that slot (Draw box), else
        2. the exact box Find hotbar saw (while the hotbar region is still the one it set), else
        3. a square in the middle of the slot's cell."""
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

    # ---------- templates ----------
    @staticmethod
    def inner_box(img):
        """The hotbar box inside a slot picture: its dark fill (the same grey Find hotbar looks for),
        so the gaps / ground beside it are left out. Returns (x, y, w, h) or None when unsure."""
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
                return None                                   # no clear box (icon art, bright skill...)
            m = 2                                              # keep the box's own border
            x, y = max(0, x - m), max(0, y - m)
            return x, y, min(W - x, w + 2 * m), min(H - y, h + 2 * m)
        except Exception:
            return None

    def capture_templates(self, slots=None):
        """Snapshot the given slots (default: all) as their READY image - only the inside of each
        hotbar box. The box found is remembered so the live 'ready' check looks at the same spot."""
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
                    boxes[i - 1] = list(full_box)           # the whole box is remembered...
                    r = self.center_of(full_box)            # ...but only its middle is the snapshot
            img = self.utils.capture_screen_bgr(r)
            if img is not None and img.size:
                cv2.imwrite(self.template_path(i), img)
                if i - 1 < len(moves):
                    moves[i - 1]["snap_center"] = not own       # this snapshot is already just the middle
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
                # a snapshot from before 'middle only': first drop the gaps beside the box (very old ones
                # were the whole cell), then cut the middle out the same way new ones are - so it still matches
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

    def slot_score(self, slot, frame):
        return self.compare(frame, self._template(slot))

    @staticmethod
    def compare(frame, tpl):
        """How alike a slot picture is to a reference picture (1 = same)."""
        if tpl is None or frame is None or not frame.size:
            return None
        if frame.shape[:2] != tpl.shape[:2]:
            frame = cv2.resize(frame, (tpl.shape[1], tpl.shape[0]))
        # A light blur hides sparkles / glow animations that made some icons never match.
        a = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        b = cv2.GaussianBlur(cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
        # Normalised correlation catches layout (name text vs timer number). The snapshot's middle is
        # searched a few pixels around, so a hotbar box that's slightly off still matches.
        h, w = b.shape
        my, mx = max(1, h // 12), max(1, w // 12)
        inner = b[my:h - my, mx:w - mx]
        if inner.size and inner.std() > 1:
            corr = float(cv2.matchTemplate(a, inner, cv2.TM_CCOEFF_NORMED).max())
        else:
            corr = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0][0])
        # Mean brightness catches the darkened cooldown overlay.
        bright = 1.0 - min(1.0, abs(a.mean() - b.mean()) / max(b.mean(), 1.0))
        return min(corr, bright)

    # ---------- finding the hotbar by itself ----------
    @staticmethod
    def _slot_row(boxes, bottom_aligned):
        """The longest row of same-size, evenly spaced boxes."""
        best = []
        for b in boxes:
            ref = b[1] + b[3] if bottom_aligned else b[1] + b[3] / 2
            row = sorted(o for o in boxes
                         if abs((o[1] + o[3] if bottom_aligned else o[1] + o[3] / 2) - ref) < max(6, b[3] * 0.2)
                         and abs(o[2] - b[2]) < b[2] * 0.25)
            ded = []
            for o in row:                                 # one box per slot (contours can repeat)
                if not ded or o[0] - ded[-1][0] > o[2] * 0.5:
                    ded.append(o)
            if len(ded) >= 3:
                gaps = np.diff([o[0] for o in ded])
                if gaps.min() > b[2] * 0.8 and gaps.std() < gaps.mean() * 0.15 and len(ded) > len(best):
                    best = ded
        return best

    @classmethod
    def find_hotbar_slots(cls, img_bgr):
        """The hotbar = the longest row of same-size, evenly spaced square slots in the lower part
        of the window. Returns [(x, y, w, h, filled)] left to right (image coords) or []."""
        H, W = img_bgr.shape[:2]
        y0 = int(H * 0.55)
        gray = cv2.cvtColor(img_bgr[y0:], cv2.COLOR_BGR2GRAY)
        best = []
        # 0. The flat dark-grey fill inside each slot (works whatever is behind the hotbar: black bar,
        #    bright floor...). The fill surrounds the move's name, so each slot is one blob; pad it out to the frame.
        for lo, hi in ((30, 62), (34, 56)):
            _, _, stats, _ = cv2.connectedComponentsWithStats(cv2.inRange(gray, lo, hi), connectivity=4)
            boxes = [(int(x), int(y) + y0, int(w), int(h)) for x, y, w, h, _ in stats[1:]
                     if W * 0.025 <= w <= W * 0.09 and 0.6 <= w / h <= 1.6]
            row = cls._slot_row(boxes, bottom_aligned=True)
            if len(row) > len(best):
                pad = lambda b: (b[0] - max(1, round(b[2] * 0.05)), b[1] - max(1, round(b[3] * 0.05)),
                                 b[2] + 2 * max(1, round(b[2] * 0.05)), b[3] + 2 * max(1, round(b[3] * 0.05)))
                best = [pad(b) for b in row]
        # 1. Slots are dark grey on a near-black bar: anything not near-black, split by the black gaps.
        #    Works at any window size (small windows blur the slot outlines into the text).
        for t in (22, 28, 34):
            mask = cv2.morphologyEx(cv2.inRange(gray, t, 255), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
            boxes = [(int(x), int(y) + y0, int(w), int(h)) for x, y, w, h, _ in stats[1:]
                     if W * 0.025 <= w <= W * 0.09 and 0.6 <= w / h <= 1.5]
            row = cls._slot_row(boxes, bottom_aligned=True)   # crowns on filled slots make them taller
            if len(row) > len(best):
                best = row
        # 2. Fallback: slot outlines (edges)
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
            y = bottom - side                            # square, from the bottom (skips the crowns)
            inner = cv2.cvtColor(img_bgr[y + side // 5:y + side * 4 // 5, x + w // 5:x + w * 4 // 5],
                                 cv2.COLOR_BGR2GRAY)
            out.append((x, y, w, side, bool(inner.size and inner.std() > 10)))   # empty slots are one flat colour
        return out

    def auto_find_hotbar(self):
        """Find the hotbar in the Roblox window that's in front and point the rotation at the
        FILLED slots only (2 skills = 2 slots). Returns (filled, total) or None."""
        try:
            import pywinctl
            win = pywinctl.getActiveWindow()
        except Exception:
            win = None
        if not win or "Roblox" not in win.title:
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
        # the exact inside of each box, so snapshots don't include the gaps / background around it
        rot["slot_boxes"] = [[reg[0] + x, reg[1] + y, reg[0] + x + w, reg[1] + y + h] for x, y, w, h, _ in slots[:n]]
        rot["slot_boxes_for"] = list(rot["region"])
        self.clear_drawn_boxes(save=False)               # the hotbar may have moved: drawn boxes would be off
        self.moves()                                     # make sure there's a card per slot
        self.app.settings.save()
        self.app.log(f"Auto-find: hotbar found ({len(slots)} slots, using the {n} filled one(s)).")
        return n, len(slots)

    def slot_threshold(self, slot):
        """READY when the score is at least this: the slot's own 'Ready at' (Auto-tune), else the global one."""
        moves = self.moves()
        own = float(moves[slot - 1].get("ready_at") or 0) if 0 < slot <= len(moves) else 0
        return own if own > 0 else float(self.cfg["rotation"]["threshold"])

    def slot_image(self, slot):
        """The live picture of one hotbar slot."""
        regions = self.slot_regions()
        if not 0 < slot <= len(regions):
            return None
        return self.utils.capture_screen_bgr(regions[slot - 1])

    def wait_until_ready(self, slot, alive, timeout=60.0):
        """A slot on cooldown changes every second (its timer counts down); a READY slot stays still.
        Wait until the slot looks the same 1 s apart, then return that picture (None = gave up)."""
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
        """Learn each slot by itself, so it works even if moves are still on cooldown when you press it:
        1. wait until the slot is READY (its picture stops changing) and save that as its snapshot,
        2. read how well it matches while ready, 3. cast it, 4. read it on cooldown,
        5. put its own 'Ready at' line halfway between. Returns {slot: (result, detail)}."""
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
            cv2.imwrite(self.template_path(slot), ready_img)        # the READY snapshot, taken when it really is
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
        """Return {slot: score or None} for every slot."""
        regions = self.slot_regions()
        if not regions:
            return {}
        x1, y1, x2, y2 = self.cfg["rotation"]["region"]
        bar = self.utils.capture_screen_bgr([x1, y1, x2, y2])
        out = {}
        for i, r in enumerate(regions, start=1):
            if bar is not None and x1 <= r[0] and r[2] <= x2 and y1 <= r[1] and r[3] <= y2:
                crop = bar[r[1] - y1:r[3] - y1, r[0] - x1:r[2] - x1]
            else:
                crop = self.utils.capture_screen_bgr(r)       # a box drawn outside the hotbar region
            out[i] = self.slot_score(i, crop)
        return out

    def is_ready(self, slot, move, scores):
        score = scores.get(slot)
        if score is not None:
            # Snapshot wins: the screen reflects cooldown reduction from other casts,
            # a fixed manual timer would not.
            return score >= self.slot_threshold(slot)
        # No snapshot: rely on the manual cooldown alone (none set = unconfigured, skip)
        cd = float(move["cooldown"] or 0)
        return cd > 0 and time.time() - self.last_cast.get(slot, 0) >= cd

    def toggle(self):
        self.stop() if self.running else self.start()

    def _warn_if_roblox_admin(self):
        """Roblox 'Run as administrator' = Windows blocks every key the macro sends: say so."""
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
        self.running = True
        self._last_shake = 0
        threading.Thread(target=self._warn_if_roblox_admin, daemon=True).start()
        from utils import foreground_roblox, roblox_windows
        self._roblox_hwnd = foreground_roblox() or next((h for h, _ in roblox_windows()), 0)
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
        self._spawn(self._ok_loop)          # built in: OK popups are clicked while the macro runs (toggle or not)
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

    def _ok_loop(self):
        """Click OK popups every ~10 s while running, same as Library / Mining / Fishing do.
        Uses the OK Popup page's setup and lock, so it never clicks at the same time as 'Always Click OK'."""
        ok = getattr(getattr(self.app, "ok_page", None), "logic", None)
        if ok is None:
            return
        while self.running:
            if ok._ok_scanner_lock.acquire(blocking=False):
                try:
                    ok.handle_ok_popup()
                except Exception as e:
                    self.app.log(f"OK check error: {e}")
                finally:
                    ok._ok_scanner_lock.release()
            for _ in range(40):
                if not self.running:
                    return
                time.sleep(0.25)

    def _spawn(self, fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()
        self._threads.append(t)

    def _focused(self):
        if not self.cfg.get("only_when_focused", True):
            return True
        try:
            w = pywinctl.getActiveWindow()
            if w and "Roblox" in w.title:
                return True
        except Exception:
            return True
        # Keep Roblox in focus (on by default): bring the Roblox window back instead of pausing
        # only while the macro RUNS (not for Find hotbar / tests started from the window)
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
        """Old settings: 'Hold click (s)' and the 'Click' aim mode became one 'then M1' tick box."""
        if "click" not in d:
            d["click"] = float(d.get("hold_click") or 0) > 0 or d.get("mouse_mode") == "click"
        if d.get("mouse_mode") == "click":
            d["mouse_mode"] = "move"
        d.pop("hold_click", None)
        d.setdefault("click_btn", "m2")                  # the click after the key: M2 by default, M1 optional
        # The M1 delay's default went from 0.15 to 0.3 s: move settings still on the old default (once)
        if not d.get("m1_v2"):
            if float(d.get("m1_delay", 0.15) or 0) == 0.15:
                d["m1_delay"] = 0.3
            d["m1_v2"] = True
        return d

    def _aim(self, mode, x, y, wait=0.1):
        """Move the mouse to the move's spot, then wait so the game turns to it before the key.
        mode "none" = use wherever the mouse already is (no wait)."""
        if mode in ("move", "click"):                    # "click" = old setting, now just moves
            RobloxInputDriver.move_to(int(x), int(y))
        else:
            return
        if wait:
            self._wait(float(wait))

    def _m1_after(self, d):
        """'then click': wait the move's delay after the key (default 0.3 s), then one M2 (or M1) click."""
        if self.migrate_click(d).get("click"):
            time.sleep(max(0.0, float(d.get("m1_delay", 0.3) or 0)))
            self._click(d.get("click_btn", "m2"))
            # mouse stays put a moment so the game casts at THIS move's spot, not the next move's aim
            time.sleep(max(0.0, float(d.get("after_click", 0.1) or 0)))

    @staticmethod
    def click_name(d):
        return "M1" if d.get("click_btn", "m2") == "m1" else "M2"

    def _click(self, btn="m1"):
        """One click wherever the mouse is: M1 = left (Items), M2 = right (Rotation / Combo default)."""
        button = Button.right if btn == "m2" else Button.left
        mouse = MouseController()
        with RobloxInputDriver._lock:
            mouse.press(button)
            time.sleep(0.04)
            mouse.release(button)

    def use_item(self, item):
        """Item use = press its hotkey (equips it), short pause, then M1 to use it."""
        with RobloxInputDriver._lock:                    # not in the middle of the Event Notifier's /clear
            self._press(item["key"])
            if item.get("click", True):
                time.sleep(max(0.05, float(item.get("click_delay", 0.3) or 0.3)))
                self._click()
        self.app.log(f"Item '{item['name']}' seen -> pressed {item['key']}" + (" + M1" if item.get("click", True) else ""))

    def _press(self, key):
        if key:
            self.utils.send_key(key, 0.04)

    # ---------- meditation (refill mana) ----------
    def anti_shake(self):
        d = self.cfg["rotation"].setdefault("anti_shake", {})
        for k, v in ANTI_SHAKE_DEFAULT.items():
            d.setdefault(k, v)
        return d

    def do_anti_shake(self):
        """',' → wait → ',' → wait. Each key waits so the game finishes the camera change."""
        d = self.anti_shake()
        key = (d.get("key") or ",").strip() or ","
        self.app.log(f"Anti screen-shake: pressing '{key}' (camera reset)")
        with RobloxInputDriver._lock:
            self._press(key)
        self._wait(max(0.0, float(d.get("between", 1.0) or 0)))
        with RobloxInputDriver._lock:
            self._press(key)
        self._wait(max(0.0, float(d.get("after", 0.5) or 0)))
        # screenshot check: does the picked spot look like normal play again? If not we're still in ','
        for _ in range(2):
            if self.anti_shake_back_to_normal() is not False:
                break
            self.app.log("Anti screen-shake: in skill tree - pressing ',' once more.")
            with RobloxInputDriver._lock:
                self._press(key)
            self._wait(max(0.5, float(d.get("after", 0.5) or 0)))
        self._last_shake = time.time()

    def save_anti_shake_ref(self):
        """Picture of the check spot during NORMAL play (out of ','). True when saved."""
        r = self.anti_shake().get("check_region") or [0, 0, 0, 0]
        if r[2] <= r[0] or r[3] <= r[1]:
            return False
        img = self.utils.capture_screen_bgr(r)
        if img is None or not img.size:
            return False
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        return bool(cv2.imwrite(ANTI_SHAKE_REF, img))

    def anti_shake_back_to_normal(self):
        """True = the spot matches the normal picture, False = it doesn't (still in ','),
        None = no check set up."""
        r = self.anti_shake().get("check_region") or [0, 0, 0, 0]
        if r[2] <= r[0] or r[3] <= r[1] or not os.path.exists(ANTI_SHAKE_REF):
            return None
        ref = cv2.imread(ANTI_SHAKE_REF)
        now = self.utils.capture_screen_bgr(r)
        if ref is None or now is None or not now.size:
            return None
        try:
            now = cv2.resize(now, (ref.shape[1], ref.shape[0]))
            a = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY).astype(np.float32)
            b = cv2.cvtColor(now, cv2.COLOR_BGR2GRAY).astype(np.float32)
            return float(np.mean(np.abs(a - b))) < 25        # small changes (glow, light) are fine
        except Exception:
            return None

    def med(self):
        d = self.cfg["rotation"].setdefault("meditation", {})
        for k, v in MEDITATION_DEFAULT.items():
            d.setdefault(k, copy.deepcopy(v))            # own copy: lists / dicts must not be shared
        return d

    def mana_reading(self):
        """(fill 0..1, left end blue, right end blue) of the mana bar, or None if no bar is set.
        Mana is light blue; the used part turns dark grey from the right, so an EMPTY bar is grey at
        its left end and a FULL bar is light blue at its right end."""
        r = self.med()["region"]
        if not (r[2] > r[0] and r[3] > r[1]):
            return None
        img = self.utils.capture_screen_bgr(r)
        if img is None or not img.size:
            return None
        h = img.shape[0]
        band = cv2.cvtColor(img[int(h * 0.3):max(int(h * 0.3) + 1, int(h * 0.7))], cv2.COLOR_BGR2HSV)
        blue = ((band[:, :, 0] >= 95) & (band[:, :, 0] <= 112) & (band[:, :, 1] >= 70) & (band[:, :, 2] >= 140))
        cols = blue.mean(axis=0) >= 0.5                  # a column counts as mana if most of it is light blue
        n = len(cols)
        edge = max(1, n // 20)
        # Mana % = where the light blue ends (the grey grows from the right). The white "4010/4035" text in
        # the middle isn't blue, so look for the LAST blue column instead of counting blue columns.
        idx = np.where(cols)[0]
        fill = float(idx[-1] + 1) / n if idx.size else 0.0
        return fill, bool(cols[:edge].mean() >= 0.5), bool(cols[-edge:].mean() >= 0.5)

    def mana_empty(self):
        """Time to meditate: mana at or under the 'Meditate at' % (or the bar's left end already grey)."""
        r = self.mana_reading()
        if not r:
            return False
        below = max(0.0, float(self.med().get("below", 5) or 0)) / 100.0
        return (not r[1]) or r[0] <= below

    def mana_full(self):
        r = self.mana_reading()
        return bool(r) and r[2]

    def meditation_steps(self):
        """The keys in order, each with the name of the wait that follows it."""
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
        """Weapon out: R → N … full … N → R.  Grimoire out: G → N … N → G.  Both: R, G → N … N → G, R."""
        d = self.med()
        out = d.get("out", "weapon")
        away = ([d["weapon_key"]] if out in ("weapon", "both") else []) + \
               ([d["grimoire_key"]] if out in ("grimoire", "both") else [])
        steps = self.meditation_steps()
        gap = lambda name: self.med_wait(name)           # every step waits for its animation (own value or 'All')
        self.app.log("Mana empty → meditating…")
        self._wait(gap("start"))                         # let the last skill finish before putting things away
        for k, name in steps["away"]:                    # put them away, one at a time
            with RobloxInputDriver._lock:
                self._press(k)
            self._wait(gap(name))
        with RobloxInputDriver._lock:
            self._press(d["key"])                        # start meditating
        self._wait(gap("sit"))
        end = time.time() + float(d.get("max_wait", 90) or 90)
        while self.running and time.time() < end and not self.mana_full():
            self._wait(0.3)
        if not self.running:
            return
        full = self.mana_full()
        with RobloxInputDriver._lock:
            self._press(d["key"])                        # stop meditating
        self._wait(gap("stand"))
        for k, name in steps["back"]:                    # take them out again
            with RobloxInputDriver._lock:
                self._press(k)
            self._wait(gap(name))
        self.app.log("Mana full - back to the rotation." if full else
                     f"Meditation stopped after {int(float(d.get('max_wait', 90)))} s (mana didn't read as full).")

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
                if self.med()["enabled"] and self.mana_empty():
                    self.meditate()
                    continue
                sh = self.anti_shake()
                if sh["enabled"]:
                    if not getattr(self, "_last_shake", 0):
                        self._last_shake = time.time()   # first one after 'every' seconds, not at the start
                    elif time.time() - self._last_shake >= max(1.0, float(sh.get("every", 30) or 30)):
                        self.do_anti_shake()
                        continue
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
                        self._m1_after(m)                                    # 4. M2/M1 (if ticked)
                    if n < int(m["repeat"]) - 1:
                        # gap between presses of a multi-use move (e.g. its 0.2 s anti-spam lockout)
                        self._wait(max(0.05, float(m.get("repeat_delay") or 0.15)))
                # 5. delay after (with a small floor so the icon has time to show its cooldown)
                self._wait(max(float(m.get("delay_after") or 0), float(rot["cast_delay"])))
                # Confirm the cast: a slot with a snapshot should no longer match it.
                score = self.read_slots().get(slot)
                if score is not None and score >= self.slot_threshold(slot):
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
                    wait = max(0.08, float(step.get("delay", 0) or 0))   # 0.08 s floor so taps stay separate
                    with RobloxInputDriver._lock:            # not in the middle of the Event Notifier's /clear
                        self._press(step.get("key", ""))
                    self.app.log(f"Combo [{trig}]: step {num} pressed {step.get('key', '')}" + (f" ({i + 1}/{n})" if n > 1 else ""))
                    self._wait(wait)
                    if self.migrate_click(step).get("click") and self.running:
                        # 'then click': the step's wait box is the wait BEFORE the click (key → wait → M2/M1 → next)
                        self._click(step.get("click_btn", "m2"))
                        self._wait(max(0.02, float(step.get("after_click", 0.1) or 0)))   # mouse still after the click
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
