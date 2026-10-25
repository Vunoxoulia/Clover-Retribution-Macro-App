import os
import time
from route_nav import RouteNav
import cv2
import numpy as np
from utils import RobloxInputDriver, arrow_key, tap_scan

CAM_90_DEFAULT = 0.75      # seconds an arrow key is held to turn the camera 90 degrees (it turns at a constant speed)
MENU_MATCH = 0.75          # main menu picture found at least this well
HEALTH_MATCH = 0.9         # health bar picture found at least this well = fully spawned (dying red flash: ~0.76)
CRYSTAL_MIN = 0.5          # % of the view that's crystal at the crystal spawn (~1-6 %; the other spawn 0 %, open field ~0.3 %)
PICK_TOL = {"crystal": 50, "jug": 25, "jug2": 25}   # default tolerance for a picked colour (crystals are a gradient: needs more)
LOCATIONS = 3              # the Juggernaut can spawn at 3 places: one recorded route (from the crystal spawn) each
JUG_DARK_RATIO = 0.85      # its body is darker than the scene: below 85 % of its typical brightness (bright fog: ~79 %)
JUG_RED_MIN = 4            # dim red marks (~H 172, V ~55) on that dark body
JUG_NEAR = 10              # picked colours 1 + 2 must be within this many px of each other (its marks are ON its body)
JUG_PURPLE_MIN = 150       # purple haze pixels around it = corrupted


