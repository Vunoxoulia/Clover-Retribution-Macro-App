import os
import json
import shutil
import threading
import time
import keyboard
from utils import game_key
import numpy as np
import cv2
from logic_base import BaseLogic

OPPOSITE = {"w": "s", "s": "w", "a": "d", "d": "a"}

DEFAULT_MINE_HOLD = 3.0
DEFAULT_MINE_WAIT = 1.75


class RouteNav(BaseLogic):
    """Shared recorded-route navigation (used by the Mining and Library macros).

    Record a walk once (Ctrl+P to start/stop), tapping E at each target. Playback
    replays your keys, and with a locked top-down camera
    (USE_ALIGNMENT) also lines up on snapshots at checkpoints and targets.
    Routes live in <ROUTES_DIRNAME>/<name>/."""

    ROUTES_DIRNAME = "routes"
    ACTIVE_ROUTE_KEY = "active_route"
    USE_ALIGNMENT = True     # False for free 3rd-person cameras: no snapshot walking
    ROUTE_TARGET = "ore"     # what an E tap marks, for the recording messages ("wisp" in the Library)

    RECORD_KEYS = {"w", "a", "s", "d", "space", "shift", "left shift"}
    E_MARKS_TARGET = True    # Mining: every E tap marks an ore. Library: E is just a recorded key (one walk)
    CHECKPOINT_IDLE = 0.5   # stand still this long while recording -> checkpoint
    MIN_TAP = 0.05          # playback: a key is held at least this long, or Roblox can miss a quick tap

    # Snapshot matching (fractions of the window): skip top bar, HUD and minimap.
    SNAP_TEMPLATE = (0.29, 0.15, 0.71, 0.70)
    SNAP_SEARCH = (0.0, 0.06, 0.88, 0.83)
    SNAP_MIN_SCORE = 0.52   # real matches score 0.58+; look-alike spots ~0.44

    def __init__(self, app):
        super().__init__(app)
        self._probe_region = None
        self._rec_thread = None
        self._rec_stop = False
        self.lap_no = 0
        self._new_lap()


    # ================= Routes (multiple recordings) =================
    def _routes_dir(self):
        from settings import get_base_path
        d = os.path.join(get_base_path(), self.ROUTES_DIRNAME)
        os.makedirs(d, exist_ok=True)
        return d

    # A route that ships with the app (Library: VunVun's route). Always listed first, used by default,
    # and locked: it can't be recorded over, renamed, deleted or edited. Make your own with New.
    BUILTIN_ROUTE = None          # display name
    BUILTIN_DIR = None            # folder inside the app (tracked in git, not user data)

    def _builtin_dir(self):
        if not self.BUILTIN_ROUTE or not self.BUILTIN_DIR:
            return None
        from settings import get_base_path
        d = os.path.join(get_base_path(), self.BUILTIN_DIR)
        return d if os.path.exists(os.path.join(d, "route.json")) else None

    def is_locked(self, name=None):
        name = name or self.active_route()
        return bool(self._builtin_dir()) and name == self.BUILTIN_ROUTE

    def list_routes(self):
        d = self._routes_dir()
        own = sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)) and n != self.BUILTIN_ROUTE)
        return ([self.BUILTIN_ROUTE] if self._builtin_dir() else []) + own

    def active_route(self):
        name = self.app.settings.get(self.ACTIVE_ROUTE_KEY, "")
        routes = self.list_routes()
        if name in routes:
            return name
        return routes[0] if routes else ""

    def set_active_route(self, name):
        self.app.settings.set(self.ACTIVE_ROUTE_KEY, name)

    def route_dir(self, name=None):
        name = name or self.active_route()
        if self.is_locked(name):
            return self._builtin_dir()
        return os.path.join(self._routes_dir(), name) if name else ""

    @staticmethod
    def _clean_name(name):
        name = "".join(c for c in name.strip() if c.isalnum() or c in " -_").strip()
        return name[:40]

    def create_route(self, name):
        name = self._clean_name(name)
        if not name or name in self.list_routes() or name == self.BUILTIN_ROUTE:
            return None
        os.makedirs(self.route_dir(name))
        self.set_active_route(name)
        return name

    def rename_route(self, old, new):
        if self.is_locked(old):
            return None
        new = self._clean_name(new)
        if not new or new in self.list_routes() or old not in self.list_routes():
            return None
        os.rename(self.route_dir(old), self.route_dir(new))
        if self.app.settings.get(self.ACTIVE_ROUTE_KEY) == old:
            self.set_active_route(new)
        return new

    def delete_route(self, name):
        if self.is_locked(name):
            return
        if name in self.list_routes():
            shutil.rmtree(self.route_dir(name))
        if self.app.settings.get(self.ACTIVE_ROUTE_KEY) == name:
            self.set_active_route(self.active_route())

    def load_route(self, name=None):
        d = self.route_dir(name)
        try:
            with open(os.path.join(d, "route.json"), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_route(self, route, name=None):
        if self.is_locked(name):
            return                                       # the built-in route is never changed
        with open(os.path.join(self.route_dir(name), "route.json"), "w", encoding="utf-8") as f:
            json.dump(route, f, indent=1)


    # ================= Screen helpers =================
    def _screen(self):
        return self.utils.capture_screen_bgr(self.get_roblox_window_region())

    def game_view_clear(self):
        """True if Roblox is what's actually on screen in the middle of its window.
        Any window on top (this macro's log/settings, a browser...) gets into our
        screenshots and breaks snapshot matching, so we check before trusting them."""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            l, t, r, b = self.get_roblox_window_region()
            w, h = r - l, b - t
            buf = ctypes.create_unicode_buffer(256)
            for fx, fy in [(0.5, 0.45), (0.33, 0.3), (0.67, 0.3), (0.33, 0.62), (0.67, 0.62)]:
                hwnd = user32.WindowFromPoint(wintypes.POINT(l + int(w * fx), t + int(h * fy)))
                user32.GetWindowTextW(user32.GetAncestor(hwnd, 2), buf, 256)
                if "Roblox" not in buf.value:
                    return False
            return True
        except Exception:
            return True  # non-Windows / API unavailable: don't block

    def wait_for_clear_view(self, alive=None, timeout=15.0):
        alive = alive or (lambda: self.running)
        if self.game_view_clear():
            return True
        self.app.log("!! Something is covering the game (log or settings window?). "
                     "Move it off the Roblox window - waiting...")
        end = time.perf_counter() + timeout
        while alive() and time.perf_counter() < end:
            time.sleep(0.5)
            if self.game_view_clear():
                self.app.log("   view is clear again, continuing")
                return True
        return False

    def save_snapshot(self, path):
        if self.game_view_clear():
            cv2.imwrite(path, self._screen())
            return True
        self.app.log(f"   !! {os.path.basename(path)} not saved: game was covered")
        return False

    # ================= Walking =================
    def _ok_pause(self, held, alive):
        """An OK popup is being clicked (it freezes the character): let go of the held keys, wait
        until it's handled, then press them again. Returns the seconds spent, so the walk can resume
        exactly where it was instead of losing that time."""
        if not self.ok_busy.is_set():
            return 0.0
        t0 = time.perf_counter()
        for k in held:
            keyboard.release(k)
        self.app.log("   'Ok' popup: route paused")
        while self.ok_busy.is_set() and alive():
            time.sleep(0.05)
        time.sleep(0.3)                                  # let the game take control back
        for k in held:
            keyboard.press(k)
        return time.perf_counter() - t0

    def hold_key(self, key, seconds, alive=None):
        """Hold a key for `seconds` (an 'Ok' popup pauses the clock while it's being clicked)."""
        key = game_key(key)                              # WASD by position (AZERTY / QWERTZ)
        alive = alive or (lambda: self.running)
        if seconds <= 0:
            return alive()
        self.walking = True
        keyboard.press(key)
        end = time.perf_counter() + seconds
        try:
            while alive() and time.perf_counter() < end:
                end += self._ok_pause([key], alive)
                time.sleep(min(0.02, max(0.0, end - time.perf_counter())))
        finally:
            keyboard.release(key)
            self.walking = False
        return alive()

    def _wait_still(self, max_wait=0.5, alive=None):
        """Short pause so the character stops sliding before a snapshot is compared."""
        alive = alive or (lambda: self.running)
        end = time.perf_counter() + min(max_wait, 0.5)
        while alive() and time.perf_counter() < end:
            time.sleep(0.02)

    # ================= Line-up checks =================
    def route_checks(self):
        """Line-ups on snapshots (start spot, checkpoints). Mining can turn them off."""
        return True

    # ================= Snapshot alignment =================
    @staticmethod
    def _edges(img_bgr):
        """Outline map (wall edges, floor borders); robust to lighting changes."""
        g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (g.shape[1] // 2, g.shape[0] // 2), interpolation=cv2.INTER_AREA)
        g = cv2.GaussianBlur(g, (3, 3), 0)
        e = cv2.Canny(g, 20, 60)
        return cv2.dilate(e, np.ones((3, 3), np.uint8)).astype(np.float32)

    @classmethod
    def measure_offset(cls, snap_bgr, cur_bgr):
        """Returns (score, dx, dy): how well the snapshot was recognised, and how far
        (px) the scene is shifted from it. Scene shifted right => we're left of it."""
        h, w = snap_bgr.shape[:2]
        if cur_bgr.shape[:2] != (h, w):
            cur_bgr = cv2.resize(cur_bgr, (w, h))
        se, ce = cls._edges(snap_bgr), cls._edges(cur_bgr)
        H, W = se.shape
        tx0, ty0, tx1, ty1 = (int(cls.SNAP_TEMPLATE[0] * W), int(cls.SNAP_TEMPLATE[1] * H),
                              int(cls.SNAP_TEMPLATE[2] * W), int(cls.SNAP_TEMPLATE[3] * H))
        sx0, sy0, sx1, sy1 = (int(cls.SNAP_SEARCH[0] * W), int(cls.SNAP_SEARCH[1] * H),
                              int(cls.SNAP_SEARCH[2] * W), int(cls.SNAP_SEARCH[3] * H))
        res = cv2.matchTemplate(ce[sy0:sy1, sx0:sx1], se[ty0:ty1, tx0:tx1], cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        return float(score), (loc[0] + sx0 - tx0) * 2, (loc[1] + sy0 - ty0) * 2

    def align_to(self, snap_bgr, label, alive=None, max_tries=14):
        """Walk until the screen lines up with a saved snapshot.
        Returns 'ok', 'lost' (snapshot not recognised) or 'unsettled'.
        Self-calibrating: learns how many px one second of walking moves the scene."""
        alive = alive or (lambda: self.running)
        pps = float(self.app.settings.get("home_px_per_sec", 300.0))
        tol = int(self.app.settings.get("home_tolerance", 30))
        prev_err = None
        for _ in range(max_tries):
            if not alive():
                return "lost"
            if not self.wait_for_clear_view(alive):
                return "lost"
            score, dx, dy = self.measure_offset(snap_bgr, self._screen())
            if score < self.SNAP_MIN_SCORE:
                return "lost"
            err = max(abs(dx), abs(dy))
            if err <= tol:
                self.app.settings.set("home_px_per_sec", round(pps, 1))
                return "ok"
            # "Close enough": within 2x tolerance and the last push didn't help
            if prev_err is not None and err <= tol * 2 and err >= prev_err - 4:
                self.app.log(f"   {label}: close enough ({dx}, {dy}) px, accepting")
                return "ok"
            prev_err = err
            # Fix the bigger error first; aim a little short so we don't overshoot
            if abs(dx) >= abs(dy):
                key, axis, before = ("d" if dx > 0 else "a"), 0, dx
            else:
                key, axis, before = ("s" if dy > 0 else "w"), 1, dy
            secs = min(0.6, max(0.05, 0.8 * abs(before) / pps))
            self.app.log(f"   {label}: off by ({dx}, {dy}) px, match {score:.2f} -> {key.upper()} {secs:.2f}s")
            self.lap["corrections"] += 1
            self.hold_key(key, secs, alive=alive)
            self._wait_still(alive=alive)
            s2, dx2, dy2 = self.measure_offset(snap_bgr, self._screen())
            moved = abs(before - (dx2, dy2)[axis])   # actual distance travelled, even on overshoot
            if s2 >= self.SNAP_MIN_SCORE and moved > 8:
                pps = min(2000.0, max(60.0, 0.5 * pps + 0.5 * (moved / secs)))
        return "unsettled"

    # ----- Home (the route's start spot) -----
    def _home_path(self):
        return os.path.join(self.route_dir(), "home.png")

    def has_home(self):
        return bool(self.active_route()) and os.path.exists(self._home_path())

    def capture_home(self):
        if not self.active_route():
            self.app.log("Create or select a route first.")
            return
        if self.save_snapshot(self._home_path()):
            self.app.log(f"Home saved for route '{self.active_route()}'.")

    def align_home(self, alive=None):
        alive = alive or (lambda: self.running)
        if not self.route_checks():
            return alive()
        if not self.has_home():
            return True
        if not self.USE_ALIGNMENT:   # free camera: just check we're roughly at the start
            score, _, _ = self.measure_offset(cv2.imread(self._home_path()), self._screen())
            if score < self.SNAP_MIN_SCORE:
                self.app.log(f"   ! start spot not recognised (match {score:.2f}) - continuing anyway")
            return True
        result = self.align_to(cv2.imread(self._home_path()), "home", alive)
        if result == "lost":
            self.app.log("   start spot not recognised - continuing anyway")
        return alive()                                   # never stops the macro by itself

    # ================= Recording (Ctrl+P) =================
    _VK = {"space": 0x20, "shift": 0x10, "left shift": 0xA0, "right shift": 0xA1}

    @classmethod
    def _key_is_down(cls, name):
        """Is this key physically held right now (asks Windows, not the keyboard hook)?"""
        vk = cls._VK.get(name) or (ord(name.upper()) if len(name) == 1 else None)
        if vk is None:
            return True                                  # unknown key: trust the hook
        try:
            import ctypes
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return True
    def is_recording(self):
        return self._rec_thread is not None and self._rec_thread.is_alive()

    def toggle_recording(self):
        """Ctrl+P: start recording into the selected route, or finish the recording."""
        if self.is_recording():
            self._rec_stop = True
            return
        if self.running:
            self.app.log("Stop the macro before recording.")
            return
        if self.is_locked():
            self.app.log(f"🔒 '{self.BUILTIN_ROUTE}' is the built-in route and can't be recorded over. "
                         "Press New to make your own route, then Ctrl+P.")
            return
        if not self.active_route():
            self.create_route("Route 1")
            if hasattr(self.app, "refresh_routes"):
                self.app.root.after(0, self.app.refresh_routes)
        self._rec_stop = False
        self._rec_thread = threading.Thread(target=self._record, daemon=True)
        self._rec_thread.start()

    def _record(self):
        name = self.active_route()
        folder = self.route_dir(name)
        if not self.check_focus():
            self.app.log("Recording: click into Roblox now - starting in 3s...")
            time.sleep(3)
        if not self.game_view_clear():
            self.app.log("!! Recording NOT started: something is covering the Roblox window.")
            return
        old = self.load_route(name) or {}
        old_timers = [(s.get("mine_hold"), s.get("mine_wait")) for s in old.get("segments", [])]
        for f in os.listdir(folder):            # previous recording of this route
            if f.endswith(".png") or f == "route.json":
                os.remove(os.path.join(folder, f))
        self.save_snapshot(os.path.join(folder, "home.png"))

        st = {"seg_start": time.perf_counter(), "last_mark": 0.0,
              "idle_since": time.perf_counter(), "idle_t": 0.0, "cp_taken": True}
        segments, events, checkpoints, held = [], [], [], set()
        lock = threading.Lock()
        if self.ROUTE_TARGET == "ore":
            self.app.log(f"● RECORDING '{name}'. Walk the route, TAP E at each ore (as many as you like), then walk "
                         f"back to the start and press Ctrl+P. Everything after the last E = the walk back.")
        else:
            self.app.log(f"● RECORDING '{name}'. Walk to the {self.ROUTE_TARGET} (jumps, E... all recorded), "
                         f"then press Ctrl+P there.")
        if hasattr(self.app, "set_recording_ui"):
            self.app.root.after(0, lambda: self.app.set_recording_ui(True))

        def close_segment(now):
            for k in list(held):  # anything still held is released here
                events.append([round(now - st["seg_start"], 3), k, "up"])
            dur = round(now - st["seg_start"], 3)
            cps = [c for c in checkpoints if dur - c["t"] > 1.0]  # right before an ore = redundant
            seg = {"events": list(events), "duration": dur, "checkpoints": cps}
            events.clear(); checkpoints.clear()
            st["seg_start"] = now
            for k in held:  # still held: keep holding in the next segment
                events.append([0.0, k, "down"])
            return seg

        def on_event(ev):
            name_ = (ev.name or "").lower()
            now = time.perf_counter()
            with lock:
                if name_ == "e" and not self.E_MARKS_TARGET:
                    pass                                 # recorded like any other key below
                elif name_ == "e" and ev.event_type == "up":
                    st["e_held"] = False
                    return
                elif name_ == "e" and ev.event_type == "down":
                    # Holding E makes Windows repeat 'down'; a real new tap has an 'up' first
                    if st.get("e_held") or now - st["last_mark"] < 0.3:
                        return
                    st["e_held"] = True
                    st["last_mark"] = now
                    seg = close_segment(now)
                    idx = len(segments) + 1
                    hold, wait = old_timers[idx - 1] if idx <= len(old_timers) else (None, None)
                    seg["mine_hold"] = hold or DEFAULT_MINE_HOLD
                    seg["mine_wait"] = wait or DEFAULT_MINE_WAIT
                    segments.append(seg)
                    threading.Thread(target=lambda: (time.sleep(0.4), self.save_snapshot(
                        os.path.join(folder, f"ore_{idx}.png"))), daemon=True).start()
                    if self.ROUTE_TARGET == "ore":
                        self.app.log(f"   ore {idx} marked ({seg['duration']:.1f}s walk, "
                                     f"{len(seg['checkpoints'])} checkpoints)")
                    else:
                        self.app.log(f"   {self.ROUTE_TARGET} reached ({seg['duration']:.1f}s walk) — press Ctrl+P to finish")
                    st["cp_taken"] = True
                    return
                if name_ in self.RECORD_KEYS or (name_ == "e" and not self.E_MARKS_TARGET):
                    t = round(now - st["seg_start"], 3)
                    if ev.event_type == "down" and name_ not in held:
                        held.add(name_); events.append([t, name_, "down"])
                        st["cp_taken"] = False
                    elif ev.event_type == "up" and name_ in held:
                        held.discard(name_); events.append([t, name_, "up"])
                        if not held:
                            st["idle_since"], st["idle_t"] = now, t

        hook = keyboard.hook(on_event)
        try:
            while not self._rec_stop:
                time.sleep(0.05)
                with lock:
                    # A key-up the hook missed would leave the key 'held' forever, and every later tap of it
                    # (10 jumps -> 2) would be ignored. Ask Windows for the real state and close it here.
                    now = time.perf_counter()
                    for k in [k for k in held if not self._key_is_down(k)]:
                        held.discard(k)
                        events.append([round(now - st["seg_start"], 3), k, "up"])
                        if not held:
                            st["idle_since"], st["idle_t"] = now, round(now - st["seg_start"], 3)
                    ready = (self.USE_ALIGNMENT and not held and not st["cp_taken"]
                             and time.perf_counter() - st["idle_since"] >= self.CHECKPOINT_IDLE)
                    if ready:
                        st["cp_taken"] = True
                        seg_no, cp_no, t = len(segments) + 1, len(checkpoints) + 1, st["idle_t"]
                if ready:
                    fname = f"cp_{seg_no}_{cp_no}.png"
                    if self.save_snapshot(os.path.join(folder, fname)):
                        with lock:
                            checkpoints.append({"t": t, "file": fname})
                        self.app.log(f"   checkpoint {seg_no}.{cp_no} saved")
        finally:
            keyboard.unhook(hook)
            if hasattr(self.app, "set_recording_ui"):
                self.app.root.after(0, lambda: self.app.set_recording_ui(False))
        with lock:
            ret = close_segment(time.perf_counter())
        route = {"ores": len(segments), "segments": segments, "return": ret}
        self.save_route(route, name)
        n_cp = sum(len(sg["checkpoints"]) for sg in segments) + len(ret["checkpoints"])
        if self.ROUTE_TARGET == "ore":
            self.app.log(f"✓ Route '{name}' saved: {len(segments)} ore{'s' if len(segments) != 1 else ''} "
                         f"+ the walk back to the start ({ret['duration']:.1f}s), {n_cp} checkpoints.")
        elif not self.E_MARKS_TARGET:
            n_keys = sum(1 for e in ret["events"] if e[2] == "down")
            self.app.log(f"✓ Route '{name}' saved: walk to the {self.ROUTE_TARGET} ({ret['duration']:.1f}s, "
                         f"{n_keys} key presses incl. jumps / E).")
        elif segments:
            self.app.log(f"✓ Route '{name}' saved: walk to the {self.ROUTE_TARGET} ({segments[0]['duration']:.1f}s).")
        else:
            self.app.log(f"✓ Route '{name}' saved, but E was never tapped — the whole walk "
                         f"({ret['duration']:.1f}s) will be used to reach the {self.ROUTE_TARGET}.")
        if hasattr(self.app, "refresh_routes"):
            self.app.root.after(0, self.app.refresh_routes)

    # ================= Playback =================
    def play_segment(self, seg, label="", alive=None):
        """Replay recorded key presses with their original timing.
        At each checkpoint it lines up on the checkpoint snapshot, then continues."""
        alive = alive or (lambda: self.running)
        events = sorted(seg["events"], key=lambda e: e[0])
        cps = (sorted(seg.get("checkpoints", []), key=lambda c: c["t"])
               if self.USE_ALIGNMENT and self.route_checks() else [])
        folder = self.route_dir()
        start = time.perf_counter()
        shift = 0.0
        down, ei, ci = set(), 0, 0
        pressed_at = {}                                  # key -> when it went down (for the minimum tap)
        self.walking = True
        try:
            while alive():
                paused = self._ok_pause(list(down), alive)
                if paused:
                    shift += paused
                    continue
                now = time.perf_counter()
                t = now - start - shift
                while ei < len(events) and events[ei][0] <= t:
                    _, key, kind = events[ei]
                    ei += 1
                    if kind == "down":
                        if key in down:                  # pressed again without a release: re-tap it
                            keyboard.release(key)
                            time.sleep(0.02)
                        keyboard.press(key); down.add(key)
                        pressed_at[key] = time.perf_counter()
                    else:
                        # quick taps (jumps): keep the key down long enough for Roblox to see it
                        held_for = time.perf_counter() - pressed_at.get(key, 0)
                        if held_for < self.MIN_TAP:
                            time.sleep(self.MIN_TAP - held_for)
                            shift += self.MIN_TAP - held_for
                        keyboard.release(key); down.discard(key)
                if ci < len(cps) and cps[ci]["t"] <= t and not down:
                    cp = cps[ci]
                    ci += 1
                    path = os.path.join(folder, cp["file"])
                    if os.path.exists(path):
                        t0 = time.perf_counter()
                        self._wait_still(alive=alive)
                        res = self.align_to(cv2.imread(path), f"checkpoint {label}.{ci}", alive, max_tries=6)
                        if res == "lost":
                            self.app.log(f"   checkpoint {label}.{ci}: not recognised, carrying on")
                        shift += time.perf_counter() - t0
                    continue
                if ei >= len(events) and ci >= len(cps) and t >= seg["duration"]:
                    break
                time.sleep(0.004)
        finally:
            self.walking = False
            for k in down:
                keyboard.release(k)
        return alive()




    def wait_focus_for_test(self, seconds=5):
        """Tests started from the macro window's button: give the user time to click into Roblox."""
        if self.check_focus():
            return True
        self.app.log(f"Click into Roblox — the test starts as soon as it's focused (within {seconds}s)...")
        end = time.time() + seconds
        while time.time() < end:
            if self.check_focus():
                time.sleep(0.3)
                return True
            time.sleep(0.1)
        self.app.log("Roblox wasn't focused — test cancelled. (Tip: press the test hotkey from inside Roblox.)")
        return False

    def _new_lap(self):
        self.lap = {"start": time.perf_counter(), "mined": 0, "targets": 0, "nudges": 0,
                    "misses": 0, "corrections": 0}


    # ================= Tests =================


