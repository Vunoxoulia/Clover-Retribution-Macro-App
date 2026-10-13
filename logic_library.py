import os
import time
import threading
import math
import keyboard
import numpy as np
import cv2
from route_nav import RouteNav
from utils import RobloxInputDriver
from settings import get_base_path

DIALOG_TEMPLATE_DIR = os.path.join(get_base_path(), "library_templates")
DIALOG_MODES = ("auto", "image", "manual")
# Settings key per dialogue button (manual spots reuse the old "positions" entries)
MAX_MOVES = 9          # one per hotbar slot; the wisp's list is these 9 + Nevermind (always last)
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
        """Settings list padded to MAX_MOVES (older setups had 3)."""
        st = self.app.settings.settings
        lst = list(st.get(key) or [])
        for i in range(len(lst), MAX_MOVES):
            lst.append(fill(i) if callable(fill) else fill)
        st[key] = lst[:MAX_MOVES]
        return st[key]

    def move_names(self):
        return self._nine("move_names", "")

    def train_flags(self):
        if not self.app.settings.get("train_moves"):
            names = self.move_names()
            self.app.settings.settings["train_moves"] = ([bool(n) for n in names] if any(names)
                                                         else [i < 3 for i in range(MAX_MOVES)])
        return list(self._nine("train_moves", False))

    def move_label(self, i):
        name = self.move_names()[i]
        return f"Move {i + 1}" + (f" ({name})" if name else "")

    # ---------- Gold clover: automatic (from the hotbar) or manual boxes ----------
    # The 3 clovers sit in a row on top of each hotbar icon; the 3rd is always in the same spot:
    # measured at ~78% across the icon (the 2nd is at ~46%), in the top part of a box that starts
    # at the top of the clovers (top ~18% = above the clover row line). A move is trained once that spot is gold.
    THIRD_X = (0.68, 0.90)
    THIRD_Y = (0.0, 0.18)                       # just the clover row, not the gold icon border below it
    GOLD_SHARE = 0.15                               # empty spot reads ~0, a gold clover ~0.2-0.25
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
        if not win or "Roblox" not in win.title:
            self.app.log("Auto-find: click into the Roblox window first.")
            return None
        reg = [win.left, win.top, win.left + win.width, win.top + win.height]
        img = self.utils.capture_screen_bgr(reg)
        slots = SmartMacroLogic.find_hotbar_slots(img) if img is not None else []
        filled = max((i for i, s in enumerate(slots, start=1) if s[4]), default=0)
        if not filled:
            self.app.log("Auto-find: couldn't see the hotbar - drag it with 🔲 Set hotbar instead.")
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
        return int(self._nine("gold_move_slots", lambda k: k + 1)[i])

    def third_clover_rect(self, slot):
        """Screen box of the 3rd-clover spot of hotbar slot 1..n (None if the hotbar isn't set)."""
        r, n = self.gold_hotbar()
        if not r or not 1 <= slot <= n:
            return None
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
        # Saturation >= 160: the clover's gold is strong (~210); the move NAME text is a pale gold (~120)
        # that used to count too when it reached into the box.
        gold = cv2.inRange(cv2.cvtColor(img, cv2.COLOR_BGR2HSV), self.GOLD_HSV_LO, self.GOLD_HSV_HI)
        return float((gold > 0).mean())

    def move_is_gold(self, i):
        if self.gold_mode() == "auto":
            share = self.third_clover_share(self.move_slot(i))
            return share is not None and share >= self.GOLD_SHARE
        area = self.app.settings.get("regions", {}).get(f"gold_clover_{i + 1}", [0, 0, 0, 0])
        return any(v != 0 for v in area) and self.utils.check_pixel_area(area, self.GOLD_CLOVER_COLOR, tolerance=25)

    def check_trained_status(self):
        """A move is done when its 3rd clover is gold (automatic: read from the hotbar; manual: its own box)."""
        flags = self.train_flags()
        trained = [not f for f in flags]
        for i in range(MAX_MOVES):
            if trained[i]:
                continue
            if self.move_is_gold(i):
                self.app.log(f"{self.move_label(i)} is already trained (Gold Clover detected).")
                trained[i] = True
        return trained

    # ================= Getting to the wisp =================
    def go_to_wisp(self):
        route = self.load_route()
        if not route:
            self.app.log("No recorded route to the wisp - using the old D/S/W walk. (Record one with Ctrl+P.)")
            self.perform_approach_movement()
            return
        # New recordings: the whole walk is one piece ('return'). Old ones: the walk up to the first E.
        seg = route["segments"][0] if route["segments"] else route["return"]
        self.align_home()
        self.app.log(f"Walking to the wisp (route '{self.active_route()}')...")
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
        if not panel:
            return None, []
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
        return panel, sorted(buttons, key=lambda b: b[1])

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
                self.app.log("Minigame detector: no snapshot yet — Areas tab → 🎮 Minigame detector → Capture.")
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

    def run_dialogue_fixed(self, move_idx):
        """Image / Manual mode: click Clover Training, then the move's button."""
        mode = self.dialog_mode()
        wait = float(self.app.settings.get("dialog_wait", 1.5))
        steps = [("clover_training", "Clover Training"), (f"move_{move_idx + 1}", self.move_label(move_idx))]
        self._park_mouse()
        for n, (key, label) in enumerate(steps, start=1):
            if n == 2 and mode == "image":
                self._skip_typing(0.6)
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

    def dialog_buttons(self):
        """[(x, y, text)] of the option buttons on screen, top to bottom (text read with OCR)."""
        win = self.get_roblox_window_region()
        img = self._screen()
        panel, boxes = self.find_dialog(img)
        if not boxes:
            return []
        x1 = min(b[0] for b in boxes); y1 = min(b[1] for b in boxes)
        x2 = max(b[0] + b[2] for b in boxes); y2 = max(b[1] + b[3] for b in boxes)
        found = self.utils.get_text_from_region([win[0] + x1, win[1] + y1, win[0] + x2, win[1] + y2])
        out = []
        for x, y, w, h in boxes:
            cy = y + h / 2 - y1
            text = " ".join(t for bb, t, c in found if abs((bb[0][1] + bb[2][1]) / 2 - cy) < h * 0.6)
            out.append((win[0] + x + w // 2, win[1] + y + h // 2, text))
        return out

    @staticmethod
    def _same_name(a, b):
        a = "".join(ch for ch in a.lower() if ch.isalnum())
        b = "".join(ch for ch in b.lower() if ch.isalnum())
        if not a or not b:
            return False
        import difflib
        return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.8

    def _scroll_list(self, buttons, notches=-1):
        """One mouse-wheel notch down over the button column."""
        from pynput.mouse import Controller as MouseController
        x, y = buttons[len(buttons) // 2][:2]
        with self.input_lock:
            self.utils.mouse_move(x, y)
            time.sleep(0.1)
            MouseController().scroll(0, notches)
        time.sleep(0.6)                                 # let the list settle
        self._park_mouse()
        time.sleep(0.2)

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
            buttons = self.dialog_buttons()
            if not buttons:
                time.sleep(0.4)
                continue
            if name:
                hit = next((b for b in buttons if self._same_name(name, b[2])), None)
                if hit:
                    self.app.log(f"[2/2] Found {label} (name) - clicking")
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
            if not self.run_dialogue(self.current_move_idx):
                time.sleep(1.0)
                continue
            self.perform_clover_scoring()
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
                     + ("✔ the list scrolled" if moved else "✖ nothing changed (already at the bottom, or scrolling "
                                                           "doesn't reach the list)"))

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

    def perform_clover_scoring(self):
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

        self.app.log("Waiting for the minigame to start...")
        start_wait = time.time()
        while self.running:
            if not self.wait_for_roblox_focus(): return
            if self.in_minigame():
                self.app.log("Minigame started.")
                self.toggle_chat("hide")
                break
            if time.time() - start_wait > 20:
                self.app.log("Timeout waiting for minigame start.")
                return
            time.sleep(0.15)

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