class UmbralAbyssLogic(RouteNav):
    """Crystal spawn -> walk route 1 -> Juggernaut there? kill it -> respawn -> route 2 -> ... -> route 3 -> again."""
    ROUTES_DIRNAME = "routes_umbral"
    ACTIVE_ROUTE_KEY = "umbral_active_route"
    USE_ALIGNMENT = False      # normal 3rd-person camera: replay the keys only
    ROUTE_TARGET = "location"
    E_MARKS_TARGET = False     # one F9 -> F9 walk = the way to one location

    def __init__(self, app):
        super().__init__(app)

    def route_checks(self):
        return False

    TURN_DEFAULTS = (("umbral_l90", "f1", -90), ("umbral_l180", "f2", -180), ("umbral_r90", "f3", 90),
                     ("umbral_r180", "f4", 180), ("umbral_360", "f5", 360))

    def turn_keys(self):
        """The camera-turn hotkeys (Hotkeys tab, default F1-F5) -> degrees: recorded into routes as exact turns."""
        hk = self.app.settings.get("hotkeys") or {}
        return {str(hk.get(a) or key).lower(): deg for a, key, deg in self.TURN_DEFAULTS}

    # ---------- camera ----------
    def cam_90_secs(self):
        try:
            return max(0.05, float(self.app.settings.get("umbral_cam_90", CAM_90_DEFAULT)))
        except (TypeError, ValueError):
            return CAM_90_DEFAULT

    def rotate_camera(self, degrees):
        """Turn the camera by `degrees` (negative = left) by holding the left / right arrow key. The arrow keys
        turn the camera at a constant speed, so the hold time is degrees / 90 x the '90 degree turn time'."""
        if not degrees:
            return
        key = "left" if degrees < 0 else "right"
        hold = abs(degrees) / 90.0 * self.cam_90_secs()
        with RobloxInputDriver._lock:                    # nothing else may press keys mid-turn
            arrow_key(key, True)
            end = time.perf_counter() + hold
            while time.perf_counter() < end:             # precise: time.sleep alone can overshoot
                time.sleep(min(0.01, max(0.0, end - time.perf_counter())))
            arrow_key(key, False)
        time.sleep(0.15)                                 # let the camera settle

    def _focus_for_test(self, seconds=10):
        return self.wait_focus_for_test(seconds)

    def test_turn(self, degrees):
        if self._focus_for_test():
            self.app.log(f"Camera: turning {abs(degrees)} degrees {'left' if degrees < 0 else 'right'} "
                         f"({abs(degrees) / 90 * self.cam_90_secs():.2f} s)")
            self.rotate_camera(degrees)

    # ---------- spawn ----------
    def scan_area(self):
        """Your box (Spawn -> Set area), or None = the Roblox window without the HUD rows and the chat column."""
        r = self.app.settings.get("regions", {}).get("umbral_scan") or [0, 0, 0, 0]
        return list(r) if r[2] > r[0] and r[3] > r[1] else None

    def _view(self):
        """The part of the screen the spawn checks look at."""
        own = self.scan_area()
        if own:
            return self.utils.capture_screen_bgr(own)
        img = self.utils.capture_screen_bgr(list(self.get_roblox_window_region()))
        if img is None or not img.size:
            return img
        h, w = img.shape[:2]
        return img[:int(h * 0.8), int(w * 0.1):]                 # no HUD rows, no chat column

    # ----- picked colours (Pick + tolerance, like Fishing) -----
    def picked(self, key):
        """(rgb, tolerance) the user picked for 'crystal' / 'jug', or (None, tol) = use the automatic check."""
        c = self.app.settings.get(f"umbral_{key}_color")
        try:
            tol = int(float(self.app.settings.get(f"umbral_{key}_tol", PICK_TOL[key])))
        except (TypeError, ValueError):
            tol = PICK_TOL[key]
        return (tuple(int(v) for v in c[:3]) if c else None), tol

    @staticmethod
    def hue_match(img, rgb, tol, scene_v=128.0):
        """Lighting-proof match for the Juggernaut colours: the same HUE (red stays red when fog makes it pink),
        enough colour, and the same kind of brightness - a dark pick only matches things darker than the scene,
        a bright pick only things that aren't dark. Tol 1-80 = hue +-2..20 (of 180): fog turns its red marks
        pink / magenta (night ~177, morning ~171, blue fog ~162), so Tol 40-64 covers every lighting."""
        px = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
        ph, ps, pv = (int(v) for v in cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0])
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        H, S, V = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
        dh = np.abs(H - ph)
        dh = np.minimum(dh, 180 - dh)                    # hue wraps round (red is at both ends)
        ok = (dh <= max(2, tol // 4)) & (S >= max(40, ps // 2))
        if pv < scene_v * 0.6:
            ok &= V < scene_v * JUG_DARK_RATIO           # a dark pick (its body): darker than the scene
        else:
            ok &= V >= 60                                # a bright pick (its marks): not a dark shadow
        return ok

    @staticmethod
    def color_match(img, rgb, tol):
        """Pixels within `tol` of the RGB colour on every channel."""
        r, g, b = rgb
        c = np.array([b, g, r], np.int16)
        return cv2.inRange(img, np.clip(c - tol, 0, 255).astype(np.uint8),
                           np.clip(c + tol, 0, 255).astype(np.uint8)) > 0

    def crystal_min(self):
        try:
            return max(0.05, float(self.app.settings.get("umbral_crystal_min", CRYSTAL_MIN)))
        except (TypeError, ValueError):
            return CRYSTAL_MIN

    def crystal_share(self, img):
        """% of the picture that's crystal: your picked colour (within its tolerance), else the glowing purple."""
        if img is None or not img.size:
            return 0.0
        rgb, tol = self.picked("crystal")
        if rgb:
            return float(self.color_match(img, rgb, tol).mean()) * 100
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m = (hsv[..., 0] >= 125) & (hsv[..., 0] <= 150) & (hsv[..., 1] >= 110) & (hsv[..., 2] >= 120)
        return float(m.mean()) * 100

    def key_wait(self):
        try:
            return max(0.2, float(self.app.settings.get("umbral_key_wait", 1.0)))
        except (TypeError, ValueError):
            return 1.0

    def respawn(self):
        """Esc -> R -> Enter (respawn), waiting after every key. wait_spawned() then waits for the health bar."""
        with RobloxInputDriver._lock:
            tap_scan(0x01)                               # Esc
            time.sleep(self.key_wait())
            self.utils.send_key('r')
            time.sleep(self.key_wait())
            tap_scan(0x1C)                               # Enter
        time.sleep(1.5)                                  # the old character / health bar is still shown briefly

    # ----- 'fully spawned' = the health bar picture is on screen -----
    @staticmethod
    def health_path():
        from settings import get_base_path
        return os.path.join(get_base_path(), "umbral_health_bar.png")

    def capture_health_bar(self, region):
        """Save a picture of the health bar AND where it is (drag a box around it while spawned), like the OK button."""
        img = self.utils.capture_screen_bgr(region)
        if img is None or img.size == 0 or min(img.shape[:2]) < 6:
            return False
        self._health_tpl = None
        self.app.settings.settings.setdefault("regions", {})["umbral_health"] = [int(v) for v in region]
        self.app.settings.save()
        return cv2.imwrite(self.health_path(), img)

    def health_match(self):
        try:
            return min(0.99, max(0.5, float(self.app.settings.get("umbral_health_match", HEALTH_MATCH))))
        except (TypeError, ValueError):
            return HEALTH_MATCH

    def has_health_bar(self):
        return os.path.exists(self.health_path())

    def health_bar_score(self):
        """0..1 how well the health bar picture is found around where it was captured (None = no picture)."""
        if getattr(self, "_health_tpl", None) is None:
            img = cv2.imread(self.health_path()) if self.has_health_bar() else None
            self._health_tpl = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img is not None else None
        tpl = self._health_tpl
        if tpl is None:
            return None
        box = self.app.settings.get("regions", {}).get("umbral_health") or [0, 0, 0, 0]
        if box[2] > box[0] and box[3] > box[1]:
            pad = max(40, (box[3] - box[1]) * 2)        # some slack: the bar may sit a little differently
            area = self.utils.capture_screen_bgr([max(0, box[0] - pad), max(0, box[1] - pad), box[2] + pad, box[3] + pad])
        else:                                            # picture from before the spot was saved: lower half of the window
            l, t, r, b = self.get_roblox_window_region()
            area = self.utils.capture_screen_bgr([l, t + (b - t) // 2, r, b])
        if area is None or area.shape[0] < tpl.shape[0] or area.shape[1] < tpl.shape[1]:
            return 0.0
        res = cv2.matchTemplate(cv2.cvtColor(area, cv2.COLOR_BGR2GRAY), tpl, cv2.TM_CCOEFF_NORMED)
        return float(res.max())

    def wait_spawned(self, timeout=25.0):
        """Wait (pressing nothing) until the character is fully spawned: the health bar is back. Also covers dying -
        it just waits out the black screen. With no health bar picture: until the screen isn't black."""
        end = time.time() + timeout
        if not self.has_health_bar():
            if not getattr(self, "_warned_health", False):
                self.app.log("No health bar picture yet (Settings -> Spawn -> Capture) - waiting for a non-black screen.")
                self._warned_health = True
            while self.running and time.time() < end:
                img = self._view()
                if img is not None and img.size and float(img.mean()) > 40:
                    time.sleep(1.0)
                    return True
                time.sleep(0.3)
            return False
        while self.running and time.time() < end:
            if (self.health_bar_score() or 0) >= self.health_match():
                time.sleep(0.5)                          # let the spawn finish appearing
                return True
            time.sleep(0.3)
        return False

    def test_health_bar(self):
        if not self._focus_for_test():
            return
        hb = self.health_bar_score()
        if hb is None:
            self.app.log("Health bar: no picture yet - Capture it first.")
        else:
            self.app.log(f"Health bar: match {hb * 100:.0f}% (needs {self.health_match() * 100:.0f}%) -> "
                         + ("seen = fully spawned" if hb >= self.health_match() else "NOT seen"))

    def scroll_notches(self):
        try:
            return max(0, int(float(self.app.settings.get("umbral_scroll", 15))))
        except (TypeError, ValueError):
            return 15

    def zoom_out(self):
        """Mouse wheel down over the middle of the game (zooms the camera out) before looking for the crystals."""
        n = self.scroll_notches()
        if not n:
            return
        from pynput.mouse import Controller as MouseController
        l, t, r, b = self.get_roblox_window_region()
        x, y = (l + r) // 2, t + (b - t) // 3
        with RobloxInputDriver._lock:
            mc = MouseController()
            sx, sy = mc.position
            for k in range(1, 13):                       # Roblox misses an instant jump: glide, wiggle, then scroll
                self.utils.mouse_move(int(sx + (x - sx) * k / 12), int(sy + (y - sy) * k / 12))
                time.sleep(0.015)
            for dx in (3, -3, 0):
                self.utils.mouse_move(x + dx, y)
                time.sleep(0.04)
            for _ in range(n):
                mc.scroll(0, -1)
                time.sleep(0.05)
        time.sleep(0.6)                                  # let the camera settle

    def ensure_crystal_spawn(self, tries=8):
        """Respawn until the character is at the crystal spawn (the 2nd one). True once it is.
        Every check: wait until fully spawned (health bar) -> scroll down -> look for the crystals."""
        for n in range(tries + 1):
            if not self.running:
                return False
            if not self.wait_spawned():
                self.app.log("   not fully spawned after 25 s (health bar not seen) - checking anyway")
            self.zoom_out()
            share = self.crystal_share(self._view())
            if share >= self.crystal_min():
                self.app.log(f"At the crystal spawn ({share:.1f}% crystals).")
                return True
            if n == tries:
                break
            self.app.log(f"Not at the crystal spawn ({share:.1f}% crystals) - respawning (Esc, R, Enter)...")
            self.respawn()
        self.app.log(f"Couldn't get the crystal spawn after {tries} respawns.")
        return False

    def test_spawn_check(self):
        if self.running:
            self.app.log("Stop the macro before Check spawn.")
            return
        if not self._focus_for_test():
            return
        self.running = True
        try:
            hb = self.health_bar_score()
            self.app.log("Spawn check: health bar " + ("- no picture yet" if hb is None else
                         f"{hb:.2f} ({'spawned' if hb >= self.health_match() else 'NOT seen'})"))
            self.zoom_out()
            share = self.crystal_share(self._view())
            self.app.log(f"Spawn check: {share:.1f}% crystals -> "
                         + ("crystal spawn" if share >= self.crystal_min() else "NOT the crystal spawn"))
        finally:
            self.running = False

    def test_go_crystal_spawn(self):
        if self.running:
            self.app.log("Stop the macro before Go to crystal spawn.")
            return
        if not self._focus_for_test():
            return
        self.running = True                              # respawning runs while this is set; Stop clears it
        try:
            self.ensure_crystal_spawn()
        finally:
            self.running = False

    def after_spawn_key(self):
        """The key pressed once the crystal spawn is confirmed (default G), then the usual wait after a key."""
        key = str(self.app.settings.get("umbral_spawn_key", "g") or "").strip().lower()
        if key and self.running:
            self.app.log(f"Pressing {key.upper()}.")
            with RobloxInputDriver._lock:
                self.utils.send_key(key)
            time.sleep(self.key_wait())

    # ---------- the 3 locations ----------
    # ---------- loadouts: a named bundle of the 3 location routes ----------
    def loadouts(self):
        """{loadout name: [route for location 1..3]}. The old single list becomes 'Default'."""
        st = self.app.settings.settings
        lo = st.get("umbral_loadouts")
        if not isinstance(lo, dict) or not lo:
            old = list(st.get("umbral_locations") or [])
            lo = {"Default": (old + [""] * LOCATIONS)[:LOCATIONS]}
            st["umbral_loadouts"] = lo
            st["umbral_loadout"] = "Default"
        return lo

    def active_loadout(self):
        lo = self.loadouts()
        name = self.app.settings.get("umbral_loadout")
        return name if name in lo else next(iter(lo))

    def set_active_loadout(self, name):
        if name in self.loadouts():
            self.app.settings.set("umbral_loadout", name)

    def new_loadout(self, name=None):
        """A new loadout with 3 new, empty routes of its own ('<name> 1..3') - record them and it's ready."""
        lo = self.loadouts()
        if not name:
            n = 1
            while f"Loadout {n}" in lo:
                n += 1
            name = f"Loadout {n}"
        name = self._clean_name(name)
        if not name or name in lo:
            return None
        routes = []
        for i in range(LOCATIONS):
            base, k = f"{name} {i + 1}", 1
            rn = base
            while self.name_taken(rn):
                k += 1
                rn = f"{base} ({k})"
            routes.append(self.create_route(rn) or "")
        lo[name] = routes
        self.app.settings.settings["umbral_loadout"] = name
        self.set_active_route(routes[0])
        self.app.settings.save()
        return name

    def rename_loadout(self, old, new):
        lo = self.loadouts()
        new = self._clean_name(new or "")
        if old not in lo or not new or new in lo:
            return None
        lo[new] = lo.pop(old)
        if self.app.settings.get("umbral_loadout") == old:
            self.app.settings.settings["umbral_loadout"] = new
        self.app.settings.save()
        return new

    def delete_loadout(self, name):
        """Removes the bundle only - its routes stay (delete those in the route list if you want)."""
        lo = self.loadouts()
        if name not in lo or len(lo) <= 1:
            return False
        lo.pop(name)
        if self.app.settings.get("umbral_loadout") == name:
            self.app.settings.settings["umbral_loadout"] = next(iter(lo))
        self.app.settings.save()
        return True

    def rename_route(self, old, new):
        new = super().rename_route(old, new)
        if new:                                          # loadouts follow the new name
            for routes in self.loadouts().values():
                routes[:] = [new if r == old else r for r in routes]
            self.app.settings.save()
        return new

    def location_routes(self):
        """[route name or '' for location 1..3] of the active loadout."""
        r = list(self.loadouts().get(self.active_loadout()) or [])
        return (r + [""] * LOCATIONS)[:LOCATIONS]

    def set_location_route(self, i, name):
        r = self.location_routes()
        r[i] = "" if name in ("", "(none)") else name
        self.loadouts()[self.active_loadout()] = r
        self.app.settings.set("umbral_locations", r)            # older versions read this

    def walk_route(self, name):
        route = self.load_route(name)
        if not route:
            self.app.log(f"   route '{name}' has no recording - skipped (record it with {self.rec_key()}).")
            return False
        seg = route["segments"][0] if route["segments"] else route["return"]
        self.play_segment(seg, label=name)
        self._wait_still()
        return self.running

    # ---------- the Juggernaut ----------
    def jug_seen(self, img=None, info=None):
        """(found, corrupted, (x, y) on screen or None). With a picked colour: the biggest patch of that colour
        (at least 'min pixels'); else the automatic check (dark body with small red marks). Purple haze around it
        = corrupted. Your character (middle), the top bar, the HUD and the side panels are left out."""
        l, t = 0, 0
        if img is None:
            l, t, r, b = self.get_roblox_window_region()
            img = self.utils.capture_screen_bgr([l, t, r, b])
        if img is None or not img.size:
            return False, False, None
        h, w = img.shape[:2]
        m = np.zeros((h, w), bool)
        box = self.app.settings.get("regions", {}).get("umbral_jug_area") or [0, 0, 0, 0]
        if box[2] > box[0] and box[3] > box[1]:          # your box (Juggernaut -> Set area)
            m[max(0, box[1] - t):max(0, box[3] - t), max(0, box[0] - l):max(0, box[2] - l)] = True
            if info is not None:
                info["area"] = f"your area {box[2] - box[0]}x{box[3] - box[1]}"
                if not m.any():
                    info["area"] += " - it's OUTSIDE the Roblox window, set it again"
        else:
            if info is not None:
                info["area"] = "the whole view (no area set)"
            m[int(h * 0.12):int(h * 0.66), int(w * 0.16):int(w * 0.84)] = True
            cx, cy = w // 2, int(h * 0.5)
            m[cy - int(h * 0.18):cy + int(h * 0.14), cx - int(w * 0.07):cx + int(w * 0.07)] = False
        rgb, tol = self.picked("jug")
        if rgb:
            rgb2, tol2 = self.picked("jug2")
            found, corrupted, pos = self.find_color_target(img, m, rgb, tol, self.jug_min_px(), rgb2, tol2,
                                                           self.jug_min_px("jug2", 5), w, h, self.jug_near(), info)
        else:
            found, corrupted, pos = self.find_jug(img, m, w, h)
        return found, corrupted, ((l + pos[0], t + pos[1]) if pos else None)

    def jug_min_px(self, key="jug", default=15):
        try:
            return max(1, int(float(self.app.settings.get(f"umbral_{key}_min", default))))
        except (TypeError, ValueError):
            return default

    def jug_near(self):
        try:
            return max(1, int(float(self.app.settings.get("umbral_jug_near", JUG_NEAR))))
        except (TypeError, ValueError):
            return JUG_NEAR

    @classmethod
    def find_color_target(cls, img, m, rgb, tol, min_px, rgb2=None, tol2=25, min_px2=5, full_w=None, full_h=None,
                          near=None, info=None):
        """The biggest patch of colour 1 inside mask m (pixels close together count as one patch). With colour 2
        picked too, only colour-1 pixels that have colour 2 within `near` px count (and only colour-2 pixels with
        colour 1 that close): its red marks sit right ON its dark body, so a red thing and a dark thing that are
        merely on screen together don't count."""
        scene = float(np.median(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 2][m])) if m.any() else 128.0
        info = info if info is not None else {}
        hit = cls.hue_match(img, rgb, tol, scene) & m
        hit2 = (cls.hue_match(img, rgb2, tol2, scene) & m) if rgb2 else None
        info.update(c1=int(hit.sum()), c2=int(hit2.sum()) if hit2 is not None else None, min1=min_px,
                    min2=min_px2, near=near or JUG_NEAR, rejected={})
        if info["c1"] < min_px:
            info["why"] = "too few colour 1 pixels - raise Colour 1's Tol or pick it again"
            return False, False, None
        if hit2 is not None:
            if info["c2"] < min_px2:
                info["why"] = "too few colour 2 pixels - raise Colour 2's Tol or pick it again"
                return False, False, None
            k = np.ones((2 * (near or JUG_NEAR) + 1,) * 2, np.uint8)
            close1 = hit & cv2.dilate(hit2.astype(np.uint8), k).astype(bool)    # red with dark next to it
            hit2 = hit2 & cv2.dilate(hit.astype(np.uint8), k).astype(bool)      # dark with red next to it
            hit = close1
            info["close"] = int(hit.sum())
            if info["close"] < min_px:
                info["why"] = "both colours are on screen but not close together - not the Juggernaut"
                return False, False, None
        n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(hit.astype(np.uint8), np.ones((25, 25), np.uint8)))
        best, best_n = None, 0
        full_w, full_h = full_w or img.shape[1], full_h or img.shape[0]
        for i in range(1, n):
            x, y, bw, bh, _ = (int(v) for v in st[i])
            rej = info["rejected"]
            if bw > full_w * 0.12 or bh > full_h * 0.3:
                rej["too big (a wall / the sky)"] = rej.get("too big (a wall / the sky)", 0) + 1
                continue                                 # bigger than the Juggernaut can be: a wall / the sky
            patch = lab == i
            cnt = int(hit[patch].sum())
            if cnt < min_px:
                rej["too few pixels"] = rej.get("too few pixels", 0) + 1
                continue
            if cnt <= best_n:
                continue
            if cnt > 0.35 * bw * bh:
                rej["a solid block of colour 1"] = rej.get("a solid block of colour 1", 0) + 1
                continue                                 # a solid block of colour 1 (a red rock), not its small marks
            if hit2 is not None and int(hit2[patch].sum()) < min_px2:
                rej["not enough colour 2 on it"] = rej.get("not enough colour 2 on it", 0) + 1
                continue                                 # colour 1 without colour 2 on it: not the Juggernaut
            best, best_n = i, cnt
        if best is None:
            info["why"] = "every spot was ruled out: " + ", ".join(f"{n}x {r}" for r, n in info["rejected"].items())
            return False, False, None
        info["marks"] = best_n
        x, y, bw, bh, _ = (int(v) for v in st[best])
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        purple = (hsv[..., 0] >= 125) & (hsv[..., 0] <= 155) & (hsv[..., 1] >= 80) & (hsv[..., 2] >= 80)
        haze = int(purple[max(0, y - bh):y + bh * 2, max(0, x - bw):x + bw * 2].sum())
        return True, haze >= JUG_PURPLE_MIN, (x + bw // 2, y + bh // 2)

    @staticmethod
    def find_jug(img, m, full_w, full_h):
        """The colour check inside mask m. full_w / full_h = the game window's size (for the size limits).
        Lighting changes a lot (bright fog: body ~70; dark cave: body ~33), so 'dark' is relative to the scene."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        scene = float(np.median(V[m])) if m.any() else 100.0
        dark_below = min(95.0, max(40.0, scene * JUG_DARK_RATIO))
        red = ((H >= 165) | (H <= 8)) & (S >= 100) & (V >= 35)            # dim or bright red marks
        purple = (H >= 125) & (H <= 155) & (S >= 80) & (V >= 80)
        body = cv2.morphologyEx(((V < dark_below) & m).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, _, st, _ = cv2.connectedComponentsWithStats(body)
        for i in range(1, n):
            x, y, bw, bh, a = (int(v) for v in st[i])
            if a < 60 or bh < 12 or bw > full_w * 0.12 or bh > full_h * 0.3:
                continue                                 # too small to be it, or a big shadow / wall
            x1, y1 = max(0, x - 4), max(0, y - 4)
            reds = int(red[y1:y + bh + 4, x1:x + bw + 4].sum())
            # small red MARKS (a few % of its box) - not a red roof / carpet (10-80 %)
            if reds >= JUG_RED_MIN and reds <= 0.08 * (bw + 8) * (bh + 8):
                hx1, hy1 = max(0, x - bw), max(0, y - bh)
                haze = int(purple[hy1:y + bh * 2, hx1:x + bw * 2].sum())
                return True, haze >= JUG_PURPLE_MIN, (x + bw // 2, y + bh // 2)
        return False, False, None

    @property
    def skills(self):
        """The Moves tab's engine (the Skill Macro's move list, Umbral's own copy)."""
        if getattr(self, "_skills", None) is None:
            from logic_umbral_moves import UmbralMoves
            self._skills = UmbralMoves(self)
        return self._skills

    def click(self, btn="m2"):
        """One click wherever the mouse is: M2 = right (default), M1 = left."""
        from pynput.mouse import Button, Controller as MouseController
        button = Button.right if btn == "m2" else Button.left
        mouse = MouseController()
        with RobloxInputDriver._lock:
            mouse.press(button)
            time.sleep(0.04)
            mouse.release(button)

    def alive_target(self):
        """Still there: its colour is still on screen."""
        return self.jug_seen()[0]

    def reset_secs(self):
        try:
            return max(3.0, float(self.app.settings.get("umbral_reset_secs", 15)))
        except (TypeError, ValueError):
            return 15.0

    def aim_at(self, pos, steps=8):
        """Glide the mouse onto the Juggernaut (Roblox misses an instant jump) so the moves go at it."""
        if not pos:
            return
        from pynput.mouse import Controller as MouseController
        x, y = pos
        sx, sy = MouseController().position
        for k in range(1, steps + 1):
            self.utils.mouse_move(int(sx + (x - sx) * k / steps), int(sy + (y - sy) * k / steps))
            time.sleep(0.012)

    def fight(self, corrupted, pos=None):
        """Like the Skill Macro's rotation: cast the highest READY move again and again (aimed at the Juggernaut
        when a move aims there) until it's dead or 'Reset after' seconds have passed. Dead = one of your kill
        words shows in the kill-popup box (Moves tab); with no box set: its colour gone twice in a row.
        Returns True when it's dead."""
        sk = self.skills
        usable = [(i, m) for i, m in enumerate(sk.moves(), start=1) if m["enabled"] and m["key"]]
        if not usable:
            self.app.log("   no moves set (Moves tab).")
            return False
        if not any(sk.has_template(i) or float(m.get("cooldown") or 0) > 0 for i, m in usable):
            # without a snapshot (ready check) or a cooldown a move is never 'ready', so nothing would cast
            self.say("   Moves can't cast: take their snapshots (Moves -> Snapshot all) or give them a cooldown.")
            return False
        by_popup = sk.kill_region() is not None
        # a popup still showing from an earlier kill doesn't count: wait until it has gone first
        stale = by_popup and sk.kill_word_in(sk.read_kill_text()) is not None
        last = [pos]

        def where():
            p = self.jug_seen()[2]
            if p:
                last[0] = p
            return last[0]
        end, n = time.time() + self.reset_secs(), 0
        sk.cast_count, sk.last_cast, sk._still = {}, {}, {}
        while self.running and time.time() < end:
            pick = sk.pick_move(sk.read_slots())
            if pick:
                slot, m = pick
                if sk.cast(slot, m, where):
                    n += 1
                    self.app.log(f"   cast {m['name'] or 'slot ' + str(slot)} [{m['key']}]")
            else:
                time.sleep(max(0.05, float(sk.cfg["rotation"]["tick"])))
            if by_popup:
                word = sk.kill_word_in(sk.read_kill_text())
                if stale:
                    stale = word is not None
                    continue
                dead = word is not None
            else:
                dead = not self.alive_target() and not self.alive_target()
                word = None
            if dead:
                self.app.log(f"   Juggernaut down ({'corrupted, ' if corrupted else ''}{n} cast(s)"
                             + (f", '{word}' popup" if word else "") + ").")
                self.kills = getattr(self, "kills", 0) + 1
                return True
        if self.running:
            self.app.log(f"   not confirmed dead after {self.reset_secs():.0f} s - resetting.")
        return False

    def jug_checks(self):
        """(how many checks, seconds between them) before deciding it isn't at this location."""
        n = int(self._num("umbral_jug_checks", 2, 1))
        return max(1, n), self._num("umbral_jug_check_gap", 5, 0.5)

    def hunt_here(self, loc):
        """At the end of a route: is the Juggernaut there (colour check)? Not seen: look again every 'gap'
        seconds, up to 'checks' times in all, before moving on. Seen: fight it."""
        checks, gap = self.jug_checks()
        found = corrupted = pos = None
        for k in range(1, checks + 1):
            info = {}
            found, corrupted, pos = self.jug_seen(info=info)
            if found or not self.running:
                break
            if k < checks:
                self.say(f"Location {loc}: check {k}/{checks} - {self.check_summary(info, False)[11:]}"
                         f" - again in {gap:g} s")
                end = time.time() + gap
                while self.running and time.time() < end:
                    time.sleep(0.1)
        if not found:
            self.say(f"Location {loc}: no Juggernaut" + (f" after {checks} checks." if checks > 1 else "."))
            return False
        self.say(f"Location {loc}: Juggernaut seen{' (corrupted)' if corrupted else ''} - attacking.")
        return self.fight(corrupted, pos)

    def end_spots(self):
        """[spot 1, spot 2] clicked when all locations are done ([0, 0] = not set)."""
        s = list(self.app.settings.get("umbral_end_clicks") or [])
        old = self.app.settings.get("umbral_end_click")          # the first version had one spot
        if not s and old and any(old):
            s = [list(old)]
        return (s + [[0, 0], [0, 0]])[:2]

    def end_clicks(self):
        """When all locations are done: wait, click spot 1 (M1), wait, click spot 2. Unset spots are skipped."""
        spots = [p for p in self.end_spots() if any(p)]
        if not spots:
            return
        try:
            wait = max(0.0, float(self.app.settings.get("umbral_end_click_wait", 1.0)))
        except (TypeError, ValueError):
            wait = 1.0
        self.app.log(f"All locations done - main menu clicks ({len(spots)}).")
        for p in spots:
            if not self.running:
                return
            time.sleep(wait)
            self._click_at(p)

    # ---------- server reset: main menu -> new server -> warm-up ----------
    def reset_on(self):
        return bool(self.app.settings.get("umbral_reset_server", False))

    def _num(self, key, default, minimum=0.0):
        try:
            return max(minimum, float(self.app.settings.get(key, default)))
        except (TypeError, ValueError):
            return default

    def click_delay(self):
        return RobloxInputDriver.click_delay()

    def _click_at(self, pos):
        """Move -> wait (Click delay) -> click, so the game has caught up with the mouse before the click."""
        if self.running:
            RobloxInputDriver.glide_click(*pos, duration=0.04)

    # ----- main menu = the server code box looks like it did when its spot was picked -----
    @staticmethod
    def menu_path():
        from settings import get_base_path
        return os.path.join(get_base_path(), "umbral_main_menu.png")

    def menu_mode(self):
        return "auto" if self.app.settings.get("umbral_menu_mode", "manual") == "auto" else "manual"

    def capture_menu(self, region):
        """Manual: your own picture of something only the main menu shows (drag a box while it's on screen)."""
        img = self.utils.capture_screen_bgr(region)
        if img is None or img.size == 0 or min(img.shape[:2]) < 6:
            return False
        self._menu_tpl = None
        self.app.settings.settings.setdefault("regions", {})["umbral_menu"] = [int(v) for v in region]
        self.app.settings.save()
        return cv2.imwrite(self.menu_path(), img)

    def has_menu_check(self):
        return self.menu_mode() == "auto" or os.path.exists(self.menu_path())

    def menu_score(self):
        """0..1 how well the main menu is found (None = Manual with nothing captured)."""
        auto = self.menu_mode() == "auto"
        if getattr(self, "_menu_tpl", None) is None or getattr(self, "_menu_tpl_auto", None) != auto:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu_box.png") if auto else self.menu_path()
            img = cv2.imread(path) if os.path.exists(path) else None
            self._menu_tpl = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img is not None else None
            self._menu_tpl_auto = auto
        tpl = self._menu_tpl
        if tpl is None:
            return None
        if not auto:                                     # your picture, around where you captured it
            box = self.app.settings.get("regions", {}).get("umbral_menu") or [0, 0, 0, 0]
            pad = 40
            area = self.utils.capture_screen_bgr([max(0, box[0] - pad), max(0, box[1] - pad), box[2] + pad, box[3] + pad])
            if area is None or area.shape[0] < tpl.shape[0] or area.shape[1] < tpl.shape[1]:
                return 0.0
            return float(cv2.matchTemplate(cv2.cvtColor(area, cv2.COLOR_BGR2GRAY), tpl, cv2.TM_CCOEFF_NORMED).max())
        # automatic: the 'Enter PS Code...' box in the lower right of the window, any window size
        l, t, r, b = self.get_roblox_window_region()
        area = self.utils.capture_screen_bgr([l + (r - l) // 2, t + (b - t) // 2, r, b])
        if area is None or not area.size:
            return 0.0
        gray = cv2.cvtColor(area, cv2.COLOR_BGR2GRAY)
        base, best = (b - t) / 1010.0, 0.0               # the built-in picture is from a 1080p screen
        for f in sorted((1.03 ** i for i in range(-20, 21)), key=lambda f: abs(f - 1)):   # nearest sizes first
            w, h = int(tpl.shape[1] * base * f), int(tpl.shape[0] * base * f)
            if w < 40 or h < 10 or w > gray.shape[1] or h > gray.shape[0]:
                continue
            res = cv2.matchTemplate(gray, cv2.resize(tpl, (w, h), interpolation=cv2.INTER_AREA), cv2.TM_CCOEFF_NORMED)
            best = max(best, float(res.max()))
            if best >= MENU_MATCH:
                break
        return best

    def menu_shown(self):
        return (self.menu_score() or 0) >= MENU_MATCH

    def test_menu(self):
        if not self._focus_for_test():
            return
        sc = self.menu_score()
        how = "automatic" if self.menu_mode() == "auto" else "your picture"
        if sc is None:
            self.app.log("Main menu check (Manual): nothing captured yet - Capture it first.")
        else:
            self.app.log(f"Main menu check ({how}): match {sc * 100:.0f}% (needs {MENU_MATCH * 100:.0f}%) -> "
                         + ("main menu" if sc >= MENU_MATCH else "NOT the main menu"))

    def join_new_server(self):
        """After Spot 1 / Spot 2 took it to the main menu: wait for the menu, click the server box, type your code,
        click Enter Server, then wait until fully spawned in the new server. True once it's in."""
        box = self.app.settings.get("umbral_server_box") or [0, 0]
        enter = self.app.settings.get("umbral_server_enter") or [0, 0]
        code = str(self.app.settings.get("umbral_server_code") or "").strip()
        if not (any(box) and any(enter) and code):
            self.app.log("Server reset: pick the server box and Enter Server spots and type the code first (Settings).")
            return False
        menu_wait = self._num("umbral_menu_wait", 20, 1)
        check = self.has_menu_check()
        self.app.log(f"Server reset: waiting for the main menu (up to {menu_wait:.0f} s)..." if check
                     else f"Server reset: waiting {menu_wait:.0f} s for the main menu...")
        end = time.time() + menu_wait
        while self.running and time.time() < end:
            if check and self.menu_shown():
                settle = self._num("umbral_menu_settle", 3.0, 0.0)
                self.app.log(f"Server reset: main menu found - waiting {settle:g} s for its buttons to settle.")
                time.sleep(settle)                       # the buttons slide in for a few seconds
                break
            time.sleep(0.3)
        else:
            if check and self.running:
                self.app.log(f"Server reset: main menu not seen after {menu_wait:.0f} s - clicking the server box anyway.")
        if not self.running:
            return False
        self._click_at(box)
        time.sleep(max(0.5, self.click_delay()))
        with RobloxInputDriver._lock:
            from utils import scan_key
            scan_key(0x1D, True); scan_key(0x1E, True); time.sleep(0.05)      # Ctrl+A: replace what's in the box
            scan_key(0x1E, False); scan_key(0x1D, False)
            time.sleep(0.1)
            import keyboard
            keyboard.write(code, delay=0.05)             # text: typed as characters, whatever the layout
        time.sleep(max(1.0, self.click_delay()))         # 'Generate Code' turns into 'Enter Server'
        if not self.running:
            return False
        self._click_at(enter)
        self.app.log(f"Server reset: entering server '{code}'...")
        time.sleep(3.0)
        if self.wait_spawned(timeout=90):
            self.app.log("Server reset: in the new server.")
            return True
        self.app.log("Server reset: not spawned after 90 s - carrying on anyway.")
        return True

    def warm_up(self):
        """For 'warm-up minutes': respawn, wait until spawned, stand still 'every X s', again. Then the normal loop."""
        minutes = self._num("umbral_warm_minutes", 5, 0)
        every = self._num("umbral_warm_every", 30, 1)
        if minutes <= 0:
            return
        self.app.log(f"Warm-up: respawning every {every:.0f} s for {minutes:g} min...")
        end = time.time() + minutes * 60
        while self.running and time.time() < end:
            self.respawn()
            self.wait_spawned()
            stop = min(end, time.time() + every)
            while self.running and time.time() < stop:
                time.sleep(0.2)
        if self.running:
            self.app.log("Warm-up done - back to the routes.")

    # ---------- tests ----------
    def test_hunt_check(self):
        """Look right now, without pressing anything."""
        if not self._focus_for_test():
            return
        info = {}
        found, corrupted, pos = self.jug_seen(info=info)
        how = ("your 2 colours" if self.picked("jug2")[0] else "your colour") if self.picked("jug")[0] else "automatic"
        self.app.log(f"Juggernaut check ({how}): "
                     + (f"FOUND at {pos}" + (" (corrupted)" if corrupted else "") if found else "NOT found"))
        for line in self.check_report(info, found):
            self.app.log("   " + line)
        self.say(self.check_summary(info, found, corrupted))       # last line = what the action bar shows

    def say(self, msg, hold=4):
        """Log a Juggernaut-check result and keep it on the action bar long enough to read."""
        try:
            self.app.log(msg, hold=hold)
        except TypeError:                                # a window whose log() has no hold
            self.app.log(msg)

    @staticmethod
    def check_summary(info, found, corrupted=False):
        """One short line for the action bar."""
        if found:
            return f"Juggernaut FOUND{' (corrupted)' if corrupted else ''} - {info.get('marks', '?')} marks on it"
        if "c1" not in info:
            return "Juggernaut NOT found"
        if info["c1"] < info["min1"]:
            return f"Juggernaut NOT found - colour 1: {info['c1']}/{info['min1']} px"
        if info["c2"] is not None and info["c2"] < info["min2"]:
            return f"Juggernaut NOT found - colour 2: {info['c2']}/{info['min2']} px"
        if "close" in info and info["close"] < info["min1"]:
            return f"Juggernaut NOT found - colours not close ({info['close']}/{info['min1']} px)"
        return "Juggernaut NOT found - " + (info.get("why") or "ruled out")[:50]

    @staticmethod
    def check_report(info, found):
        """What Check now saw, one line per step: each colour's pixels, how many are close together, and why not."""
        if "c1" not in info:
            return []
        ok = lambda n, need: "OK" if n >= need else "TOO FEW"
        out = [f"looked in: {info.get('area', '?')}",
               f"colour 1: {info['c1']} px (needs {info['min1']}) - {ok(info['c1'], info['min1'])}"]
        if info["c2"] is not None:
            out.append(f"colour 2: {info['c2']} px (needs {info['min2']}) - {ok(info['c2'], info['min2'])}")
        if "close" in info:
            out.append(f"close together (within {info['near']} px): {info['close']} px (needs {info['min1']}) - "
                       f"{ok(info['close'], info['min1'])}")
        if found:
            out.append(f"-> {info.get('marks', '?')} colour-1 pixels on the Juggernaut")
        elif info.get("why"):
            out.append(f"-> why not: {info['why']}")
        return out

    def test_kill_check(self):
        """Read the kill-popup box now and say what it read (nothing is pressed)."""
        sk = self.skills
        if not sk.kill_region():
            self.app.log("Kill check: drag the kill-popup box first (Moves tab).")
            return
        texts = sk.read_kill_text()
        word = sk.kill_word_in(texts)
        self.app.log(f"Kill check read: {' | '.join(texts) or '(nothing)'} -> "
                     + (f"KILL ('{word}')" if word else "no kill word"))

    def test_path(self):
        """Walk the selected route once (no fighting)."""
        if self.running:
            self.app.log("Stop the macro before testing a path.")
            return
        if not self._focus_for_test():
            return
        name = self.active_route()
        self.app.log(f"--- Test Path: walking route '{name or 'none'}' ---")
        self.running = True
        try:
            if self.walk_route(name):
                self.app.log("Arrived at the end of the recorded path.")
        finally:
            self.running = False

    def test_detection(self):
        self.test_spawn_check()

    def setup_problems(self):
        out = []
        locs = [(i + 1, n) for i, n in enumerate(self.location_routes()) if n]
        if not locs:
            out.append({"id": "umbral_no_routes", "block": True, "short": "No routes picked",
                        "go": ("Routes", "umbral_loc_0"),
                        "text": "No routes picked for the locations (Routes tab)."})
        for loc, name in locs:
            if not self.load_route(name):
                out.append({"id": f"umbral_unrecorded:{name}", "block": False,
                            "short": f"Location {loc} isn't recorded", "go": ("Routes", f"umbral_record_{loc - 1}"),
                            "text": f"Location {loc}: route '{name}' isn't recorded yet - it will be skipped "
                                    f"(Routes tab -> Record)."})
        if not self.has_health_bar():
            out.append({"id": "umbral_health", "block": False, "short": "No health bar picture",
                        "go": ("Spawn", "umbral_health"),
                        "text": "No health bar picture - 'fully spawned' is guessed from a non-black screen "
                                "(Spawn tab -> Health bar -> Capture)."})
        if not self.picked("crystal")[0]:
            out.append({"id": "umbral_crystal", "block": False, "short": "No crystal colour",
                        "go": ("Spawn", "umbral_pick_crystal"),
                        "text": "No crystal colour picked - the built-in purple is used (Spawn tab)."})
        if not self.picked("jug")[0]:
            out.append({"id": "umbral_jug_colour", "block": False, "short": "No Juggernaut colour",
                        "go": ("Juggernaut", "umbral_pick_jug"),
                        "text": "No Juggernaut colour picked - the less reliable automatic check is used "
                                "(Juggernaut tab -> Colour 1 / 2)."})
        sk = self.skills
        usable = [(i, m) for i, m in enumerate(sk.moves(), start=1) if m["enabled"] and m["key"]]
        if not any(sk.has_template(i) or float(m.get("cooldown") or 0) > 0 for i, m in usable):
            out.append({"id": "umbral_moves", "block": False, "short": "Moves have no snapshots",
                        "go": ("Moves", "umbral_snap"),
                        "text": "Moves can't cast: no snapshots (Moves tab -> Snapshot all) and no cooldowns."})
        if not sk.kill_region():
            out.append({"id": "umbral_kill_box", "block": False, "short": "No kill-popup box",
                        "go": ("Moves", "umbral_killbox"),
                        "text": "No kill-popup box - a kill is guessed from the Juggernaut's colour disappearing "
                                "(Moves tab -> Kill check -> Set box)."})
        if self.reset_on():
            if not (any(self.app.settings.get("umbral_server_box") or [0]) and
                    any(self.app.settings.get("umbral_server_enter") or [0]) and
                    str(self.app.settings.get("umbral_server_code") or "").strip()):
                out.append({"id": "umbral_reset", "block": False, "short": "Server reset isn't set up",
                            "go": ("Server reset", "umbral_server_box"),
                            "text": "Reset server is on but the server box / Enter Server spot / code isn't set "
                                    "(Server reset tab)."})
            elif not self.has_menu_check():
                out.append({"id": "umbral_menu", "block": False, "short": "No main menu picture",
                            "go": ("Server reset", "umbral_menu"),
                            "text": "Reset server: no main menu picture (Manual) - it just waits the full time "
                                    "(Server reset tab -> Capture menu, or pick Automatic)."})
        return out

    def main_loop(self):
        locs = [(i + 1, n) for i, n in enumerate(self.location_routes()) if n]
        if not locs:
            self.app.log("No routes set for the locations (Settings -> Locations) - nothing to do.")
            return
        self.kills, cycle = 0, 0
        self.app.log(f"Umbral Abyss Stone started: loadout '{self.active_loadout()}', {len(locs)} location(s).")
        if self.reset_on() and self.has_menu_check() and self.wait_for_roblox_focus() and self.menu_shown():
            self.app.log("Main menu detected - joining your server first.")
            if self.join_new_server():
                self.warm_up()
        while self.running:
            cycle += 1
            for loc, name in locs:
                if not self.running or not self.wait_for_roblox_focus():
                    break
                if not self.ensure_crystal_spawn():
                    self.running = False
                    break
                self.after_spawn_key()
                self.app.log(f"Location {loc}: walking route '{name}'...")
                if self.walk_route(name):
                    self.hunt_here(loc)
                if self.running and (loc, name) != locs[-1]:
                    self.respawn()                       # back to the start for the next route
            if self.running:
                self.app.log(f"=== Cycle {cycle} done - {self.kills} kill(s) so far ===")
                self.end_clicks()                        # the next cycle's crystal-spawn check respawns
                if self.reset_on() and self.running:
                    if self.join_new_server():
                        self.warm_up()
        self.app.log("Umbral Abyss Stone macro Stopped")
