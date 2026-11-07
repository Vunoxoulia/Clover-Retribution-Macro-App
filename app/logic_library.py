import os
import time
import threading
import math
import numpy as np
import cv2
from route_nav import RouteNav
from utils import RobloxInputDriver, is_roblox_title
from settings import get_base_path

DIALOG_TEMPLATE_DIR = os.path.join(get_base_path(), "library_templates")
DIALOG_MODES = ("image", "manual")
MAX_MOVES = 9
MANUAL_MOVES = 3
DIALOG_BUTTONS = {"clover_training": "Clover Training", **{f"move_{i}": f"Move {i}" for i in range(1, MAX_MOVES + 1)}}


class LibraryLogic(RouteNav):

    ROUTES_DIRNAME = "routes_library"
    BUILTIN_ROUTE = "VunVun's route"
    BUILTIN_DIR = os.path.join("builtin_routes", "library")
    ACTIVE_ROUTE_KEY = "library_active_route"
    USE_ALIGNMENT = False
    ROUTE_TARGET = "wisp"
    E_MARKS_TARGET = False

    def __init__(self, app):
        super().__init__(app)
        self.current_move_idx = 0
        self.click_history = []
        self.GOLD_CLOVER_COLOR = (250, 171, 33)
        self.DEFAULT_CLOVER_COLORS = {"gold": (255, 180, 51), "silver": (164, 178, 178), "bronze": (198, 62, 37)}
        self.DEFAULT_CLOVER_TOLERANCES = {"gold": 5, "silver": 5, "bronze": 5}

    GOLD_PER_TRAINING = 250
    _gold_lock = threading.Lock()

    def lifetime_gold(self):
        st = self.app.settings
        life = st.get("lifetime_gold")
        if life is None:
            life = max(int(st.get("total_gold", 0) or 0),
                       sum(int(v or 0) for v in (st.get("move_stats") or [])))
        return int(life)

    def spells_gold(self):
        return sum(int(v or 0) for v in self._nine("move_stats", 0)[:self.stats_moves()])

    def stats_moves(self):
        return MAX_MOVES

    def record_gold(self, amount=None):
        amount = self.GOLD_PER_TRAINING if amount is None else amount
        st = self.app.settings
        with self._gold_lock:
            st.settings["lifetime_gold"] = self.lifetime_gold() + amount
            st.settings["total_gold"] = int(st.get("total_gold", 0) or 0) + amount
            stats = self._nine("move_stats", 0)
            i = getattr(self, "current_move_idx", None)
            if isinstance(i, int) and 0 <= i < len(stats):
                stats[i] = int(stats[i] or 0) + amount
            st.save()
        try:
            self.app.root.after(0, self.app.update_gold_display)
        except Exception:
            pass

    def reset_spells_gold(self, i=None):
        st = self.app.settings
        with self._gold_lock:
            st.settings.setdefault("lifetime_gold", self.lifetime_gold())
            stats = self._nine("move_stats", 0)
            for k in (range(len(stats)) if i is None else [i]):
                if 0 <= k < len(stats):
                    stats[k] = 0
            st.save()

    def _nine(self, key, fill):
        st = self.app.settings.settings
        lst = st.get(key)
        if not isinstance(lst, list):
            lst = st[key] = []
        for i in range(len(lst), MAX_MOVES):
            lst.append(fill(i) if callable(fill) else fill)
        del lst[MAX_MOVES:]
        return lst

    def set_move_slot(self, i, slot):
        self._nine("gold_move_slots", lambda k: k + 1)[i] = int(slot)
        self.app.settings.save()

    def move_names(self):
        return self._nine("move_names", "")

    def manual_moves(self):
        st = self.app.settings.settings
        lst = st.get("manual_moves")
        if not isinstance(lst, list):
            lst = st["manual_moves"] = []
        for i in range(len(lst), MANUAL_MOVES):
            lst.append({"train": i == 0, "slot": i + 1})
        del lst[MANUAL_MOVES:]
        return lst

    def train_flags(self):
        if self.dialog_mode() == "manual":
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

    THIRD_X = (0.68, 0.90)
    THIRD_Y = (0.0, 0.18)
    GOLD_SHARE = 0.05
    GOLD_HSV_LO, GOLD_HSV_HI = (10, 160, 170), (30, 255, 255)

    def gold_mode(self):
        return "manual" if self.app.settings.get("gold_mode") == "manual" else "auto"

    def gold_hotbar(self):
        hb = self.app.settings.get("gold_hotbar") or {}
        r = hb.get("region", [0, 0, 0, 0])
        return (r, max(1, int(hb.get("slots", 6)))) if r[2] > r[0] and r[3] > r[1] else (None, 0)

    CLOVER_ROW = 1.13

    def auto_find_gold_hotbar(self):
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
        cy = self._clover_row_y(img, slots)
        if cy is not None:
            top_img = (cy - self.THIRD_Y[1] / 2 * bottom_img) / (1 - self.THIRD_Y[1] / 2)
        else:
            top_img = bottom_img - side * self.CLOVER_ROW
        hb = self.app.settings.settings.setdefault("gold_hotbar", {})
        hb["region"] = [reg[0] + slots[0][0], reg[1] + int(round(top_img)), reg[0] + last[0] + last[2],
                        reg[1] + bottom_img]
        hb["slots"] = filled
        hb["spots"] = [self.corner_spot(reg[0] + x, reg[1] + y, w, s) for x, y, w, s, _ in slots[:filled]]
        self.app.settings.save()
        self.app.log(f"Auto-find: hotbar found, {filled} filled slot(s). Press Show to check the yellow boxes.")
        return filled

    @staticmethod
    def _clover_row_y(img, slots):
        side, top = slots[0][3], slots[0][1]
        y1, y2 = max(0, int(top - side * 0.3)), int(top + side * 0.25)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        prof = np.zeros(max(0, y2 - y1))
        for x, _, w, _, filled in slots:
            if not filled:
                continue
            band = hsv[y1:y2, x + int(w * 0.55):x + int(w * 0.98)]
            prof += ((band[:, :, 0] >= 8) & (band[:, :, 0] <= 32) & (band[:, :, 1] >= 160)
                     & (band[:, :, 2] >= 170)).sum(axis=1)
        if not prof.size or prof.max() < 3:
            return None
        return float((prof * np.arange(y1, y2)).sum() / prof.sum())

    def move_slot(self, i):
        if self.dialog_mode() == "manual" and i < MANUAL_MOVES:
            return int(self.manual_moves()[i].get("slot") or i + 1)
        return int(self._nine("gold_move_slots", lambda k: k + 1)[i])

    CORNER_X = (0.71, 0.96)
    CORNER_Y = (-0.12, 0.15)

    @classmethod
    def corner_spot(cls, x, top, w, side):
        return [int(x + cls.CORNER_X[0] * w), int(top + cls.CORNER_Y[0] * side),
                int(x + cls.CORNER_X[1] * w), int(top + cls.CORNER_Y[1] * side)]

    def third_clover_rect(self, slot):
        r, n = self.gold_hotbar()
        if not r or not 1 <= slot <= n:
            return None
        spots = (self.app.settings.get("gold_hotbar") or {}).get("spots") or []
        if slot <= len(spots):
            return list(spots[slot - 1])
        sw, h = (r[2] - r[0]) / n, r[3] - r[1]
        x = r[0] + (slot - 1) * sw
        return [int(x + self.THIRD_X[0] * sw), int(r[1] + self.THIRD_Y[0] * h),
                int(x + self.THIRD_X[1] * sw), int(r[1] + self.THIRD_Y[1] * h)]

    def third_clover_share(self, slot):
        rect = self.third_clover_rect(slot)
        if not rect:
            return None
        img = self.utils.capture_screen_bgr(rect)
        if img is None or not img.size:
            return None
        return float((self.gold_mask(img) > 0).mean())

    GOLD_TOL = 8

    def _color_mask(self, img_bgr, rgb):
        c = np.array([int(v) for v in rgb[:3][::-1]])
        return cv2.inRange(img_bgr, np.clip(c - self.GOLD_TOL, 0, 255).astype(np.uint8),
                           np.clip(c + self.GOLD_TOL, 0, 255).astype(np.uint8))

    def gold_mask(self, img_bgr):
        own = self.app.settings.get("gold_color")
        if own:
            return self._color_mask(img_bgr, own)
        lo = (int(self.GOLD_HSV_LO[0]) + 3, int(self.GOLD_HSV_LO[1]) + 20, int(self.GOLD_HSV_LO[2]) + 20)
        hi = (int(self.GOLD_HSV_HI[0]) - 3, 255, 255)
        return cv2.inRange(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV), lo, hi)

    def slot_is_gold(self, slot):
        share = self.third_clover_share(slot)
        return share is not None and share >= self.GOLD_SHARE

    def move_is_gold(self, i):
        if self.gold_mode() == "auto":
            return self.slot_is_gold(self.move_slot(i))
        area = self.app.settings.get("regions", {}).get(f"gold_clover_{i + 1}", [0, 0, 0, 0])
        if not any(v != 0 for v in area):
            return False
        img = self.utils.capture_screen_bgr(area)
        if img is None or not img.size:
            return False
        if not self.app.settings.get("gold_color"):
            mask = self._color_mask(img, self.GOLD_CLOVER_COLOR)
        else:
            mask = self.gold_mask(img)
        return float((mask > 0).mean()) >= self.GOLD_SHARE

    def usable_moves(self):
        return MANUAL_MOVES if self.dialog_mode() == "manual" else MAX_MOVES

    def check_trained_status(self):
        flags = self.train_flags()
        trained = [not f for f in flags]
        limit = self.usable_moves()
        skipped = [i for i in range(limit, MAX_MOVES) if not trained[i]]
        if skipped and not getattr(self, "_warned_manual_limit", False):
            self.app.log(f"Manual dialogue only reaches Moves 1-{MANUAL_MOVES} (no scrolling) - skipping "
                         + ", ".join(f"Move {i + 1}" for i in skipped) + ". Use Image for those.")
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

    def go_to_wisp(self):
        route, name = self.load_route(), self.active_route()
        if not route:
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
        seg = route["segments"][0] if route["segments"] else route["return"]
        self.align_home()
        self.handle_ok_popup()
        self.app.log(f"Walking to the wisp (route '{name}')...")
        self.play_segment(seg, label="wisp")
        self._wait_still()

    def perform_approach_movement(self):
        for key, secs in (("d", 2.0), ("s", 2.0), ("w", 3.0)):
            if not self.running:
                return
            self.app.log(f"Approaching NPC area (Holding {key.upper()})...")
            self.hold_key(key, secs)

    def find_dialog(self, img):
        return self.find_dialog_at(img, getattr(self, "_ui_scale", None))

    UI_REF = (1919, 1040)

    @classmethod
    def find_dialog_at(cls, img, ui=None):
        H, W = img.shape[:2]
        y0 = int(H * 0.55)
        g = cv2.cvtColor(img[y0:], cv2.COLOR_BGR2GRAY)
        bgr = img[y0:].astype(np.int16)
        hovered = (bgr[..., 1] > bgr[..., 2] + 25) & (bgr[..., 1] > bgr[..., 0] + 15)
        dark = ((g < 75) | hovered).astype(np.uint8) * 255
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, _, st, _ = cv2.connectedComponentsWithStats(dark)
        found = cls._dialog_by_size(y0, n, st, W, H)
        tries = [(min(W, H * 16 / 9), H)] if W > H * 16 / 9 else []
        if ui:
            tries.append((cls.UI_REF[0] * ui, cls.UI_REF[1] * ui))
        for sw, sh in tries:
            if found[1]:
                break
            again = cls._dialog_by_size(y0, n, st, sw, sh)
            if again[1]:
                found = again
        return found

    @staticmethod
    def _dialog_by_size(y0, n, st, W, Hs):
        panel = None
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if w > W * 0.2 and h > Hs * 0.12 and a > w * h * 0.5:
                panel = (x, y + y0, w, h)
        def column_fallback():
            cands = [(int(x), int(y) + y0, int(w), int(h)) for x, y, w, h, a in st[1:]
                     if W * 0.06 < w < W * 0.16 and Hs * 0.02 < h < Hs * 0.07 and a > w * h * 0.35]
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
            return (max(0, bx - 12), top, 1, bottom - top)

        def buttons_next_to(panel):
            px, py, pw, ph = panel
            parts = []
            for i in range(1, n):
                x, y, w, h, a = st[i]
                y += y0
                if px + pw < x < px + pw + W * 0.16 and Hs * 0.02 < h < Hs * 0.07 and w > 6 and a > w * h * 0.35:
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
        win = self.get_roblox_window_region()
        img = self._screen()
        panel, buttons = self.find_dialog(img)
        centers = [(win[0] + x + w // 2, win[1] + y + h // 2) for x, y, w, h in buttons]
        if not with_text:
            return panel is not None, centers
        sig = None
        if panel:
            x, y, w, h = panel
            crop = img[max(0, y + int(h * .05)):y + int(h * .45), max(0, x + int(w * .03)):x + int(w * .97)]
            if crop.size == 0:
                sig = np.zeros((24, 120), bool)
            else:
                top = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                text = cv2.dilate((top > 110).astype(np.uint8) * 255, np.ones((5, 5), np.uint8))
                sig = cv2.resize(text, (120, 24), interpolation=cv2.INTER_AREA) > 64
        return panel is not None, centers, sig

    def roblox_client_region(self):
        now = time.time()
        cache = getattr(self, "_client_cache", None)
        if cache and now - cache[0] < 1.0:
            return list(cache[1])
        region = None
        try:
            import pywinctl
            windows = [w for w in pywinctl.getAllWindows() if is_roblox_title(w.title)]
            if windows:
                active = pywinctl.getActiveWindow()
                w = active if active and is_roblox_title(active.title) else windows[0]
                f = w.getClientFrame()
                if f.right - f.left > 50 and f.bottom - f.top > 50:
                    region = [int(f.left), int(f.top), int(f.right), int(f.bottom)]
        except Exception:
            pass
        region = region or list(self.get_roblox_window_region())
        self._client_cache = (now, region)
        return list(region)

    def _hud_shot(self):
        return self.utils.capture_screen_bgr(self.roblox_client_region())

    BAR_THICK = {"health": 28, "mana": 23}

    def ui_scale(self):
        u = getattr(self, "_ui_scale", None)
        return min(4.0, max(0.3, u)) if u else 1.0

    def _bar(self, img, kind):
        from hud import find_bar
        b = find_bar(img, kind)
        if b:
            self._ui_scale = (b[3] - b[1]) / self.BAR_THICK[kind]
        return b

    def hud_shown(self, img=None):
        img = self._hud_shot() if img is None else img
        return self._bar(img, "health") is not None or self._bar(img, "mana") is not None

    def mana_bar_shown(self, img=None):
        return self._bar(self._hud_shot() if img is None else img, "mana") is not None

    TOP_BAR_PX = 64

    def clover_area(self):
        l, t, r, b = self.roblox_client_region()
        try:
            import ctypes
            scale = ctypes.windll.user32.GetDpiForSystem() / 96.0
        except Exception:
            scale = 1.0
        scale = max(1.0, scale, self.ui_scale())
        line = t + int(self.TOP_BAR_PX * scale)
        region = (self.app.settings.get("regions", {}) or {}).get("score", [0, 0, 0, 0])
        if region and any(region):
            x1, y1, x2, y2 = region
            return [x1, max(y1, line) if line < y2 else y1, x2, y2]
        return [l, min(b - 1, line), r, b]

    def nevermind_button(self, buttons=None):
        buttons = self.dialog_buttons() if buttons is None else buttons
        return next((b for b in buttons if "never" in (b[2] or "").lower()), None)

    def set_clover_region_auto(self):
        self.app.settings.settings.setdefault("regions", {})["score"] = [0, 0, 0, 0]

    def toggle_chat(self, why):
        pos = self.app.settings.get("regions", {}).get("chat_button", [0, 0])
        if not self.app.settings.get("hide_chat_in_minigame") or not any(pos):
            return
        if why == "hide":
            self._chat_hidden = True
        elif not getattr(self, "_chat_hidden", False):
            return
        else:
            self._chat_hidden = False
        with RobloxInputDriver._lock:
            self.human_click(*pos, duration=0.12)
            self._park_mouse()
            time.sleep(0.6)
        self.app.log("Chat hidden for the minigame." if why == "hide" else "Chat shown again.")

    def menu_showing(self):
        has_panel, buttons = self.read_dialog()
        return has_panel and len(buttons) >= 2

    def letterbox_shown(self, img=None):
        img = self._hud_shot() if img is None else img
        if img is None or not img.size:
            return False
        H = img.shape[0]
        bottom = img[int(H * 0.95):, :, :3].max(axis=2)
        if float((bottom < 15).mean()) < 0.97:
            return False
        return float(img[int(H * 0.3):int(H * 0.7), :, :3].mean()) > 25

    def in_minigame(self):
        return self.letterbox_shown()

    def hotbar_back(self):
        r, _ = self.gold_hotbar()
        if not r:
            return not self.letterbox_shown()
        img = self.utils.capture_screen_bgr(r)
        if img is None or not img.size:
            return False
        return float((img[:, :, :3].max(axis=2) > 40).mean()) >= 0.25

    def after_minigame(self):
        if not self.running or not self.wait_for_roblox_focus():
            return
        from utils import scan_key, press_key
        with RobloxInputDriver._lock:
            scan_key(0x1D, True)
            time.sleep(0.05)
            press_key("1", True)
            time.sleep(0.05)
            press_key("1", False)
            time.sleep(0.05)
            scan_key(0x1D, False)
        self.app.log("Pressed Ctrl+1 (minigame done).")
        time.sleep(1.0)

    def dialog_mode(self):
        mode = self.app.settings.get("dialog_mode", "image")
        return mode if mode in DIALOG_MODES else "image"

    @staticmethod
    def dialog_template_path(key):
        return os.path.join(DIALOG_TEMPLATE_DIR, f"{key}.png")

    def has_dialog_template(self, key):
        return os.path.exists(self.dialog_template_path(key))

    def capture_dialog_button(self, key, region):
        img = self.utils.capture_screen_bgr(region)
        if img is None or img.size == 0 or min(img.shape[:2]) < 8:
            return False
        os.makedirs(DIALOG_TEMPLATE_DIR, exist_ok=True)
        return cv2.imwrite(self.dialog_template_path(key), img)

    def find_dialog_button(self, key, threshold=0.8):
        if not self.has_dialog_template(key):
            return None
        if not key.startswith("move_"):
            return self.utils.image_search(self.dialog_template_path(key), self.get_roblox_window_region(), threshold)
        reg = self.get_roblox_window_region()
        frame = self.utils.capture_screen_bgr(reg)
        tpl = cv2.imread(self.dialog_template_path(key))
        if frame is None or tpl is None or tpl.shape[0] > frame.shape[0] or tpl.shape[1] > frame.shape[1]:
            return None
        _, val, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(frame, tpl, cv2.TM_CCOEFF_NORMED))
        if val < threshold:
            return None
        th, tw = tpl.shape[:2]
        for k in range(1, MAX_MOVES + 1):
            other = f"move_{k}"
            if other == key or not self.has_dialog_template(other):
                continue
            o = cv2.imread(self.dialog_template_path(other))
            if o is None:
                continue
            pad = 8
            x1, y1 = max(0, x - pad), max(0, y - pad)
            crop = frame[y1:y + th + pad, x1:x + tw + pad]
            if o.shape[0] > crop.shape[0] or o.shape[1] > crop.shape[1]:
                continue
            if float(cv2.matchTemplate(crop, o, cv2.TM_CCOEFF_NORMED).max()) > val + 0.01:
                return None
        return reg[0] + x + tw // 2, reg[1] + y + th // 2

    def manual_point(self, key):
        pt = self.app.settings.get("positions", {}).get(key, [0, 0])
        return tuple(pt) if pt and any(pt) else None

    def _skip_typing(self, seconds):
        end = time.time() + seconds
        while self.running and time.time() < end:
            time.sleep(0.05)

    def after_training_wait(self):
        try:
            return max(0.0, float(self.app.settings.get("after_training_wait", 5)))
        except (TypeError, ValueError):
            return 5.0

    def run_dialogue_fixed(self, move_idx):
        mode = self.dialog_mode()
        wait = float(self.app.settings.get("dialog_wait", 5))
        steps = [("clover_training", "Clover Training"), (f"move_{move_idx + 1}", self.move_label(move_idx))]
        self._park_mouse()
        for n, (key, label) in enumerate(steps, start=1):
            if n == 2 and mode == "image":
                time.sleep(self.after_training_wait())
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
                time.sleep(0.3)
                pt = self.find_dialog_button(key) or pt
            if not self.running:
                return False
            self.app.log(f"[{n}/2] Clicking {label} ({mode})")
            self.human_click(*pt, duration=0.15)
            self._park_mouse()
        return True

    TRAINING_WORDS = ("clover", "training", "research")
    NEVER_WORDS = ("class", "reset", "opportunit")

    @staticmethod
    def _has_word(text, words):
        import difflib, re
        t = text.lower()
        if any(w in t for w in words):
            return True
        tokens = re.findall(r"[a-z]{4,}", t)
        return any((tok[0] == w[0] or w in LibraryLogic.NEVER_WORDS)
                   and difflib.SequenceMatcher(None, tok, w).ratio() >= 0.8 for tok in tokens for w in words)

    def find_training_button(self):
        btns = self.dialog_buttons()
        low = [(x, y, (t or "").lower()) for x, y, t in btns]
        for x, y, t in low:
            if self._has_word(t, self.TRAINING_WORDS) and not self._has_word(t, self.NEVER_WORDS):
                return (x, y), f"'{t.strip()[:40]}'"
        hit = self._find_words_right_of_panel(self.TRAINING_WORDS, self.NEVER_WORDS)
        if hit:
            return hit, "the 'research / Clover Training' text"
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

    @staticmethod
    def reading_order(res):
        boxes = []
        for r in res or []:
            ys = [p[1] for p in r[0]]
            boxes.append(((min(ys) + max(ys)) / 2, max(1.0, max(ys) - min(ys)), min(p[0] for p in r[0]), r))
        boxes.sort(key=lambda b: b[0])
        lines = []
        for b in boxes:
            if lines and abs(b[0] - lines[-1][0]) <= 0.5 * max(b[1], lines[-1][1]):
                lines[-1][2].append(b)
            else:
                lines.append([b[0], b[1], [b]])
        return [b[3] for line in lines for b in sorted(line[2], key=lambda b: b[2])]

    def _ocr_button(self, crop):
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
            text = " ".join(t for _, t, c in self.reading_order(res) if float(c) > 0.3).strip()
            if len(self._norm_name(text)) > len(self._norm_name(best)):
                best = text
        return best

    def _read_button_texts(self, win, boxes, img_h=None, img=None):
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
            for i, (x, y, w, h) in enumerate(boxes):
                k = self._norm_name(texts[i])
                if not k or sum(1 for t in texts if self._norm_name(t) == k) > 1:
                    again = self._ocr_button(img[max(0, y):y + h, max(0, x):x + w])
                    if self._norm_name(again):
                        texts[i] = again
            for i, (x, y, w, h) in enumerate(boxes):
                texts[i] = self.fix_numeral(texts[i], img[max(0, y) + 3:y + h - 3, max(0, x) + 12:x + w - 12])
        return texts

    @staticmethod
    def shape_numeral(crop):
        if crop is None or not crop.size or crop.shape[0] < 6 or crop.shape[1] < 10:
            return ""
        b, g, r = (crop[..., i].astype(int) for i in range(3))
        dark = (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) < 70).astype(np.uint8)
        m = ((r > 140) & (g > 110) & (r - b > 60) & (cv2.dilate(dark, np.ones((5, 5), np.uint8)) > 0)).astype(np.uint8)
        rows = m.sum(1) > 0
        bands, start = [], None
        for yy, on in enumerate(list(rows) + [False]):
            if on and start is None:
                start = yy
            elif not on and start is not None:
                bands.append((start, yy)); start = None
        if not bands:
            return ""
        y1, y2 = max(bands, key=lambda bd: int(m[bd[0]:bd[1]].sum()))
        m[:y1] = 0
        m[y2:] = 0
        xs = np.where(m.sum(0) > 0)[0]
        if len(xs) < 2:
            return ""
        runs, start = [], xs[0]
        for a, c in zip(xs, xs[1:]):
            if c != a + 1:
                runs.append((start, a)); start = c
        runs.append((start, xs[-1]))
        gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
        if not gaps:
            return ""
        word_gap = max(3, max(gaps) * 0.6)
        last = len(runs) - 1
        while last > 0 and gaps[last - 1] < word_gap:
            last -= 1
        out = ""
        for x1, x2 in runs[last:]:
            gl = m[:, x1:x2 + 1]
            ys = np.where(gl.sum(1) > 0)[0]
            hh, w = ys[-1] - ys[0] + 1, x2 - x1 + 1
            if w <= hh * 0.45:
                out += "I"
                continue
            mid = gl[ys[0] + hh // 3: ys[0] + 2 * hh // 3].sum(0) > 0
            bars = int(np.sum(np.diff(np.concatenate([[0], mid.astype(int)])) == 1))
            bc = np.where(gl[ys[-1] - max(1, hh // 5):ys[-1] + 1].sum(0) > 0)[0]
            if len(bc) and bc[-1] - bc[0] < w * 0.5 and bars <= 2 and w < hh * 1.2:
                out += "V"
            else:
                out += "I" * max(1, bars)
        import re
        return out if re.fullmatch(r"I{1,3}|IV|VI{0,3}|IX|X", out) else ""

    def fix_numeral(self, text, crop):
        if not self._numeral(text):
            return text
        shape = self.shape_numeral(crop)
        if not shape:
            return text
        return " ".join(text.split()[:-1] + [shape])

    def dialog_buttons(self):
        win = self.get_roblox_window_region()
        img = self._screen()
        panel, boxes = self.find_dialog(img)
        if not boxes:
            return []
        texts = self._read_button_texts(win, boxes, img.shape[0], img)
        return [(win[0] + x + w // 2, win[1] + y + h // 2, t) for (x, y, w, h), t in zip(boxes, texts)]

    @staticmethod
    def _same_name(a, b):
        import difflib, re
        an = "".join(ch for ch in a.lower() if ch.isalnum())
        bn = "".join(ch for ch in b.lower() if ch.isalnum())
        if not an or not bn:
            return False
        if an == bn:
            return True
        if not LibraryLogic._same_numeral(a, b):
            return False
        if " " in a.strip():
            aw = [w for w in re.findall(r"[a-z0-9]+", a.lower()) if len(w) >= 3 and not re.fullmatch(r"[ivxl1]{1,5}", w)]
            bw = [w for w in re.findall(r"[a-z0-9]+", b.lower()) if len(w) >= 3 and not re.fullmatch(r"[ivxl1]{1,5}", w)]
            near = lambda w, ws: any(difflib.SequenceMatcher(None, w, x).ratio() >= 0.75 for x in ws)
            if aw and bw and all(near(w, bw) for w in aw) and all(near(w, aw) for w in bw):
                return True
            return abs(len(an) - len(bn)) <= 2 and difflib.SequenceMatcher(None, an, bn).ratio() >= 0.9
        if an in bn or bn in an or difflib.SequenceMatcher(None, an, bn).ratio() >= 0.8:
            return True
        if len(an) >= 3:
            return any(difflib.SequenceMatcher(None, an, w).ratio() >= 0.75
                       for w in re.findall(r"[a-z0-9]+", b.lower()) if len(w) >= 3)
        return False

    @staticmethod
    def _numeral(t):
        import re
        words = re.findall(r"[a-z0-9|]+", (t or "").lower())
        if len(words) >= 2:
            w = words[-1].translate(str.maketrans("l1|", "iii"))
            if re.fullmatch(r"[ivx]{1,5}|[0-9]{1,2}", w):
                return w
        return ""

    @staticmethod
    def _same_numeral(a, b):
        na, nb = LibraryLogic._numeral(a), LibraryLogic._numeral(b)
        if na == nb:
            return True
        if na and not nb:
            tail = "".join(ch for ch in b.lower() if ch.isalnum()).translate(str.maketrans("l1", "ii"))
            return tail.endswith(na) and not tail[:-len(na)][-1:] in ("i", "v", "x")
        return False

    def _scroll_list(self, buttons, notches=-1):
        from pynput.mouse import Controller as MouseController
        x, y = buttons[len(buttons) // 2][:2]
        with self.input_lock:
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
        time.sleep(0.6)
        self._park_mouse()
        time.sleep(0.2)

    @staticmethod
    def _is_skip(text):
        return (text or "").strip().lower().strip(".!") in ("skip", "skip>", ">>")

    def _move_refs(self):
        refs = list(getattr(self, "_hotbar_seen", []) or [])
        if not refs and self.running and not getattr(self, "_hotbar_tried", False):
            self._hotbar_tried = True
            try:
                refs = [t for _, t in (self.read_hotbar_names() or []) if t]
                self._hotbar_seen = refs
            except Exception:
                refs = []
        flags = self.train_flags()
        names = self._nine("move_names", "")
        return refs + [names[i] for i in range(MAX_MOVES) if flags[i] and names[i]]

    def _looks_like_move(self, text, refs):
        import difflib
        t = self._norm_name(text)
        if len(t) < 3 or self._is_skip(text) or self._has_word(text, self.TRAINING_WORDS) or self._has_word(text, self.NEVER_WORDS)                 or "never" in t:
            return False
        for r in refs:
            rn = self._norm_name(r)
            if len(rn) < 3:
                continue
            need = 0.5 if min(len(t), len(rn)) >= 6 else 0.75
            if rn in t or difflib.SequenceMatcher(None, t, rn).ratio() >= need:
                return True
        return False

    def wait_move_list(self, timeout=12.0, alive=None):
        alive = alive or (lambda: self.running)
        end = time.time() + timeout
        last, since, seen_list = None, 0.0, []
        refs = self._move_refs()
        while alive() and time.time() < end:
            buttons = [b for b in self.dialog_buttons() if not self._is_skip(b[2])]
            sig = tuple((int(b[0]) // 8, int(b[1]) // 8) for b in buttons)
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
                seen_list = buttons
            time.sleep(0.25)
        return seen_list

    def save_debug_shot(self, name):
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
        l, t, r, b = self.get_roblox_window_region()
        return [(int(l + (r - l) * 0.86), int(t + (b - t) * 0.72), "")]

    def _any_move_picture(self, idxs):
        return any(self.has_dialog_template(f"move_{i + 1}") and self.find_dialog_button(f"move_{i + 1}")
                   for i in idxs)

    def _best_name_hit(self, name, buttons):
        import difflib
        hits = [b for b in buttons if b[2] and self._same_name(name, b[2])]
        if not hits:
            return None
        n = self._norm_name(name)
        return max(hits, key=lambda b: (self._norm_name(b[2]) == n,
                                        difflib.SequenceMatcher(None, n, self._norm_name(b[2])).ratio()))

    def pick_move_button(self, move_idx):
        key, name = f"move_{move_idx + 1}", self.move_names()[move_idx]
        label = self.move_label(move_idx)
        has_pic = self.has_dialog_template(key)
        if not (has_pic and self.find_dialog_button(key)):
            self.wait_move_list(timeout=5.0)
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
                    self.app.log("-> The move list didn't show up (only 'Skip' / no buttons).")
                    return False
                self.app.log(f"   {label} not visible yet - scrolling down (by picture)")
                self._scroll_list(self._list_anchor())
                continue
            at_end = any("never" in (b[2] or "").lower() for b in buttons)
            if name and (not has_pic or at_end):
                hit = self._best_name_hit(name, buttons)
                if hit:
                    self.app.log(f"[2/2] Found {label} (name{' - picture not found' if has_pic else ''}) - clicking")
                    self.human_click(hit[0], hit[1], duration=0.15)
                    return True
            elif not has_pic and step == 0:
                moves = [b for b in buttons if "never" not in b[2].lower()]
                if move_idx < len(moves):
                    self.app.log(f"[2/2] Clicking button {move_idx + 1} = {label} (no name/picture set)")
                    self.human_click(moves[move_idx][0], moves[move_idx][1], duration=0.15)
                    return True
            never = self.nevermind_button(buttons)
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
        if self.dialog_mode() == "manual":
            if not self.wait_for_roblox_focus():
                return False
            self.utils.send_key('e')
            self.app.log("Dialogue: pressed E (manual mode).")
            return True
        return self.reopen_dialogue(timeout=20.0, opened="Dialogue opened (Clover Training showing).", failed=None)

    def reopen_dialogue(self, timeout=60.0, opened="Dialogue open again (Clover Training showing).",
                        failed="Couldn't reopen the dialogue here - walking to the wisp again."):
        if not self.wait_for_roblox_focus():
            return False
        if self.dialog_mode() == "manual":
            for _ in range(10):
                self.utils.send_key('space'); self.utils.send_key('e'); time.sleep(0.2)
            return True
        spam = threading.Event()
        spam.set()

        def press():
            while spam.is_set() and self.running:
                for key in ('space', 'e'):
                    if not spam.is_set():
                        return
                    self.utils.send_key(key)
                    time.sleep(0.05)
        threading.Thread(target=press, daemon=True).start()
        try:
            if self._training_within(timeout):
                self.app.log(opened)
                return True
            if failed:
                self.app.log(failed)
            return False
        finally:
            spam.clear()

    def _training_within(self, seconds):
        end = time.time() + seconds
        last_full, said = 0.0, False
        while self.running and time.time() < end:
            if self.mana_bar_shown():
                if time.time() - last_full < 1.0:
                    time.sleep(0.1)
                    continue
            elif not said:
                said = True
                self.app.log("Mana bar gone - waiting for Clover Training.")
            last_full = time.time()
            if self.training_option_visible():
                return True
            time.sleep(0.1)
        return False

    def training_option_visible(self):
        if self.dialog_mode() == "image" and self.find_dialog_button("clover_training") is not None:
            return True
        if not self.read_dialog()[0]:
            return False
        return any(self._has_word((t or "").lower(), self.TRAINING_WORDS)
                   and not self._has_word((t or "").lower(), self.NEVER_WORDS)
                   for _, _, t in self.dialog_buttons())

    def _park_mouse(self):
        l, t, r, b = self.get_roblox_window_region()
        self.utils.mouse_move((l + r) // 2, t + int((b - t) * 0.3))

    def run_dialogue(self, move_idx):
        return self.run_dialogue_fixed(move_idx)

    def gold_ready(self):
        if self.gold_mode() == "auto":
            return self.gold_hotbar()[0] is not None
        regions = self.app.settings.get("regions", {}) or {}
        return all(any(regions.get(f"gold_clover_{i + 1}", [0, 0, 0, 0]))
                   for i, on in enumerate(self.train_flags()) if on)

    def setup_problems(self):
        out = []
        mode = self.dialog_mode()
        if mode == "manual" and not self.manual_point("clover_training"):
            out.append({"id": "lib_manual_training", "block": False, "short": "No Clover Training spot",
                        "go": ("Setup", "dialog_card"),
                        "text": "Manual dialogue: no click spot for Clover Training (Setup -> step 2 Moves and wisp dialogue)."})
        if mode == "image" and not self.has_dialog_template("clover_training"):
            out.append({"id": "lib_image_training", "block": False, "short": "No Clover Training picture",
                        "go": ("Setup", "dialog_card"),
                        "text": "Image dialogue: no picture of Clover Training yet (Setup -> step 2 Moves and wisp dialogue)."})
        if mode == "image":
            flags = self.train_flags()
            for i in range(MAX_MOVES):
                if flags[i] and not self.has_dialog_template(f"move_{i + 1}"):
                    out.append({"id": f"lib_pic_{i}", "block": False, "short": f"{self.move_label(i)} has no picture",
                                "go": ("Setup", "dialog_card"),
                                "text": f"Image dialogue: {self.move_label(i)} is ticked but has no picture - only its "
                                        f"name is used to find it (Setup -> step 2 Moves and wisp dialogue -> Capture)."})
        if not self.load_route() and not any(self.load_route(b) for b in self._builtins()):
            out.append({"id": "lib_route", "block": False, "short": "No route recorded",
                        "go": ("Setup", "route_menu"),
                        "text": f"No recorded route - it uses the old D/S/W walk (record one with {self.rec_key()})."})
        if not self.gold_ready():
            out.append({"id": "lib_gold", "block": False, "short": "No gold clover check",
                        "go": ("Setup", "gold_card"),
                        "text": "The gold clover check isn't set - a move that turned gold isn't noticed, so it keeps "
                                "being trained (Setup -> step 3 Gold clover check)."})
        return out

    def main_loop(self):
        from logic_events import WATCHER
        WATCHER.hold("Library")
        try:
            self._library_loop()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.app.log(f"Library error: {e} - macro stopped.")
            self.running = False
        finally:
            WATCHER.release("Library")

    def _library_loop(self):
        from logic_events import WATCHER
        self._last_done = -1
        while self.running:
            if not self.wait_for_roblox_focus():
                break
            trained = self.check_trained_status()
            to_train = [i for i in range(MAX_MOVES) if not trained[i]]
            if not to_train:
                self.app.log("All selected moves are trained! Macro stopped.")
                self.running = False
                if self.app.settings.get("sound_when_done", False):
                    from utils import play_sound
                    play_sound("done")
                break
            if self.app.settings.get("train_in_order", False):
                self.current_move_idx = next((i for i in to_train if i > self._last_done), to_train[0])
            else:
                self.current_move_idx = to_train[0]
            if self.in_minigame():
                self.app.log("Minigame is running — clicking clovers before walking.")
                self.perform_clover_scoring(after_pick=False)
                WATCHER.checkpoint("Library")
                time.sleep(1.0)
                continue
            self.app.log(f"Training {self.move_label(self.current_move_idx)}")

            if self.dialogue_visible():
                opened = True
                mode = self.dialog_mode()
                on_first_menu = self.find_dialog_button("clover_training") is not None if mode == "image" else True
                if not on_first_menu:
                    self.app.log("Already in the move list - picking the move here.")
                    if self.pick_move_button(self.current_move_idx):
                        played = self.perform_clover_scoring()
                        if played is not False and self.running:
                            self.app.log("Cycle Complete")
                            self._last_done = self.current_move_idx
                            WATCHER.checkpoint("Library")
                            self.handle_ok_popup()
                            time.sleep(1.0)
                            continue
                else:
                    self.app.log("Already at the wisp - skipping the walk.")
            else:
                self.go_to_wisp()
                if not self.running:
                    break
                opened = self.open_dialogue()
            if not opened:
                self.app.log("Couldn't open the wisp dialogue. Trying again from the start...")
                time.sleep(1.0)
                continue
            done = False
            for attempt in range(3):
                if self.run_dialogue(self.current_move_idx):
                    done = True
                    break
                if not self.running:
                    break
                if self.dialog_mode() != "manual" and self.dialogue_visible():
                    never = self.nevermind_button()
                    if never:
                        self.human_click(never[0], never[1], duration=0.15)
                        time.sleep(1.0)
                    self.app.log("Dialogue stuck - reopening it: double jump + E")
                else:
                    self.app.log("Dialogue closed - staying here: double jump + E until it opens again")
                if not self.reopen_dialogue():
                    break
            if not done:
                time.sleep(1.0)
                continue
            played = self.perform_clover_scoring()
            if played is False and self.running:
                if self.dialog_mode() != "manual" and self.dialogue_visible():
                    self.app.log("The dialogue is still open - picking the move again.")
                    if self.run_dialogue(self.current_move_idx):
                        played = self.perform_clover_scoring()
                if played is False:
                    self.app.log("No minigame - starting the cycle again.")
                    time.sleep(1.0)
                    continue
            if not self.running:
                break
            self.app.log("Cycle Complete")
            self._last_done = self.current_move_idx
            WATCHER.checkpoint("Library")
            self.handle_ok_popup()
            time.sleep(1.0)

    def test_detection(self):
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
        img = self._hud_shot()
        box = self.letterbox_shown(img)
        hb, _ = self.gold_hotbar()
        hotbar = ("not set (Setup step 3)" if not hb else ("visible" if self.hotbar_back() else "hidden"))
        self.app.log(f"Minigame black bars: {'YES' if box else 'no'} | Hotbar: {hotbar} | "
                     f"Mana bar: {'seen' if self.mana_bar_shown(img) else 'not seen'} (only used while opening the dialogue)")

    def test_scroll(self):
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

    @staticmethod
    def _norm_name(t):
        return "".join(ch for ch in (t or "").lower() if ch.isalnum())

    def read_hotbar_names(self, only_slots=None):
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
                    out.append((n, ""))
                continue
            m = max(2, w // 14)
            text = self._ocr_button(img[y + m:y + side - m, x + m:x + w - m])
            if not self._norm_name(text):
                box = [reg[0] + x + m, reg[1] + y + m, reg[0] + x + w - m, reg[1] + y + side - m]
                lines = self.reading_order(self.utils.get_text_from_region(box, upscale=3))
                text = " ".join(t for _, t, c in lines if c > 0.3).strip()
            text = self.fix_numeral(text, img[y + side // 2:y + side - m, x + m:x + w - m])
            out.append((n, text))
        if any(t for _, t in out):
            self._hotbar_seen = [t for _, t in out if t]
        return out

    @staticmethod
    def _same_picture(a, b):
        try:
            if a is None or b is None or not a.size or not b.size:
                return False
            ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
            gb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (ga.shape[1], ga.shape[0]))
            return float(cv2.matchTemplate(ga, gb, cv2.TM_CCOEFF_NORMED).max()) >= 0.93
        except Exception:
            return False

    @staticmethod
    def _button_like(pic):
        if pic is None or not pic.size or pic.shape[1] < pic.shape[0] * 2:
            return False
        g = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY)
        return float((g < 75).mean()) >= 0.35

    UNREAD_NAME = "(words not read)"

    def scan_move_list(self, alive=lambda: True, keep_unread=False):
        self._bad_pic_shot = False
        found, seen_names, still, unread = [], set(), 0, 0
        every = []
        for _ in range(MAX_MOVES + 4):
            if not alive():
                break
            if not self.wait_move_list(alive=alive):
                break
            win = self.get_roblox_window_region()
            img = self._screen()
            panel, boxes = self.find_dialog(img)
            if not boxes:
                time.sleep(0.5)
                continue
            new, centers, never = 0, [], False
            texts = self._read_button_texts(win, boxes, img.shape[0], img)
            first_menu = any(self._has_word(t, self.TRAINING_WORDS) or any(w in t.lower() for w in self.NEVER_WORDS)
                             for t in texts)
            for (x, y, w, h), text in zip(boxes, texts):
                text = text.strip()
                centers.append((win[0] + x + w // 2, win[1] + y + h // 2, text))
                if "never" in text.lower():
                    never = True
                    continue
                if self._is_skip(text):
                    continue
                if self._has_word(text, self.TRAINING_WORDS) or any(w in text.lower() for w in self.NEVER_WORDS):
                    continue
                pic = img[y:y + h, x:x + w].copy()
                if not self._button_like(pic):
                    if not self._bad_pic_shot:
                        self._bad_pic_shot = True
                        path = self.save_debug_shot("move_list_pictures")
                        self.app.log(f"Move list: the button of '{text}' didn't look like a button - picture "
                                     f"not saved. What the macro saw: {path}")
                    pic = None
                key = self._norm_name(text)
                if key:
                    text = self.fix_numeral(text, img[y + 3:y + h - 3, x + 12:x + w - 12])
                    key = self._norm_name(text)
                if pic is not None and not first_menu and not any(self._same_picture(pic, p) for _, p in every):
                    every.append((text if key else f"Button {len(every) + 1} {self.UNREAD_NAME}", pic))
                same = next((k for k, (_, p) in enumerate(found) if self._same_picture(pic, p)), None)
                if same is not None:
                    if key and self.UNREAD_NAME in found[same][0]:
                        found[same] = (text, found[same][1])
                        seen_names.add(key)
                    continue
                if not key:
                    if keep_unread and pic is not None and not first_menu:
                        unread += 1
                        found.append((f"Button {unread} {self.UNREAD_NAME}", pic))
                        new += 1
                    continue
                if key in seen_names:
                    again = self._ocr_button(pic)
                    if self._norm_name(again) and self._norm_name(again) not in seen_names:
                        text, key = again, self._norm_name(again)
                    else:
                        text = f"{text} (#{sum(1 for n, _ in found if self._norm_name(n).startswith(key)) + 1})"
                        key = self._norm_name(text)
                seen_names.add(key)
                found.append((text, pic))
                new += 1
            if never:
                break
            still = still + 1 if new == 0 else 0
            if still >= 2:
                break
            self._scroll_list(centers)
        self._save_move_list_pictures(every, found)
        return found

    MOVE_LIST_DIR = os.path.join(DIALOG_TEMPLATE_DIR, "move_list")

    def _save_move_list_pictures(self, every, found):
        try:
            if not every:
                return
            os.makedirs(self.MOVE_LIST_DIR, exist_ok=True)
            for f in os.listdir(self.MOVE_LIST_DIR):
                if f.lower().endswith(".png"):
                    os.remove(os.path.join(self.MOVE_LIST_DIR, f))
            for i, (name, pic) in enumerate(every, start=1):
                name = next((n for n, p in found if self._same_picture(pic, p)), name)
                safe = "".join(c if c.isalnum() or c in " -()#" else "_" for c in name).strip()[:60] or "button"
                cv2.imwrite(os.path.join(self.MOVE_LIST_DIR, f"{i:02d} {safe}.png"), pic)
            self.app.log(f"Move list: saved a picture of all {len(every)} button(s) in {self.MOVE_LIST_DIR}")
        except Exception as e:
            self.app.log(f"Move list: couldn't save the button pictures ({e}).")

    @staticmethod
    def _words(text):
        import re
        return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower().replace("'", "")) if w]

    @classmethod
    def unique_keyword(cls, name, all_names):
        import difflib
        others = [w for n in all_names if n != name for w in cls._words(n)]
        cands = [w for w in cls._words(name) if len(w) >= 3]
        unique = [w for w in cands if not any(difflib.SequenceMatcher(None, w, o).ratio() >= 0.8 for o in others)]
        return max(unique, key=len) if unique else None

    def match_hotbar_to_list(self, hotbar, names):
        import difflib, re
        names = [n for n in names if self.UNREAD_NAME not in n]
        keys = {n: self.unique_keyword(n, names) for n in names}

        def close(a, b):
            return difflib.SequenceMatcher(None, a, b).ratio()

        all_words = [set(self._words(n)) for n in names]
        shared = {w for i, ws in enumerate(all_words) for w in ws
                  if any(close(w, o) >= 0.8 for j, os_ in enumerate(all_words) if j != i for o in os_)}

        def leftover(text):
            return [t for t in self._words(text) if not any(close(t, w) >= 0.8 for w in shared)
                    and not re.fullmatch(r"[ivxl1]{1,5}", t)]

        def score(hot, name):
            if not self._norm_name(hot):
                return 0.0
            if (self._numeral(hot) or self._numeral(name)) and not self._same_numeral(name, hot):
                return 0.0
            if self._numeral(name) and not leftover(hot):
                return 0.6 + 0.4 * close(self._norm_name(hot), self._norm_name(name))
            left, k = leftover(hot), keys.get(name)
            if not left:
                if k:
                    return 0.3
                return 0.6 + 0.4 * close(self._norm_name(hot), self._norm_name(name))
            if not k:
                return 0.3
            best = 0.0
            for t in left:
                r = close(t, k)
                if len(t) >= 3 and len(k) >= 3 and t[:2] == k[:2]:
                    r = max(r, 0.7)
                if k.startswith(t):
                    r = max(r, 0.6 + 0.4 * len(t) / len(k))
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
        stats = self._nine("move_stats", 0)
        if 0 <= i < len(stats) and stats[i]:
            self.reset_spells_gold(i)

    def apply_auto_setup(self, rows, pictures, clear=()):
        names = self._nine("move_names", "")
        slots = self._nine("gold_move_slots", lambda k: k + 1)
        flags = self._nine("train_moves", False)
        if not any("move" in r for r in rows):
            for i in range(MAX_MOVES):
                names[i], flags[i] = "", False
        for i in clear:
            if names[i]:
                self.reset_move_gold(i)
            names[i], flags[i] = "", False
        keys = getattr(self, "_auto_keys", {})
        for n, r in enumerate(rows[:MAX_MOVES]):
            i = int(r.get("move", n))
            word = r.get("keyword") or keys.get(r["name"])
            new = word.capitalize() if word else r["name"]
            if self.UNREAD_NAME in r["name"]:
                new = r.get("hotbar") or ""
            if self._norm_name(new) != self._norm_name(names[i]):
                self.reset_move_gold(i)
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
                time.sleep(float(self.app.settings.get("dialog_wait", 5)))
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

    def test_open_dialogue(self):
        if self.running:
            self.app.log("Stop the macro first, then test the opening.")
            return
        if not self.wait_focus_for_test():
            return
        self.app.log("--- Test opening: space + E until Clover Training shows (up to 20 s) ---")
        self.running = True
        try:
            ok = self.reopen_dialogue(timeout=20.0, opened="--- Test opening: Clover Training seen - OK ---",
                                      failed="--- Test opening: Clover Training NOT seen in 20 s ---")
            if not ok and not self.running:
                self.app.log("--- Test opening stopped ---")
        finally:
            self.running = False

    def test_find_moves(self, walk=False):
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
        seen = []
        found = {}
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
                time.sleep(self.after_training_wait())
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
                    break
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
            region = self.clover_area()
            self.app.log("Test: using the automatic Clover Region (the Roblox window below its top bar).")

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

    MINIGAME_START_LIMIT = 30.0
    SCORE_LOOK = 6.0
    MINIGAME_LENGTH = 50.0

    def after_move_wait(self):
        try:
            return max(0.0, float(self.app.settings.get("after_move_wait", 1.0)))
        except (TypeError, ValueError):
            return 1.0

    def score_showing(self):
        self._last_read = []
        try:
            reg = self.get_roblox_window_region()
            for _, text, conf in self.utils.get_text_from_region(reg, upscale=1):
                self._last_read.append((text or "").strip())
                if self.is_score_word(text):
                    return True
        except Exception as e:
            self.app.log(f"   reading the screen for SCORE failed: {e}")
        return False

    def _what_was_read(self):
        words = [t for t in getattr(self, "_last_read", []) if t][:8]
        return ", ".join(f"'{t[:24]}'" for t in words) if words else "nothing"

    @staticmethod
    def is_score_word(text):
        import re
        return any(w in ("score", "scores") for w in re.findall(r"[a-z0-9]+", (text or "").lower().replace("0", "o")))

    def _wait_for_score(self):
        end = time.time() + self.SCORE_LOOK
        while self.running and time.time() < end:
            if self.score_showing():
                self.app.log("Minigame confirmed (SCORE on screen).")
                return True
            time.sleep(0.3)
        return False

    def perform_clover_scoring(self, after_pick=True):
        settings = self.app.settings.settings
        clover_colors = settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        global_tolerance = settings.get("color_tolerance", 15)
        clover_tols = settings.get("clover_tolerances", {})

        session_stats = {"gold": 0, "silver": 0, "bronze": 0, "total_clicks": 0}
        self.minigame_running = True
        
        if after_pick:
            wait = self.after_move_wait()
            if wait > 0:
                self.app.log(f"Waiting {wait:g} s after picking the move...")
                end = time.time() + wait
                while self.running and time.time() < end:
                    time.sleep(0.05)
        limit = self.MINIGAME_START_LIMIT
        start_wait, seen, last_note, last_read = time.time(), 0, time.time(), 0.0
        self.app.log("Looking for the minigame (SCORE on screen)...")
        while self.running:
            if not self.wait_for_roblox_focus():
                self.minigame_running = False
                return False
            box = self.letterbox_shown()
            seen = seen + 1 if box else 0
            score = False
            if time.time() - last_read >= 1.0:
                last_read = time.time()
                score = self.score_showing()
            if score or seen >= 3:
                if not score and not self._wait_for_score():
                    if self.running:
                        self.app.log("Black minigame bars, but no 'SCORE' on screen - not pressing anything (read: "
                                     f"{self._what_was_read()}).")
                    self.minigame_running = False
                    return False
                self.app.log("Minigame started (SCORE on screen).")
                self.toggle_chat("hide")
                break
            if time.time() - last_note >= 5:
                last_note = time.time()
                self.app.log(f"   still waiting: black minigame bars {'showing' if box else 'not showing'}, "
                             f"no SCORE yet (read: {self._what_was_read()})")
            if time.time() - start_wait > limit:
                self.app.log(f"The minigame didn't start within {limit:g} s - the move probably wasn't picked.")
                self.minigame_running = False
                return False
            time.sleep(0.15)
        if not self.running:
            self.minigame_running = False
            return False

        region = self.clover_area()
        gap = int(max(20, min(150, 50 * self.ui_scale())))
        result = {"ended": False}
        look_from = time.time() + (self.MINIGAME_LENGTH if after_pick else 0)

        def end_detector():
            back, n = 0, 0
            while self.running and self.minigame_running:
                time.sleep(0.25)
                if time.time() < look_from:
                    continue
                n += 1
                try:
                    back = back + 1 if self.hotbar_back() else 0
                    if back >= 3:
                        self.app.log("Minigame ended.")
                        result["ended"] = True
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
                        is_too_close = any(math.hypot(tx - p['x'], ty - p['y']) < gap for p in self.click_history)
                        if is_too_close:
                            continue
                        raw_targets.append((clover_type, tx, ty, area))

                if raw_targets:
                    type_priority = {'gold': 0, 'silver': 1, 'bronze': 2}
                    raw_targets.sort(key=lambda item: (type_priority.get(item[0], 3), -item[3]))

                    targets = []
                    for clover_type, tx, ty, area in raw_targets:
                        duplicate = any(math.hypot(tx - px, ty - py) < gap for _, px, py, _ in targets)
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
        self.record_gold()
        if result["ended"]:
            self.after_minigame()
        return True
