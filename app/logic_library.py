import os
import time
import threading
import math
import keyboard
import numpy as np
import cv2
from route_nav import RouteNav
from utils import RobloxInputDriver, is_roblox_title
from settings import get_base_path

DIALOG_TEMPLATE_DIR = os.path.join(get_base_path(), "library_templates")
DIALOG_MODES = ("auto", "image", "manual")
# Settings key per dialogue button (manual spots reuse the old "positions" entries)
MAX_MOVES = 9          # one per hotbar slot; the wisp's list is these 9 + Nevermind (always last)
MANUAL_MOVES = 3       # Manual dialogue clicks fixed spots and never scrolls: only the first 3 moves are reachable
DIALOG_BUTTONS = {"clover_training": "Clover Training", **{f"move_{i}": f"Move {i}" for i in range(1, MAX_MOVES + 1)}}


class LibraryLogic(RouteNav):
    """Spatial Library clover training.

    1. Walk to the wisp with a recorded route (Ctrl+P), or the old D/S/W walk.
    2. Open the dialogue and pick options BY POSITION (works in any language):
       first menu -> 2nd button (Clover Training), move menu -> button N for move N.
    3. Wait for the minigame (its captured snapshot shows up) and click clovers until it ends."""

    ROUTES_DIRNAME = "routes_library"
    BUILTIN_ROUTE = "VunVun's route"
    BUILTIN_DIR = os.path.join("builtin_routes", "library")
    EXTRA_BUILTINS = (("VunVun's route 2", os.path.join("builtin_routes", "library_2")),)
    ACTIVE_ROUTE_KEY = "library_active_route"
    USE_ALIGNMENT = False      # normal 3rd-person camera: no snapshot walking
    ROUTE_TARGET = "wisp"
    E_MARKS_TARGET = False     # E is recorded like any key: the whole Ctrl+P → Ctrl+P walk is the way to the wisp

    def __init__(self, app):
        super().__init__(app)
        self.current_move_idx = 0
        self.click_history = []
        self.GOLD_CLOVER_COLOR = (250, 171, 33)
        self.DEFAULT_CLOVER_COLORS = {"gold": (255, 180, 51), "silver": (164, 178, 178), "bronze": (198, 62, 37)}
        self.DEFAULT_CLOVER_TOLERANCES = {"gold": 20, "silver": 20, "bronze": 20}

    # ================= Which moves to train =================
    def _nine(self, key, fill):
        """Settings list padded to MAX_MOVES (older setups had 3). Padded IN PLACE: the saved list is never
        swapped for a copy, or a page still holding the old list (slot dropdowns) would edit a dropped copy."""
        st = self.app.settings.settings
        lst = st.get(key)
        if not isinstance(lst, list):
            lst = st[key] = []
        for i in range(len(lst), MAX_MOVES):
            lst.append(fill(i) if callable(fill) else fill)
        del lst[MAX_MOVES:]
        return lst

    def set_move_slot(self, i, slot):
        """Which hotbar slot move i sits in (for the gold clover check)."""
        self._nine("gold_move_slots", lambda k: k + 1)[i] = int(slot)
        self.app.settings.save()

    def move_names(self):
        return self._nine("move_names", "")

    def manual_moves(self):
        """Manual dialogue's own 3 move spots: [{'train': bool, 'slot': hotbar slot}]. Independent of
        'Moves to train' (names / ticks / slots there are for Auto and Image only)."""
        st = self.app.settings.settings
        lst = st.get("manual_moves")
        if not isinstance(lst, list):
            lst = st["manual_moves"] = []
        for i in range(len(lst), MANUAL_MOVES):
            lst.append({"train": i == 0, "slot": i + 1})
        del lst[MANUAL_MOVES:]
        return lst

    def train_flags(self):
        if self.dialog_mode() == "manual":           # Manual: its own ticks, only 3 spots
            return [bool(m.get("train")) for m in self.manual_moves()] + [False] * (MAX_MOVES - MANUAL_MOVES)
        if not self.app.settings.get("train_moves"):
            names = self.move_names()
            self.app.settings.settings["train_moves"] = ([bool(n) for n in names] if any(names)
                                                         else [i < 3 for i in range(MAX_MOVES)])
        return list(self._nine("train_moves", False))

    def move_label(self, i):
        if self.dialog_mode() == "manual":
            return f"Move spot {i + 1}"
        name = self.move_names()[i]
        return f"Move {i + 1}" + (f" ({name})" if name else "")

    # ---------- Gold clover: automatic (from the hotbar) or manual boxes ----------
    # The 3 clovers sit in a row on top of each hotbar icon; the 3rd is always in the same spot:
    # measured at ~78% across the icon (the 2nd is at ~46%), in the top part of a box that starts
    # at the top of the clovers (top ~18% = above the clover row line). A move is trained once that spot is gold.
    THIRD_X = (0.68, 0.90)
    THIRD_Y = (0.0, 0.18)                       # just the clover row, not the gold icon border below it
    GOLD_SHARE = 0.05       # anything not gold reads 0.00 (strong-gold colour test); gold reads 0.08 (small window) - 0.25
    GOLD_HSV_LO, GOLD_HSV_HI = (10, 160, 170), (30, 255, 255)   # clover gold only, never the gold-ish text

    def gold_mode(self):
        return "manual" if self.app.settings.get("gold_mode") == "manual" else "auto"

    def gold_hotbar(self):
        hb = self.app.settings.get("gold_hotbar") or {}
        r = hb.get("region", [0, 0, 0, 0])
        return (r, max(1, int(hb.get("slots", 6)))) if r[2] > r[0] and r[3] > r[1] else (None, 0)

    CLOVER_ROW = 1.13        # box height = icon height × this (adds the row of clovers above the icons)

    def auto_find_gold_hotbar(self):
        """Find the hotbar in the Roblox window that's in front (same search as the Skill Macro's Find hotbar)
        and set the gold-clover box over the FILLED slots, clovers included. Returns slot count or None."""
        from logic_smart import SmartMacroLogic
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
        slots = SmartMacroLogic.find_hotbar_slots(img) if img is not None else []
        filled = max((i for i, s in enumerate(slots, start=1) if s[4]), default=0)
        if not filled:
            self.app.log("Auto-find: couldn't see the hotbar - drag it with Set hotbar instead.")
            return None
        side = slots[0][3]
        bottom_img = slots[0][1] + side
        last = slots[filled - 1]
        # Where the clover row really is (Roblox scales it differently in small windows): the gold/bronze
        # clovers are the colourful bits just above the right side of the filled slots.
        cy = self._clover_row_y(img, slots)
        if cy is not None:
            top_img = (cy - self.THIRD_Y[1] / 2 * bottom_img) / (1 - self.THIRD_Y[1] / 2)   # 3rd-clover box centred on it
        else:
            top_img = bottom_img - side * self.CLOVER_ROW                              # no clovers yet: usual spot
        hb = self.app.settings.settings.setdefault("gold_hotbar", {})
        hb["region"] = [reg[0] + slots[0][0], reg[1] + int(round(top_img)), reg[0] + last[0] + last[2],
                        reg[1] + bottom_img]
        hb["slots"] = filled
        # The 3rd clover always sits on the TOP-RIGHT CORNER of its slot's frame: pin each check box there,
        # from that slot's own frame (no guessing the clover row, which could end up too high).
        hb["spots"] = [self.corner_spot(reg[0] + x, reg[1] + y, w, s) for x, y, w, s, _ in slots[:filled]]
        self.app.settings.save()
        self.app.log(f"Auto-find: hotbar found, {filled} filled slot(s). Press Show to check the yellow boxes.")
        return filled

    @staticmethod
    def _clover_row_y(img, slots):
        """Centre height of the clover row above the hotbar (image coords), or None if no clovers show."""
        side, top = slots[0][3], slots[0][1]
        y1, y2 = max(0, int(top - side * 0.3)), int(top + side * 0.25)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        prof = np.zeros(max(0, y2 - y1))
        for x, _, w, _, filled in slots:
            if not filled:
                continue
            band = hsv[y1:y2, x + int(w * 0.55):x + int(w * 0.98)]
            prof += ((band[:, :, 0] >= 8) & (band[:, :, 0] <= 32) & (band[:, :, 1] >= 160)
                     & (band[:, :, 2] >= 170)).sum(axis=1)   # strong clover gold/bronze, not the name text
        if not prof.size or prof.max() < 3:
            return None
        return float((prof * np.arange(y1, y2)).sum() / prof.sum())

    def move_slot(self, i):
        if self.dialog_mode() == "manual" and i < MANUAL_MOVES:
            return int(self.manual_moves()[i].get("slot") or i + 1)
        return int(self._nine("gold_move_slots", lambda k: k + 1)[i])

    CORNER_X = (0.71, 0.96)     # of the slot's width: the 3rd clover / top-right corner of the frame
    CORNER_Y = (-0.12, 0.15)    # of the slot's height, around the frame's top edge (small windows draw clovers lower)

    @classmethod
    def corner_spot(cls, x, top, w, side):
        """Check box on the top-right corner of one slot frame (screen coords)."""
        return [int(x + cls.CORNER_X[0] * w), int(top + cls.CORNER_Y[0] * side),
                int(x + cls.CORNER_X[1] * w), int(top + cls.CORNER_Y[1] * side)]

    def third_clover_rect(self, slot):
        """Screen box of the 3rd-clover spot of hotbar slot 1..n (None if the hotbar isn't set)."""
        r, n = self.gold_hotbar()
        if not r or not 1 <= slot <= n:
            return None
        spots = (self.app.settings.get("gold_hotbar") or {}).get("spots") or []
        if slot <= len(spots):                           # Auto: pinned to each slot's top-right corner
            return list(spots[slot - 1])
        sw, h = (r[2] - r[0]) / n, r[3] - r[1]
        x = r[0] + (slot - 1) * sw
        return [int(x + self.THIRD_X[0] * sw), int(r[1] + self.THIRD_Y[0] * h),
                int(x + self.THIRD_X[1] * sw), int(r[1] + self.THIRD_Y[1] * h)]

    def third_clover_share(self, slot):
        """How much of the 3rd-clover spot is gold (0..1), or None if it can't be checked."""
        rect = self.third_clover_rect(slot)
        if not rect:
            return None
        img = self.utils.capture_screen_bgr(rect)
        if img is None or not img.size:
            return None
        return float((self.gold_mask(img) > 0).mean())

    def gold_strictness(self):
        """How alike a pixel must be to the gold colour, in % (default 95)."""
        try:
            return min(100.0, max(50.0, float(self.app.settings.get("gold_strict", 95))))
        except (TypeError, ValueError):
            return 95.0

    def gold_mask(self, img_bgr):
        """Gold pixels of a BGR picture.
        - your own picked gold colour: every channel within (100 - strictness)% of it (95% = about +-13 of 255)
        - built-in: the clover's strong gold only (saturation >= 160 - the move NAME text is a pale gold ~120),
          and the strictness narrows that range further."""
        own = self.app.settings.get("gold_color")
        strict = self.gold_strictness()
        if own:
            tol = int(round((100.0 - strict) * 2.55))
            r, g, b = (int(v) for v in own[:3])
            lo = np.array([max(0, b - tol), max(0, g - tol), max(0, r - tol)], np.uint8)
            hi = np.array([min(255, b + tol), min(255, g + tol), min(255, r + tol)], np.uint8)
            return cv2.inRange(img_bgr, lo, hi)
        k = (100.0 - strict) / 5.0                        # 95% = the tested built-in range; stricter = narrower
        lo = (int(self.GOLD_HSV_LO[0] + (1 - min(k, 1)) * 3), int(self.GOLD_HSV_LO[1] + (1 - min(k, 1)) * 20),
              int(self.GOLD_HSV_LO[2] + (1 - min(k, 1)) * 20))
        hi = (int(self.GOLD_HSV_HI[0] - (1 - min(k, 1)) * 3), 255, 255)
        return cv2.inRange(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV), lo, hi)

    def move_is_gold(self, i):
        if self.gold_mode() == "auto":
            share = self.third_clover_share(self.move_slot(i))
            return share is not None and share >= self.GOLD_SHARE
        area = self.app.settings.get("regions", {}).get(f"gold_clover_{i + 1}", [0, 0, 0, 0])
        if not any(v != 0 for v in area):
            return False
        img = self.utils.capture_screen_bgr(area)
        if img is None or not img.size:
            return False
        if not self.app.settings.get("gold_color"):
            # manual boxes always compared with a colour: the built-in clover gold unless you picked your own
            own = self.GOLD_CLOVER_COLOR
            tol = int(round((100.0 - self.gold_strictness()) * 2.55))
            r, g, b = own
            mask = cv2.inRange(img, np.array([max(0, b - tol), max(0, g - tol), max(0, r - tol)], np.uint8),
                               np.array([min(255, b + tol), min(255, g + tol), min(255, r + tol)], np.uint8))
        else:
            mask = self.gold_mask(img)
        # a real patch of gold, not one stray pixel
        return float((mask > 0).mean()) >= self.GOLD_SHARE

    def usable_moves(self):
        """How many moves this dialogue mode can reach: Manual = 3 (fixed spots, no scrolling), else all 9."""
        return MANUAL_MOVES if self.dialog_mode() == "manual" else MAX_MOVES

    def check_trained_status(self):
        """A move is done when its 3rd clover is gold (automatic: read from the hotbar; manual: its own box)."""
        flags = self.train_flags()
        trained = [not f for f in flags]
        limit = self.usable_moves()
        skipped = [i for i in range(limit, MAX_MOVES) if not trained[i]]
        if skipped and not getattr(self, "_warned_manual_limit", False):
            self.app.log(f"Manual dialogue only reaches Moves 1-{MANUAL_MOVES} (no scrolling) - skipping "
                         + ", ".join(f"Move {i + 1}" for i in skipped) + ". Use Image or Auto for those.")
            self._warned_manual_limit = True
        for i in skipped:
            trained[i] = True
        for i in range(MAX_MOVES):
            if trained[i]:
                continue
            if self.move_is_gold(i):
                self.app.log(f"{self.move_label(i)} is already trained (Gold Clover detected).")
                trained[i] = True
        return trained

    # ================= Getting to the wisp =================
    def go_to_wisp(self):
        route, name = self.load_route(), self.active_route()
        if not route:
            # the selected route was never recorded (e.g. made with New): use the built-in route instead of
            # asking for a recording - nobody has to press Ctrl+P to use the macro
            for b in self._builtins():
                route = self.load_route(b)
                if route:
                    self.app.log(f"Route '{name}' has no recording - using the built-in '{b}' instead.")
                    name = b
                    break
        if not route:
            self.app.log(f"No recorded route to the wisp - using the old D/S/W walk. (Record one with {self.rec_key()}.)")
            self.perform_approach_movement()
            return
        # New recordings: the whole walk is one piece ('return'). Old ones: the walk up to the first E.
        seg = route["segments"][0] if route["segments"] else route["return"]
        self.align_home()
        self.app.log(f"Walking to the wisp (route '{name}')...")
        self.play_segment(seg, label="wisp")
        self._wait_still()

    def perform_approach_movement(self):
        """Legacy walk for users without a recording."""
        for key, secs in (("d", 2.0), ("s", 2.0), ("w", 3.0)):
            if not self.running:
                return
            self.app.log(f"Approaching NPC area (Holding {key.upper()})...")
            self.hold_key(key, secs)

    # ================= Dialogue (language independent) =================
    @staticmethod
    def find_dialog(img):
        """Find the dialogue panel and the option buttons to its right, by shape.
        Returns (panel, buttons) in image coords; buttons top-to-bottom."""
        H, W = img.shape[:2]
        y0 = int(H * 0.55)
        g = cv2.cvtColor(img[y0:], cv2.COLOR_BGR2GRAY)
        bgr = img[y0:].astype(np.int16)
        hovered = (bgr[..., 1] > bgr[..., 2] + 25) & (bgr[..., 1] > bgr[..., 0] + 15)  # green = mouse over it
        dark = ((g < 75) | hovered).astype(np.uint8) * 255
        # remove thin dark lines (e.g. the mouse cursor's outline) that would glue buttons together
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, _, st, _ = cv2.connectedComponentsWithStats(dark)
        panel = None
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if w > W * 0.2 and h > H * 0.12 and a > w * h * 0.5:
                panel = (x, y + y0, w, h)
        def column_fallback():
            # The panel can blend into other dark things (the macro window, a dark floor) or another dark area
            # can look like it, so find the BUTTON COLUMN itself: 2+ same-size dark buttons stacked at one x.
            cands = [(int(x), int(y) + y0, int(w), int(h)) for x, y, w, h, a in st[1:]
                     if W * 0.06 < w < W * 0.16 and H * 0.02 < h < H * 0.07 and a > w * h * 0.35]
            best = []
            for c in cands:
                col = sorted((o for o in cands if abs(o[0] - c[0]) <= 6 and abs(o[2] - c[2]) <= c[2] * 0.1),
                             key=lambda o: o[1])
                if len(col) >= 2 and len(col) > len(best):
                    best = col
            if not best:
                return None
            bx = min(b[0] for b in best)
            top, bottom = min(b[1] for b in best), max(b[1] + b[3] for b in best)
            return (max(0, bx - 12), top, 1, bottom - top)        # a thin stand-in just left of the buttons

        def buttons_next_to(panel):
            px, py, pw, ph = panel
            # pieces right of the panel; a button can be cut in two by a bright line (mouse pointer, glare),
            # so pieces on the same row that touch are joined back into one button first
            parts = []
            for i in range(1, n):
                x, y, w, h, a = st[i]
                y += y0
                # fill >= 35%: in small windows a button's two lines of text cover much of its dark fill
                if px + pw < x < px + pw + W * 0.16 and H * 0.02 < h < H * 0.07 and w > 6 and a > w * h * 0.35:
                    parts.append([x, y, x + w, y + h])
            parts.sort()
            merged = []
            for p_ in parts:
                for m in merged:
                    same_row = abs(m[1] - p_[1]) <= 6 and abs(m[3] - p_[3]) <= 6
                    if same_row and p_[0] - m[2] <= 14:
                        m[0], m[1] = min(m[0], p_[0]), min(m[1], p_[1])
                        m[2], m[3] = max(m[2], p_[2]), max(m[3], p_[3])
                        break
                else:
                    merged.append(list(p_))
            buttons = [(x1, y1, x2 - x1, y2 - y1) for x1, y1, x2, y2 in merged
                       if px + pw < x1 < px + pw + W * 0.08 and W * 0.06 < x2 - x1 < W * 0.16]
            return sorted(buttons, key=lambda b: b[1])

        buttons = buttons_next_to(panel) if panel else []
        if not buttons:
            alt = column_fallback()
            if alt:
                panel, buttons = alt, buttons_next_to(alt)
        if not buttons and not panel:
            return None, []
        return panel, buttons

    def read_dialog(self, with_text=False):
        """(dialogue open?, button centres) - plus a small image of the panel's text
        when with_text, used to tell menus apart without reading any words."""
        win = self.get_roblox_window_region()
        img = self._screen()
        panel, buttons = self.find_dialog(img)
        centers = [(win[0] + x + w // 2, win[1] + y + h // 2) for x, y, w, h in buttons]
        if not with_text:
            return panel is not None, centers
        sig = None
        if panel:
            x, y, w, h = panel
            top = cv2.cvtColor(img[y + int(h * .05):y + int(h * .45), x + int(w * .03):x + int(w * .97)],
                               cv2.COLOR_BGR2GRAY)
            text = cv2.dilate((top > 110).astype(np.uint8) * 255, np.ones((5, 5), np.uint8))
            sig = cv2.resize(text, (120, 24), interpolation=cv2.INTER_AREA) > 64
        return panel is not None, centers, sig

    # ---------- Minigame detector: a snapshot of something only shown in the minigame ----------
    MINIGAME_TEMPLATE = os.path.join(DIALOG_TEMPLATE_DIR, "minigame.png")

    def minigame_mode(self):
        return "snapshot"                         # the old black-bar check didn't work, so it was removed

    def has_minigame_snapshot(self):
        return os.path.exists(self.MINIGAME_TEMPLATE) and any(self.app.settings.get("regions", {}).get("minigame_marker", [0]))

    def save_minigame_snapshot(self, img_bgr, region):
        """img_bgr = the cropped marker taken DURING a minigame; region = where it sits on screen."""
        if img_bgr is None or img_bgr.size == 0 or min(img_bgr.shape[:2]) < 6:
            return False
        os.makedirs(DIALOG_TEMPLATE_DIR, exist_ok=True)
        self.app.settings.settings.setdefault("regions", {})["minigame_marker"] = list(region)
        self.app.settings.save()
        self._mg_tpl = None
        return cv2.imwrite(self.MINIGAME_TEMPLATE, img_bgr)

    def minigame_score(self):
        """0..1 how much the marker area looks like the snapshot (None if no snapshot)."""
        if not self.has_minigame_snapshot():
            return None
        if getattr(self, "_mg_tpl", None) is None:
            self._mg_tpl = cv2.imread(self.MINIGAME_TEMPLATE)
        tpl = self._mg_tpl
        now = self.utils.capture_screen_bgr(self.app.settings.get("regions")["minigame_marker"])
        if tpl is None or now is None or now.size == 0:
            return None
        if now.shape[:2] != tpl.shape[:2]:
            now = cv2.resize(now, (tpl.shape[1], tpl.shape[0]))
        a = cv2.cvtColor(now, cv2.COLOR_BGR2GRAY).astype(np.float32)
        b = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if a.std() < 1 or b.std() < 1:                   # flat area: compare brightness only
            return 1.0 - min(1.0, abs(a.mean() - b.mean()) / 64.0)
        corr = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0][0])
        bright = 1.0 - min(1.0, abs(a.mean() - b.mean()) / max(b.mean(), 1.0))
        return max(0.0, min(corr, bright))

    # ---------- hide Roblox chat during the minigame ----------
    # Its white "Here / Global / Friends" tabs look like silver clovers to the clicker.
    def toggle_chat(self, why):
        """Click the chat button (top bar) set in Areas. 'hide' when a minigame starts, 'show' after it,
        so the Event Notifier can still read chat between minigames."""
        pos = self.app.settings.get("regions", {}).get("chat_button", [0, 0])
        if not self.app.settings.get("hide_chat_in_minigame") or not any(pos):
            return
        if why == "hide":
            self._chat_hidden = True
        elif not getattr(self, "_chat_hidden", False):
            return                                   # only re-open what we closed
        else:
            self._chat_hidden = False
        # Holds the shared input lock until the chat has finished closing/opening, so no clover click
        # (or OK / event check) can land in between and undo it.
        with RobloxInputDriver._lock:
            self.human_click(*pos, duration=0.12)
            self._park_mouse()
            time.sleep(0.6)
        self.app.log("Chat hidden for the minigame." if why == "hide" else "Chat shown again.")

    def in_minigame(self):
        s = self.minigame_score()
        if s is None:
            if not getattr(self, "_warned_no_mg", False):
                self.app.log("Minigame detector: no snapshot yet — Areas tab → Minigame detector → Capture.")
                self._warned_no_mg = True
            return False
        return s >= float(self.app.settings.get("minigame_threshold", 0.8))

    # ---------- Image / Manual dialogue modes ----------
    def dialog_mode(self):
        mode = self.app.settings.get("dialog_mode", "auto")
        return mode if mode in DIALOG_MODES else "auto"

    @staticmethod
    def dialog_template_path(key):
        return os.path.join(DIALOG_TEMPLATE_DIR, f"{key}.png")

    def has_dialog_template(self, key):
        return os.path.exists(self.dialog_template_path(key))

    def capture_dialog_button(self, key, region):
        """Save a snapshot of one dialogue button (drag a box around it while it's on screen)."""
        img = self.utils.capture_screen_bgr(region)
        if img is None or img.size == 0 or min(img.shape[:2]) < 8:
            return False
        os.makedirs(DIALOG_TEMPLATE_DIR, exist_ok=True)
        return cv2.imwrite(self.dialog_template_path(key), img)

    def find_dialog_button(self, key, threshold=0.8):
        """Screen position of a captured button, or None."""
        if not self.has_dialog_template(key):
            return None
        return self.utils.image_search(self.dialog_template_path(key), self.get_roblox_window_region(), threshold)

    def manual_point(self, key):
        pt = self.app.settings.get("positions", {}).get(key, [0, 0])
        return tuple(pt) if pt and any(pt) else None

    def _skip_typing(self, seconds):
        """Just wait while the dialogue text types out (Skip is never clicked)."""
        end = time.time() + seconds
        while self.running and time.time() < end:
            time.sleep(0.05)

    def after_training_wait(self):
        """Seconds to wait after clicking Clover Training before reading the move list (editable in
        Settings > Wisp dialogue). Reading too early sees a half-faded list and scrolls past the move."""
        try:
            return max(0.0, float(self.app.settings.get("after_training_wait", 1.5)))
        except (TypeError, ValueError):
            return 1.5

    def run_dialogue_fixed(self, move_idx):
        """Image / Manual mode: click Clover Training, then the move's button."""
        mode = self.dialog_mode()
        wait = float(self.app.settings.get("dialog_wait", 1.5))
        steps = [("clover_training", "Clover Training"), (f"move_{move_idx + 1}", self.move_label(move_idx))]
        self._park_mouse()
        for n, (key, label) in enumerate(steps, start=1):
            if n == 2 and mode == "image":
                time.sleep(self.after_training_wait())   # let the move list fully show before reading it
                return self.pick_move_button(move_idx)
            if mode == "manual":
                pt = self.manual_point(key)
                if not pt:
                    self.app.log(f"-> No click spot set for {label}. Set it in Settings > Wisp dialogue.")
                    return False
                self._skip_typing(wait)
            else:
                if not self.has_dialog_template(key):
                    self.app.log(f"-> No snapshot of the {label} button. Capture it in Settings > Wisp dialogue.")
                    return False
                pt, deadline = None, time.time() + 15
                while self.running and time.time() < deadline and not pt:
                    pt = self.find_dialog_button(key)
                    if not pt:
                        self._skip_typing(0.3)
                if not pt:
                    self.app.log(f"-> Couldn't find the {label} button on screen.")
                    return False
                time.sleep(0.3)                          # let the menu finish fading in
                pt = self.find_dialog_button(key) or pt
            if not self.running:
                return False
            self.app.log(f"[{n}/2] Clicking {label} ({mode})")
            self.human_click(*pt, duration=0.15)
            self._park_mouse()
        return True

    # ---------- the move list: 9 moves + Nevermind, only ~4 visible, scrolls with the mouse wheel ----------
    TRAINING_WORDS = ("clover", "training", "research")
    NEVER_WORDS = ("class", "reset", "opportunit")        # Class Reset must never be clicked

    @staticmethod
    def _has_word(text, words):
        """True if `text` contains one of `words`, forgiving OCR typos in tiny text
        ('reskarch' = research, 'Trainingl' = training)."""
        import difflib, re
        t = text.lower()
        if any(w in t for w in words):
            return True
        tokens = re.findall(r"[a-z]{4,}", t)
        return any(difflib.SequenceMatcher(None, tok, w).ratio() >= 0.8 for tok in tokens for w in words)

    def find_training_button(self):
        """The first menu's 'I'd like to research. [Clover Training]' button, found by its TEXT.
        Returns ((x, y), description) or None. A button mentioning Class Reset is never returned."""
        btns = self.dialog_buttons()
        low = [(x, y, (t or "").lower()) for x, y, t in btns]
        for x, y, t in low:
            if self._has_word(t, self.TRAINING_WORDS) and not self._has_word(t, self.NEVER_WORDS):
                return (x, y), f"'{t.strip()[:40]}'"
        # Backup: read the whole button column and click right on the words (a button the shape
        # finder missed is still found this way)
        hit = self._find_words_right_of_panel(self.TRAINING_WORDS, self.NEVER_WORDS)
        if hit:
            return hit, "the 'research / Clover Training' text"
        # No readable 'Clover Training' text: fall back to position (just above Nevermind), but only
        # with 3+ buttons and never onto a button that reads as Class Reset.
        if len(low) >= 3:
            x, y, t = low[-2]
            if not self._has_word(t, self.NEVER_WORDS):
                return (x, y), f"button {len(low) - 1} of {len(low)} (just above Nevermind)"
        if not getattr(self, "_warned_training", 0) or time.time() - self._warned_training > 5:
            self.app.log(f"   First menu: can't find 'Clover Training' yet ({len(low)} button(s): "
                         f"{' | '.join(t[:25] or '?' for _, _, t in low)}) - waiting")
            self._warned_training = time.time()
        return None

    def _find_words_right_of_panel(self, words, never=()):
        """OCR the strip right of the dialogue panel (where the option buttons are); return the screen
        centre of the first text line containing one of `words` (and none of `never`), or None."""
        win = self.get_roblox_window_region()
        img = self._screen()
        panel, _ = self.find_dialog(img)
        if not panel:
            return None
        px, py, pw, ph = panel
        W = img.shape[1]
        area = [win[0] + px + pw, win[1] + max(0, py - int(ph * 0.3)),
                win[0] + min(W, px + pw + int(W * 0.18)), win[1] + py + ph]
        lines = self.utils.get_text_from_region(area)
        lines.sort(key=lambda r: min(p[1] for p in r[0]))
        for i, (box, text, conf) in enumerate(lines):
            t = text.lower()
            nxt = lines[i + 1][1].lower() if i + 1 < len(lines) else ""
            if self._has_word(t, words) and not (self._has_word(t, never) or self._has_word(nxt, never)):
                cx = sum(p[0] for p in box) / len(box)
                cy = sum(p[1] for p in box) / len(box)
                return int(area[0] + cx), int(area[1] + cy)
        return None

    def _ocr_button(self, crop):
        """Read ONE button picture. Small, pixelated text (e.g. 'Sovereign Magic: Cage Gates' squeezed into
        a smaller font) reads blank or as 'Cagt' straight off the screen; enlarging it smoothly and giving it
        a wide border of its own background makes the reader see the whole line."""
        if crop is None or not crop.size:
            return ""
        self.utils._init_ocr()
        reader = getattr(self.utils, "ocr_reader", None)
        if not reader:
            return ""
        best = ""
        for up in (2, 4):
            big = cv2.resize(crop, None, fx=up, fy=up, interpolation=cv2.INTER_LANCZOS4)
            big = cv2.copyMakeBorder(big, 40, 40, 40, 40, cv2.BORDER_REPLICATE)
            try:
                res, _ = reader(big)
            except Exception:
                res = None
            res = sorted(res or [], key=lambda r: (min(p[1] for p in r[0]), min(p[0] for p in r[0])))
            text = " ".join(t for _, t, c in res if float(c) > 0.3).strip()
            if len(self._norm_name(text)) > len(self._norm_name(best)):
                best = text
        return best

    def _read_button_texts(self, win, boxes, img_h=None, img=None):
        """Read ALL the option buttons in one go (the whole column plus a margin - reading each button on its
        own cuts letters at its edges) and give each button the text lines that sit on it."""
        m = 10
        x1 = max(0, min(b[0] for b in boxes) - m); y1 = max(0, min(b[1] for b in boxes) - m)
        x2 = max(b[0] + b[2] for b in boxes) + m; y2 = max(b[1] + b[3] for b in boxes) + m
        if img_h:
            y2 = min(y2, img_h)
        found = self.utils.get_text_from_region([win[0] + x1, win[1] + y1, win[0] + x2, win[1] + y2], upscale=3)
        texts = []
        for x, y, w, h in boxes:
            cy = y + h / 2 - y1
            lines = sorted((min(p[1] for p in bb), t) for bb, t, c in found
                           if abs((bb[0][1] + bb[2][1]) / 2 - cy) < h * 0.6)
            texts.append(" ".join(t for _, t in lines))
        if img is not None:
            # a button that read blank, or the same as another one, gets its own careful read
            for i, (x, y, w, h) in enumerate(boxes):
                k = self._norm_name(texts[i])
                if not k or sum(1 for t in texts if self._norm_name(t) == k) > 1:
                    again = self._ocr_button(img[max(0, y):y + h, max(0, x):x + w])
                    if self._norm_name(again):
                        texts[i] = again
        return texts

    def dialog_buttons(self):
        """[(x, y, text)] of the option buttons on screen, top to bottom (text read with OCR)."""
        win = self.get_roblox_window_region()
        img = self._screen()
        panel, boxes = self.find_dialog(img)
        if not boxes:
            return []
        texts = self._read_button_texts(win, boxes, img.shape[0], img)
        return [(win[0] + x + w // 2, win[1] + y + h // 2, t) for (x, y, w, h), t in zip(boxes, texts)]

    @staticmethod
    def _same_name(a, b):
        """Does button text b show move name a? Whole-name match (forgiving), or - for the one-word names
        Auto setup saves - any single word on the button within one misread letter ('Cage' ~ 'Cagt')."""
        import difflib, re
        an = "".join(ch for ch in a.lower() if ch.isalnum())
        bn = "".join(ch for ch in b.lower() if ch.isalnum())
        if not an or not bn:
            return False
        if an in bn or bn in an or difflib.SequenceMatcher(None, an, bn).ratio() >= 0.8:
            return True
        if len(an) >= 3 and " " not in a.strip():
            return any(difflib.SequenceMatcher(None, an, w).ratio() >= 0.75
                       for w in re.findall(r"[a-z0-9]+", b.lower()) if len(w) >= 3)
        return False

    def _scroll_list(self, buttons, notches=-1):
        """One mouse-wheel notch down over the button column."""
        from pynput.mouse import Controller as MouseController
        x, y = buttons[len(buttons) // 2][:2]
        with self.input_lock:
            # Roblox misses an instant jump: glide there in small steps, wiggle, THEN scroll
            mc = MouseController()
            sx, sy = mc.position
            for k in range(1, 13):
                self.utils.mouse_move(int(sx + (x - sx) * k / 12), int(sy + (y - sy) * k / 12))
                time.sleep(0.015)
            for dx in (3, -3, 0):
                self.utils.mouse_move(x + dx, y)
                time.sleep(0.04)
            time.sleep(0.15)
            for _ in range(abs(notches)):
                mc.scroll(0, -1 if notches < 0 else 1)
                time.sleep(0.08)
        time.sleep(0.6)                                 # let the list settle
        self._park_mouse()
        time.sleep(0.2)

    @staticmethod
    def _is_skip(text):
        return (text or "").strip().lower().strip(".!") in ("skip", "skip>", ">>")

    def _move_refs(self):
        """Names to recognise the move list by: the hotbar names read once (cached for this session)
        plus the saved 'Moves to train' names."""
        refs = list(getattr(self, "_hotbar_seen", []) or [])
        if not refs and self.running and not getattr(self, "_hotbar_tried", False):
            self._hotbar_tried = True                 # read the hotbar once per session, not every dialogue
            try:
                refs = [t for _, t in (self.read_hotbar_names() or []) if t]
                self._hotbar_seen = refs
            except Exception:
                refs = []
        flags = self.train_flags()
        names = self._nine("move_names", "")
        return refs + [names[i] for i in range(MAX_MOVES) if flags[i] and names[i]]

    def _looks_like_move(self, text, refs):
        """Does this button text match one of the moves ~50% or more? First-menu buttons never count."""
        import difflib
        t = self._norm_name(text)
        if len(t) < 3 or self._is_skip(text) or self._has_word(text, self.TRAINING_WORDS) or self._has_word(text, self.NEVER_WORDS)                 or "never" in t:
            return False
        for r in refs:
            rn = self._norm_name(r)
            if len(rn) < 3:
                continue
            need = 0.5 if min(len(t), len(rn)) >= 6 else 0.75     # short words need a closer match
            if rn in t or difflib.SequenceMatcher(None, t, rn).ratio() >= need:
                return True
        return False

    def wait_move_list(self, timeout=12.0, alive=None):
        """Wait until the MOVE LIST is on screen: 2+ real buttons (not just 'Skip' while the text is typing)
        and the same buttons for ~0.8 s. Returns those buttons [(x, y, text)], or [] if it never settled."""
        alive = alive or (lambda: self.running)
        end = time.time() + timeout
        last, since, seen_list = None, 0.0, []
        refs = self._move_refs()
        while alive() and time.time() < end:
            buttons = [b for b in self.dialog_buttons() if not self._is_skip(b[2])]
            # 'settled' = the same buttons in the same PLACES. Not the exact letters: on a busy background
            # (wisp sparkles) the reader can flip a letter each time ('Nevermind.' / 'Nevermind'), which
            # used to keep it from ever settling -> "Couldn't read the wisp's move list".
            sig = tuple((int(b[0]) // 8, int(b[1]) // 8) for b in buttons)
            # fast trigger: a button that looks ~50% like one of YOUR moves (hotbar / saved names) = the move list
            if any(self._looks_like_move(b[2], refs) for b in buttons):
                return buttons
            if len(buttons) >= 2:
                if sig != last:
                    last, since = sig, time.time()
                elif time.time() - since >= 0.8:
                    return buttons
            else:
                last = None
            if len(buttons) >= 2:
                seen_list = buttons                  # remember: a list WAS there
            time.sleep(0.25)
        # never perfectly still, but a real list was seen: use it rather than giving up
        return seen_list

    def save_debug_shot(self, name):
        """Save exactly what the macro sees (the Roblox window it reads) to data/debug/<name>.png, with the
        dialogue panel / buttons it found drawn in. Returns the file path (or None)."""
        try:
            from settings import get_base_path
            img = self._screen()
            if img is None or not img.size:
                return None
            panel, boxes = self.find_dialog(img)
            if panel:
                x, y, w, h = (int(v) for v in panel)
                cv2.rectangle(img, (x, y), (x + max(w, 2), y + h), (255, 160, 0), 2)
            for x, y, w, h in boxes:
                cv2.rectangle(img, (int(x), int(y)), (int(x + w), int(y + h)), (0, 0, 255), 2)
            cv2.putText(img, f"{len(boxes)} button(s) found", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            folder = os.path.join(get_base_path(), "debug")
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{name}.png")
            cv2.imwrite(path, img)
            return path
        except Exception:
            return None

    def _list_anchor(self):
        """Where to scroll the move list when no buttons could be detected (Image mode works by picture):
        the dialogue's button column sits on the right, lower part of the Roblox window."""
        l, t, r, b = self.get_roblox_window_region()
        return [(int(l + (r - l) * 0.86), int(t + (b - t) * 0.72), "")]

    def _any_move_picture(self, idxs):
        return any(self.has_dialog_template(f"move_{i + 1}") and self.find_dialog_button(f"move_{i + 1}")
                   for i in idxs)

    def _best_name_hit(self, name, buttons):
        """The button that shows `name` BEST: an exact match beats one that only contains it
        ('Flameball' must pick 'Flameball', not 'Great Flameball')."""
        import difflib
        hits = [b for b in buttons if b[2] and self._same_name(name, b[2])]
        if not hits:
            return None
        n = self._norm_name(name)
        return max(hits, key=lambda b: (self._norm_name(b[2]) == n,
                                        difflib.SequenceMatcher(None, n, self._norm_name(b[2])).ratio()))

    def pick_move_button(self, move_idx):
        """In the move menu: find the move by its captured picture or its name; if it isn't visible,
        scroll ONE notch down and look again. Nevermind is always last: seeing it = end of the list."""
        key, name = f"move_{move_idx + 1}", self.move_names()[move_idx]
        label = self.move_label(move_idx)
        has_pic = self.has_dialog_template(key)
        for step in range(MAX_MOVES + 3):
            if not self.running:
                return False
            if has_pic:
                pt = self.find_dialog_button(key)
                if pt:
                    self.app.log(f"[2/2] Found {label} (picture) - clicking")
                    self.human_click(*pt, duration=0.15)
                    return True
            buttons = self.wait_move_list(timeout=4 if has_pic else 12)
            if not buttons:
                if not has_pic:
                    self.app.log(f"-> The move list didn't show up (only 'Skip' / no buttons).")
                    return False
                # Image mode: the button shapes weren't detected, but the picture is what counts -
                # scroll over the dialogue and look for the picture again
                self.app.log(f"   {label} not visible yet - scrolling down (by picture)")
                self._scroll_list(self._list_anchor())
                continue
            at_end = any("never" in (b[2] or "").lower() for b in buttons)
            # Image mode: the PICTURE leads - the name is only a last try once the whole list was checked
            if name and (not has_pic or at_end):
                hit = self._best_name_hit(name, buttons)
                if hit:
                    self.app.log(f"[2/2] Found {label} (name{' - picture not found' if has_pic else ''}) - clicking")
                    self.human_click(hit[0], hit[1], duration=0.15)
                    return True
            elif not has_pic and step == 0:
                # nothing to recognise it by: count down the buttons that are showing
                moves = [b for b in buttons if "never" not in b[2].lower()]
                if move_idx < len(moves):
                    self.app.log(f"[2/2] Clicking button {move_idx + 1} = {label} (no name/picture set)")
                    self.human_click(moves[move_idx][0], moves[move_idx][1], duration=0.15)
                    return True
            never = next((b for b in buttons if "never" in b[2].lower()), None)
            if never:
                self.app.log(f"-> Reached the end of the list without finding {label}. "
                             f"Check its name / picture in Settings.")
                self.human_click(never[0], never[1], duration=0.15)
                return False
            self.app.log(f"   {label} not visible yet - scrolling down")
            self._scroll_list(buttons)
        self.app.log(f"-> Couldn't find {label} in the move list.")
        return False

    def dialogue_visible(self):
        if self.read_dialog()[0]:
            return True
        return self.dialog_mode() == "image" and self.find_dialog_button("clover_training") is not None

    def open_dialogue(self):
        """Press E at the wisp until the dialogue panel appears."""
        if self.dialog_mode() == "manual":
            # Manual mode is for setups where detection fails, so don't wait for it.
            if not self.wait_for_roblox_focus():
                return False
            self.utils.send_key('e')
            self.app.log("Dialogue: pressed E (manual mode).")
            return True
        for attempt in range(1, 9):
            if not self.wait_for_roblox_focus():
                return False
            if attempt % 3 == 0:
                self.utils.send_key('space')      # unstick / stand up
                time.sleep(0.4)
            self.utils.send_key('e')
            end = time.time() + 2.0
            while self.running and time.time() < end:
                if self.dialogue_visible():
                    self.app.log("Dialogue opened.")
                    return True
                time.sleep(0.15)
        return False

    def reopen_dialogue(self, tries=10):
        """Standing at the wisp: double jump (space, space) then E, until the dialogue shows again.
        Every key waits for its animation first. Returns True once it's open."""
        for _ in range(tries):
            if not self.running or not self.wait_for_roblox_focus():
                return False
            self.utils.send_key('space'); time.sleep(0.35)     # jump
            self.utils.send_key('space'); time.sleep(0.8)      # double jump, then land
            self.utils.send_key('e')
            if self.dialog_mode() == "manual":
                time.sleep(1.0)
                return True                               # manual mode can't see the dialogue: assume it opened
            end = time.time() + 2.0
            while self.running and time.time() < end:
                if self.dialogue_visible():
                    self.app.log("Dialogue open again.")
                    return True
                time.sleep(0.15)
        self.app.log("Couldn't reopen the dialogue here - walking to the wisp again.")
        return False

    def _park_mouse(self):
        """Keep the cursor off the option buttons (it changes how they look)."""
        l, t, r, b = self.get_roblox_window_region()
        self.utils.mouse_move((l + r) // 2, t + int((b - t) * 0.3))

    def run_dialogue(self, move_idx):
        """Click through the dialogue by button position. Returns True once the move was picked.
        Only acts on a menu once it has looked the same for STABLE_SECS (skips fade-in frames).
        Menus are told apart by their text's shape (same text ~0.0-0.08 apart, new text 0.19+)."""
        if self.dialog_mode() != "auto":
            return self.run_dialogue_fixed(move_idx)
        STABLE_SECS = 1.0
        stage, menu1_text = "training", None
        no_panel_since, seen, seen_since = None, None, 0.0
        deadline = time.time() + 30
        self._park_mouse()
        while self.running and time.time() < deadline:
            has_panel, btns, text_img = self.read_dialog(with_text=True)
            if not has_panel:
                no_panel_since = no_panel_since or time.time()
                if time.time() - no_panel_since > 3:
                    self.app.log("-> Dialogue closed unexpectedly.")
                    return False
                time.sleep(0.15)
                continue
            no_panel_since = None
            layout = tuple(y // 8 for _, y in btns)
            if layout != seen:
                seen, seen_since = layout, time.time()
            n = len(btns)
            if time.time() - seen_since < STABLE_SECS:
                time.sleep(0.1)
                continue
            if n <= 1:
                time.sleep(0.1)                         # text still typing: wait for the menu (Skip isn't clicked)
                continue
            elif stage == "moves" and float(np.mean(text_img ^ menu1_text)) < 0.12:
                pass                                    # same text as the first menu: not changed yet
            elif stage == "training":
                target = self.find_training_button()
                if target is None:
                    time.sleep(0.3)                     # not sure which one it is: look again, never guess
                    continue
                (tx, ty), why = target
                self.app.log(f"[1/2] First menu: clicking {why}")
                self.human_click(tx, ty, duration=0.15)
                self._park_mouse()
                time.sleep(self.after_training_wait())  # let the move list fully show before reading it
                stage, menu1_text = "moves", text_img
            else:
                return self.pick_move_button(move_idx)     # picture / name, scrolling if needed
            time.sleep(0.15)
        self.app.log("-> Dialogue timed out.")
        return False

    # ================= Main loop =================
    def main_loop(self):
        from logic_events import WATCHER
        WATCHER.hold("Library")             # event checks only after each minigame
        try:
            self._library_loop()
        finally:
            WATCHER.release("Library")

    def _library_loop(self):
        from logic_events import WATCHER
        while self.running:
            if not self.wait_for_roblox_focus():
                break
            trained = self.check_trained_status()
            to_train = [i for i in range(MAX_MOVES) if not trained[i]]
            if not to_train:
                # Everything selected is maxed: stop the macro (the app stays open) and play a sound
                self.app.log("All selected moves are trained! Macro stopped.")
                self.running = False
                if self.app.settings.get("sound_when_done", False):
                    from utils import play_sound
                    play_sound("done")
                break
            self.current_move_idx = to_train[0]
            if self.in_minigame():
                # Still (or already) in a minigame: play it instead of walking off
                self.app.log("Minigame is running — clicking clovers before walking.")
                self.perform_clover_scoring()
                WATCHER.checkpoint("Library")
                time.sleep(1.0)
                continue
            self.app.log(f"Training {self.move_label(self.current_move_idx)}")

            self.go_to_wisp()
            if not self.running:
                break
            if not self.open_dialogue():
                self.app.log("Couldn't open the wisp dialogue. Trying again from the start...")
                time.sleep(1.0)
                continue
            # The dialogue WAS found. If it closes before the move is picked (Nevermind, a misclick...),
            # we're still at the wisp: stay here, double jump + E until it's back - no walking again.
            done = False
            for attempt in range(3):
                if self.run_dialogue(self.current_move_idx):
                    done = True
                    break
                if not self.running:
                    break
                if self.dialog_mode() != "manual" and self.dialogue_visible():
                    continue                            # still open: just try the dialogue again
                self.app.log("Dialogue closed - staying here: double jump + E until it opens again")
                if not self.reopen_dialogue():
                    break
            if not done:
                time.sleep(1.0)
                continue
            played = self.perform_clover_scoring()
            if played is False and self.running:
                # never saw it start: still at the wisp? pick the move again here instead of walking off
                if self.dialog_mode() != "manual" and self.dialogue_visible():
                    self.app.log("The dialogue is still open - picking the move again.")
                    if self.run_dialogue(self.current_move_idx):
                        played = self.perform_clover_scoring()
                if played is False:
                    self.app.log("No minigame - starting the cycle again.")
                    time.sleep(1.0)
                    continue
            self.app.log("Cycle Complete")
            WATCHER.checkpoint("Library")   # minigame done: safe moment to check chat
            self.handle_ok_popup()
            time.sleep(1.0)

    # ================= Tests =================
    def test_detection(self):
        """F1: what the macro sees right now (dialogue buttons / prompt / minigame)."""
        mode = self.dialog_mode()
        flags = self.train_flags()
        keys = {k: v for k, v in DIALOG_BUTTONS.items() if not k.startswith("move_") or flags[int(k[5:]) - 1]}
        if mode == "image":
            found = [f"{label}: {'FOUND' if self.find_dialog_button(k) else ('not on screen' if self.has_dialog_template(k) else 'no snapshot')}"
                     for k, label in keys.items()]
            self.app.log("Image mode -> " + " | ".join(found))
        elif mode == "manual":
            self.app.log("Manual mode -> " + " | ".join(
                f"{label}: {self.manual_point(k) or 'not set'}" for k, label in keys.items()))
        has_panel, btns = self.read_dialog()
        if has_panel:
            texts = [b[2] or "?" for b in self.dialog_buttons()]
            self.app.log(f"Dialogue open, {len(btns)} button(s) showing: " + " | ".join(texts)
                         + ("   (Nevermind is further down — the list scrolls)" if not any("never" in t.lower() for t in texts) else ""))
        else:
            self.app.log("No dialogue open.")
        s = self.minigame_score()
        self.app.log("Minigame: " + ("no snapshot captured yet (Areas tab)" if s is None else
                     f"{'YES' if s >= float(self.app.settings.get('minigame_threshold', 0.8)) else 'no'} (match {s:.2f})"))

    def test_scroll(self):
        """With the wisp's move list open: read the buttons, scroll ONE notch, read them again."""
        if not self.wait_focus_for_test():
            return
        before = self.dialog_buttons()
        if not before:
            self.app.log("Test scroll: no dialogue buttons on screen — open the wisp's move list first.")
            return
        names = lambda bs: " | ".join(b[2] or "?" for b in bs)
        self._scroll_list(before)
        after = self.dialog_buttons()
        moved = [b[2] for b in before] != [b[2] for b in after]
        self.app.log(f"Test scroll: before: {names(before)}  →  after: {names(after)}  "
                     + ("the list scrolled" if moved else "nothing changed (already at the bottom, or scrolling "
                                                           "doesn't reach the list)"))

    # ---------- Auto setup: hotbar names -> wisp move list -> 'Moves to train' ----------
    @staticmethod
    def _norm_name(t):
        return "".join(ch for ch in (t or "").lower() if ch.isalnum())

    def read_hotbar_names(self, only_slots=None):
        """[(hotbar slot number, text read on it)] for the FILLED slots of the Roblox window in front
        (only `only_slots` when given - Auto setup passes the ticked moves' slots; an empty one reads '')."""
        from logic_smart import SmartMacroLogic
        try:
            import pywinctl
            win = pywinctl.getActiveWindow()
        except Exception:
            win = None
        if not win or not is_roblox_title(win.title):
            return None
        reg = [win.left, win.top, win.left + win.width, win.top + win.height]
        img = self.utils.capture_screen_bgr(reg)
        slots = SmartMacroLogic.find_hotbar_slots(img) if img is not None else []
        out = []
        for n, (x, y, w, side, filled) in enumerate(slots, start=1):
            if only_slots is not None and n not in only_slots:
                continue
            if not filled:
                if only_slots is not None:
                    out.append((n, ""))               # ticked but empty: say so in the confirmation
                continue
            m = max(2, w // 14)
            box = [reg[0] + x + m, reg[1] + y + m, reg[0] + x + w - m, reg[1] + y + side - m]
            lines = self.utils.get_text_from_region(box, upscale=3)
            lines.sort(key=lambda r: min(p[1] for p in r[0]))
            out.append((n, " ".join(t for _, t, c in lines if c > 0.3).strip()))
        return out

    @staticmethod
    def _same_picture(a, b):
        """Two button pictures of the same move (it was seen again after scrolling)?"""
        try:
            if a is None or b is None or not a.size or not b.size:
                return False
            ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
            gb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (ga.shape[1], ga.shape[0]))
            return float(cv2.matchTemplate(ga, gb, cv2.TM_CCOEFF_NORMED).max()) >= 0.93
        except Exception:
            return False

    def scan_move_list(self, alive=lambda: True):
        """With the wisp's MOVE LIST open: read every button top to bottom, scrolling down until Nevermind.
        Returns [(name, picture)] in list order (picture = BGR crop of the button, for Image mode)."""
        found, seen_names, still = [], set(), 0
        for _ in range(MAX_MOVES + 4):
            if not alive():
                break
            if not self.wait_move_list(alive=alive):
                break                                    # list never showed (still typing / closed)
            win = self.get_roblox_window_region()
            img = self._screen()
            panel, boxes = self.find_dialog(img)
            if not boxes:
                time.sleep(0.5)
                continue
            new, centers, never = 0, [], False
            for (x, y, w, h), text in zip(boxes, self._read_button_texts(win, boxes, img.shape[0], img)):
                text = text.strip()
                centers.append((win[0] + x + w // 2, win[1] + y + h // 2, text))
                if "never" in text.lower():
                    never = True
                    continue
                if self._is_skip(text):
                    continue
                if self._has_word(text, self.TRAINING_WORDS) or self._has_word(text, self.NEVER_WORDS):
                    continue                             # first menu (Clover Training / Class Reset): not a move
                pic = img[y:y + h, x:x + w].copy()
                if any(self._same_picture(pic, p) for _, p in found):
                    continue                             # the same button again (list scrolled)
                key = self._norm_name(text)
                if not key:
                    continue
                if key in seen_names:
                    # a DIFFERENT button that read the same (e.g. small text lost a word: 'Cage' Gates vs Gates):
                    # read just this button again, bigger, to get its real name
                    again = self._ocr_button(pic)
                    if self._norm_name(again) and self._norm_name(again) not in seen_names:
                        text, key = again, self._norm_name(again)
                    else:
                        text = f"{text} (#{sum(1 for n, _ in found if self._norm_name(n).startswith(key)) + 1})"
                        key = self._norm_name(text)      # keep it as its own move; the picture tells them apart
                seen_names.add(key)
                found.append((text, pic))
                new += 1
            if never:
                break
            still = still + 1 if new == 0 else 0
            if still >= 2:
                break                                # list stopped moving
            self._scroll_list(centers)
        return found

    @staticmethod
    def _words(text):
        import re
        return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower().replace("'", "")) if w]

    @classmethod
    def unique_keyword(cls, name, all_names):
        """The one word of `name` that no other move-list name has (longest first), or None.
        'Sovereign Magic: Cage Gates' among the Sovereign Magic moves -> 'cage'."""
        import difflib
        others = [w for n in all_names if n != name for w in cls._words(n)]
        cands = [w for w in cls._words(name) if len(w) >= 3]
        unique = [w for w in cands if not any(difflib.SequenceMatcher(None, w, o).ratio() >= 0.8 for o in others)]
        return max(unique, key=len) if unique else None

    def match_hotbar_to_list(self, hotbar, names):
        """The MOVE LIST leads; the hotbar only says which slot holds which move.
        Each move-list name gets a unique keyword; each hotbar slot is matched to the move whose keyword (or
        full name) fits what the hotbar shows, best pairs first, every move used once.
        Returns [{'slot', 'hotbar', 'match', 'keyword', 'score', 'suggest'}]."""
        import difflib
        keys = {n: self.unique_keyword(n, names) for n in names}

        def close(a, b):
            return difflib.SequenceMatcher(None, a, b).ratio()

        # words two or more moves share ('sovereign', 'magic', 'gates' - misreads like 'sovercign' too)
        # tell nothing apart: drop them and compare ONLY what's left - each move's unique word
        all_words = [set(self._words(n)) for n in names]
        shared = {w for i, ws in enumerate(all_words) for w in ws
                  if any(close(w, o) >= 0.8 for j, os_ in enumerate(all_words) if j != i for o in os_)}

        def leftover(text):
            return [t for t in self._words(text) if not any(close(t, w) >= 0.8 for w in shared)]

        def score(hot, name):
            if not self._norm_name(hot):
                return 0.0
            left, k = leftover(hot), keys.get(name)
            if not left:
                # the hotbar shows only shared words -> the move WITHOUT a unique word ('Sovereign Magic: Gates')
                if k:
                    return 0.3
                return 0.6 + 0.4 * close(self._norm_name(hot), self._norm_name(name))
            if not k:
                return 0.3                    # the hotbar has an extra word this move doesn't have
            best = 0.0
            for t in left:
                r = close(t, k)
                if len(t) >= 3 and len(k) >= 3 and t[:2] == k[:2]:
                    r = max(r, 0.7)           # 'cagt' / 'cate' / 'cag' for 'cage': same start, a letter misread
                if k.startswith(t):
                    r = max(r, 0.6 + 0.4 * len(t) / len(k))   # cut off on the hotbar: 'C' / 'Ca' for 'cage'
                best = max(best, r)
            return best

        pairs = sorted(((score(t, n), slot, n) for slot, t in hotbar for n in names), reverse=True)
        chosen, used = {}, set()
        for sc, slot, n in pairs:
            if slot in chosen or n in used or sc < 0.5:
                continue
            chosen[slot] = (n, sc)
            used.add(n)
        rows = []
        for slot, text in hotbar:
            n, sc = chosen.get(slot, ("", 0.0))
            ranked = [m for _, sl, m in pairs if sl == slot and (m == n or m not in used)]
            rows.append({"slot": slot, "hotbar": text, "match": n, "keyword": keys.get(n) if n else None,
                         "score": round(sc, 2), "suggest": list(dict.fromkeys(ranked))[:3]})
        self._auto_keys = keys
        return rows

    def reset_move_gold(self, i):
        """A slot got a DIFFERENT move: its 'gold used' starts again from 0 (the total keeps counting)."""
        stats = self._nine("move_stats", 0)
        if 0 <= i < len(stats) and stats[i]:
            stats[i] = 0
            self.app.settings.set("move_stats", stats)

    def apply_auto_setup(self, rows, pictures):
        """rows: [{'slot', 'name', 'train'}] in the order to train. Fills 'Moves to train' (names, slots,
        ticks) and, in Image mode, saves each chosen move's button picture."""
        names = self._nine("move_names", "")
        slots = self._nine("gold_move_slots", lambda k: k + 1)
        flags = self._nine("train_moves", False)
        if not any("move" in r for r in rows):           # old behaviour: fill from the top, clear the rest
            for i in range(MAX_MOVES):
                names[i], flags[i] = "", False
        keys = getattr(self, "_auto_keys", {})
        for n, r in enumerate(rows[:MAX_MOVES]):
            i = int(r.get("move", n))                  # the ticked Move row this hotbar slot belongs to
            word = r.get("keyword") or keys.get(r["name"])
            new = word.capitalize() if word else r["name"]   # one unique word - easy for the reader
            if self._norm_name(new) != self._norm_name(names[i]):
                self.reset_move_gold(i)                  # a different move in this slot: its gold starts at 0
            names[i] = new
            slots[i], flags[i] = int(r["slot"]), bool(r["train"])
            pic = pictures.get(r["name"])
            note = ""
            if self.dialog_mode() == "image":
                if pic is not None and pic.size:
                    os.makedirs(DIALOG_TEMPLATE_DIR, exist_ok=True)
                    note = (" - picture saved" if cv2.imwrite(self.dialog_template_path(f"move_{i + 1}"), pic)
                            else " - picture COULDN'T be saved")
                else:
                    note = " - no picture of it (old picture kept)"
            self.app.log(f"Auto setup: Move {i + 1} (slot {slots[i]}) = '{r['name']}' -> looks for '{names[i]}'{note}")
        self.app.settings.save()

    def _test_manual_spots(self, walk, result, say):
        """Manual mode test: no pictures, no reading - just your spots. Full test (walk=True) walks, presses E
        and clicks your Clover Training spot; then (both tests) the mouse HOVERS each ticked move spot."""
        if self.running:
            say("Stop the macro first."); return result
        ct = self.manual_point("clover_training")
        spots = [(i, self.manual_point(f"move_{i + 1}")) for i, m in enumerate(self.manual_moves()) if m.get("train")]
        if walk and not ct:
            say("Clover Training: no spot set - Pick spot in Wisp dialogue."); return result
        if not spots:
            say("Tick at least one Move spot in Wisp dialogue first."); return result
        if not self.wait_focus_for_test():
            return result
        self.running = True
        try:
            if walk:
                self.app.log("--- Full test (Manual): walking to the wisp ---")
                self.go_to_wisp()
                if not self.running or not self.open_dialogue():
                    say("Couldn't open the wisp's dialogue."); return result
                time.sleep(float(self.app.settings.get("dialog_wait", 1.5)))
                self.app.log("Clicking your Clover Training spot")
                self.human_click(*ct, duration=0.15)
                self._park_mouse()
                time.sleep(self.after_training_wait())
                say(f"Clover Training: clicked your spot {ct}")
            for i, pt in spots:
                if not self.running:
                    break
                if not pt:
                    say(f"Move spot {i + 1}: no spot set - Pick spot in Wisp dialogue")
                    continue
                self.utils.mouse_move(*pt)
                time.sleep(0.9)
                say(f"Move spot {i + 1}: hovered {pt} - check the mouse was on the right move")
        finally:
            self.running = False
        result["ok"] = all(pt for _, pt in spots)
        say("Nothing was clicked except Clover Training." if walk else "Nothing was clicked.")
        return result

    def test_find_moves(self, walk=False):
        """Dry run of the move search: go down the move list ONCE and only HOVER each ticked move it finds
        (never clicks a move). walk=False (F4): the move list must already be open - no walking, no clicks.
        walk=True (full test, F5): walk the route, open the dialogue and click Clover Training first.
        Returns a result dict: {'lines': [...], 'ok': bool} - also logged."""
        mode = self.dialog_mode()
        result = {"lines": [], "ok": False}
        say = lambda m: (result["lines"].append(m), self.app.log(m))
        if mode == "manual":
            return self._test_manual_spots(walk, result, say)
        if self.running:
            say("Stop the macro first."); return result
        if not self.wait_focus_for_test():
            return result
        flags = self.train_flags()
        wanted = [i for i in range(MAX_MOVES) if flags[i]]
        if not wanted:
            say("Tick at least one move in 'Moves to train' first."); return result
        self.running = True
        seen = []                                    # every button text read on the way (for suggestions)
        found = {}                                   # move index -> how it was found
        try:
            if not walk:
                self.app.log("--- Find moves (test): reading the open move list (no walking, no clicks) ---")
                if not self.wait_move_list(timeout=4) and not (mode == "image" and self._any_move_picture(wanted)):
                    if mode != "image":
                        say("No move list on screen. Open the wisp's move list first - "
                            "or use the Full test, which walks there and opens it.")
                        return result
                    self.app.log("   No buttons detected - searching by picture only.")
            else:
                self.app.log("--- Full test: walking to the wisp ---")
                self.go_to_wisp()
                if not self.running or not self.open_dialogue():
                    say("Couldn't open the wisp's dialogue (are you at the wisp?)."); return result
                # first menu -> Clover Training (this one IS clicked, it's the only way to reach the move list)
                deadline = time.time() + 20
                target = None
                while self.running and time.time() < deadline and not target:
                    if mode == "image" and self.has_dialog_template("clover_training"):
                        pt = self.find_dialog_button("clover_training")
                        target = (pt, "picture") if pt else None
                    else:
                        t = self.find_training_button()
                        target = t if t else None
                    if not target:
                        time.sleep(0.4)
                if not target:
                    say("Couldn't find 'Clover Training' in the first menu."); return result
                self.human_click(*target[0], duration=0.15)
                self._park_mouse()
                time.sleep(self.after_training_wait())  # move list fades in
            for step in range(MAX_MOVES + 3):
                if not self.running:
                    break
                buttons = self.wait_move_list(timeout=4 if mode == "image" else 12)
                if not buttons and mode != "image":
                    say("The move list didn't show up (only 'Skip' while the text was typing?) - try again.")
                    break
                seen.extend(b[2] for b in buttons if b[2] and b[2] not in seen and not self._is_skip(b[2]))
                for i in wanted:
                    if i in found:
                        continue
                    key, name = f"move_{i + 1}", self.move_names()[i]
                    pt, how = None, ""
                    pic = mode == "image" and self.has_dialog_template(key)
                    if pic:
                        pt = self.find_dialog_button(key); how = "picture"
                    at_end = any("never" in (b[2] or "").lower() for b in buttons)
                    # the picture leads; the name is only tried once the whole list was checked for the picture
                    if not pt and name and (not pic or at_end):
                        hit = self._best_name_hit(name, buttons)
                        if hit:
                            pt, how = (hit[0], hit[1]), (f"name '{hit[2]}' (picture not found)" if pic
                                                         else f"name '{hit[2]}'")
                    if pt:
                        found[i] = how
                        self.app.log(f"   {self.move_label(i)} found ({how}) - hovering, not clicking")
                        self.utils.mouse_move(*pt)
                        time.sleep(0.9)
                if all(i in found for i in wanted):
                    break
                if any("never" in (b[2] or "").lower() for b in buttons):
                    break                            # Nevermind is always last: end of the list
                self._scroll_list(buttons or self._list_anchor())
        finally:
            self.running = False
        import difflib
        for i in wanted:
            label = self.move_label(i)
            if i in found:
                say(f"{label}: found by {found[i]}")
                continue
            name = self.move_names()[i]
            has_pic = self.has_dialog_template(f"move_{i + 1}")
            if not name and not has_pic:
                say(f"{label}: no name{' or picture' if mode == 'image' else ''} set - nothing to look for")
                continue
            line = f"{label}: not found"
            options = [t for t in seen if t and "never" not in t.lower() and not self._is_skip(t)]
            close = difflib.get_close_matches(name, options, n=2, cutoff=0.35) if name else []
            if close:
                line += "  →  did you mean: " + " / ".join(f"'{c}'" for c in close) + " ?"
            elif options:
                line += "  (saw: " + ", ".join(f"'{t}'" for t in options[:6]) + ")"
            if mode == "image" and not has_pic:
                line += "  - no picture captured, so only the name was tried"
            say(line)
        result["ok"] = all(i in found for i in wanted)
        say("All ticked moves were found." if result["ok"] else "Some moves weren't found - see above.")
        self.app.log("(The dialogue was left open - nothing else was clicked.)")
        return result

    def test_path(self):
        """Walk to the wisp only (no dialogue)."""
        if self.running:
            self.app.log("Stop the macro before testing the path.")
            return
        if not self.wait_focus_for_test():
            return
        self.app.log(f"--- Test Path: walking to the wisp (route '{self.active_route() or 'none'}') ---")
        self.running = True
        try:
            self.go_to_wisp()
            self.app.log("Arrived at the end of the recorded path.")
        except Exception as e:
            self.app.log(f"Test Path error: {e}")
        finally:
            self.running = False

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

    def minigame_start_wait(self):
        """How long to wait for the minigame to show up after picking a move (editable, default 30 s)."""
        try:
            return max(5.0, float(self.app.settings.get("minigame_start_wait", 30)))
        except (TypeError, ValueError):
            return 30.0

    def perform_clover_scoring(self):
        """Wait until the minigame is SEEN, then click clovers until it's gone. Returns False if it never
        started (nothing was played), True once a minigame was played."""
        settings = self.app.settings.settings
        region = settings["regions"]["score"]  
        clover_colors = settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        global_tolerance = settings.get("color_tolerance", 15)
        clover_tols = settings.get("clover_tolerances", {})

        session_stats = {"gold": 0, "silver": 0, "bronze": 0, "total_clicks": 0}
        self.minigame_running = True
        
        if all(v == 0 for v in region):
            # No Clover Region set: use the middle of the game view
            l, t, r, b = self.get_roblox_window_region()
            h = b - t
            region = [l, t + int(h * 0.10), r, t + int(h * 0.90)]

        # The minigame must be SEEN first (a few checks in a row, so a flash doesn't count) - only then can
        # 'it's gone' mean it ended. Until it has been seen, nothing is decided and nothing is clicked.
        limit = self.minigame_start_wait()
        self.app.log(f"Waiting for the minigame to start (up to {limit:g} s)...")
        start_wait, seen = time.time(), 0
        while self.running:
            if not self.wait_for_roblox_focus():
                self.minigame_running = False
                return False
            seen = seen + 1 if self.in_minigame() else 0
            if seen >= 3:
                self.app.log("Minigame started.")
                self.toggle_chat("hide")
                break
            if time.time() - start_wait > limit:
                self.app.log(f"The minigame didn't start within {limit:g} s - the move probably wasn't picked.")
                self.minigame_running = False
                return False
            time.sleep(0.15)
        if not self.running:
            self.minigame_running = False
            return False

        def end_detector():
            gone_since = None
            while self.running and self.minigame_running:
                time.sleep(0.25)
                try:
                    if self.in_minigame():
                        gone_since = None
                    elif gone_since is None:
                        gone_since = time.time()
                    elif time.time() - gone_since >= 2.0:   # snapshot gone for 2s (ignores flashes)
                        self.app.log("Minigame ended.")
                        self.minigame_running = False
                        break
                except Exception:
                    pass

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

        self.minigame_running = False
        self.toggle_chat("show")
        new_gold = self.app.settings.get("total_gold", 0) + 250
        self.app.settings.set("total_gold", new_gold)
        move_stats = self._nine("move_stats", 0)
        if hasattr(self, "current_move_idx"):
            move_stats[self.current_move_idx] += 250
            self.app.settings.set("move_stats", move_stats)
        self.app.root.after(0, self.app.update_gold_display)
        return True

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
