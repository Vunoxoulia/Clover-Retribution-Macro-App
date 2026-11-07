import os
import json
import shutil
import threading
import time
import keyboard
from utils import press_key, position_name, key_scan_code
import numpy as np
import cv2
from logic_base import BaseLogic

DEFAULT_MINE_HOLD = 3.0
DEFAULT_MINE_WAIT = 1.75


class RouteNav(BaseLogic):

    ROUTES_DIRNAME = "routes"
    ACTIVE_ROUTE_KEY = "active_route"
    USE_ALIGNMENT = True
    ROUTE_TARGET = "ore"

    RECORD_KEYS = {"w", "a", "s", "d", "space", "shift", "left shift"}
    E_MARKS_TARGET = True
    CHECKPOINT_IDLE = 0.5
    MIN_TAP = 0.05

    SNAP_TEMPLATE = (0.29, 0.15, 0.71, 0.70)
    SNAP_SEARCH = (0.0, 0.06, 0.88, 0.83)
    SNAP_MIN_SCORE = 0.52

    def __init__(self, app):
        super().__init__(app)
        self._probe_region = None
        self._rec_thread = None
        self._rec_stop = False
        self.lap_no = 0
        self._new_lap()


    def _routes_dir(self):
        from settings import get_base_path
        d = os.path.join(get_base_path(), self.ROUTES_DIRNAME)
        os.makedirs(d, exist_ok=True)
        return d

    BUILTIN_ROUTE = None
    BUILTIN_DIR = None
    EXTRA_BUILTINS = ()

    def _builtins(self):
        from settings import get_app_path
        out = {}
        pairs = ([(self.BUILTIN_ROUTE, self.BUILTIN_DIR)] if self.BUILTIN_ROUTE else []) + list(self.EXTRA_BUILTINS)
        for name, folder in pairs:
            if name and folder:
                d = os.path.join(get_app_path(), folder)
                if os.path.exists(os.path.join(d, "route.json")):
                    out[name] = d
        return out

    def _builtin_dir(self, name=None):
        b = self._builtins()
        return b.get(name or self.BUILTIN_ROUTE)

    def is_locked(self, name=None):
        name = name or self.active_route()
        return name in self._builtins()

    def list_routes(self):
        d = self._routes_dir()
        b = self._builtins()
        own = sorted(n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n)) and n not in b)
        return list(b) + own

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
            return self._builtin_dir(name)
        return os.path.join(self._routes_dir(), name) if name else ""

    @staticmethod
    def _clean_name(name):
        name = "".join(c for c in name.strip() if c.isalnum() or c in " -_").strip()
        return name[:40]

    def name_taken(self, name):
        low = name.strip().lower()
        return any(n.lower() == low for n in list(self.list_routes()) + list(self._builtins()))

    def create_route(self, name):
        name = self._clean_name(name)
        if not name or self.name_taken(name):
            return None
        os.makedirs(self.route_dir(name))
        self.set_active_route(name)
        return name

    def free_route_name(self, base="My Route"):
        n = 1
        while self.name_taken(f"{base} {n}"):
            n += 1
        return f"{base} {n}"

    def rename_route(self, old, new):
        if self.is_locked(old):
            return None
        new = self._clean_name(new)
        if not new or old not in self.list_routes() or (self.name_taken(new) and new.lower() != old.lower()):
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

    def export_route(self, path, name=None):
        import zipfile
        name = name or self.active_route()
        d = self.route_dir(name)
        if not name or not os.path.exists(os.path.join(d, "route.json")):
            return False
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("route_info.json", json.dumps({"type": "route", "macro": self.ROUTES_DIRNAME, "name": name}))
            for f in os.listdir(d):
                if f == "route.json" or f.endswith(".png"):
                    z.write(os.path.join(d, f), f)
        return True

    def import_route(self, path):
        import zipfile
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            raise ValueError("That file isn't a route.")
        with z:
            names = z.namelist()
            try:
                info = json.loads(z.read("route_info.json").decode("utf-8"))
            except Exception:
                info = {}
            if "route.json" not in names or info.get("type", "route") != "route":
                raise ValueError("That file isn't a route.")
            if info.get("macro", self.ROUTES_DIRNAME) != self.ROUTES_DIRNAME:
                raise ValueError("That route is for a different macro.")
            base = self._clean_name(info.get("name") or os.path.splitext(os.path.basename(path))[0]) or "Imported"
            name, k = base, 2
            while self.name_taken(name):
                name, k = f"{base[:36]} {k}", k + 1
            d = os.path.join(self._routes_dir(), name)
            os.makedirs(d)
            for f in names:
                b = os.path.basename(f)
                if b == f and (b == "route.json" or b.endswith(".png")):
                    with z.open(f) as src, open(os.path.join(d, b), "wb") as out:
                        shutil.copyfileobj(src, out)
        self.set_active_route(name)
        return name

    @staticmethod
    def _read_route_file(path):
        with open(path, encoding="utf-8") as f:
            route = json.load(f)
        if not (isinstance(route, dict) and isinstance(route.get("segments"), list)
                and isinstance(route.get("return"), dict)):
            raise ValueError("not a route file")
        return route

    def _route_note(self, key, msg):
        seen = self.__dict__.setdefault("_route_notes", set())
        if key not in seen:
            seen.add(key)
            self.app.log(msg)

    def load_route(self, name=None):
        label = name or self.active_route()
        path = os.path.join(self.route_dir(name), "route.json")
        bak = path + ".bak"
        own = not self.is_locked(name)
        if not os.path.exists(path):
            if own and os.path.exists(bak):
                try:
                    route = self._read_route_file(bak)
                    shutil.copy2(bak, path)
                    self._route_note(("restored", path), f"Route '{label}': its file was missing - restored the backup.")
                    return route
                except Exception:
                    pass
            return None
        try:
            return self._read_route_file(path)
        except Exception as e:
            if not own:
                self._route_note(("broken", path), f"Built-in route '{label}' couldn't be read ({e}) - "
                                                   f"download the macro again.")
                return None
            try:
                os.replace(path, path + ".broken")
            except OSError:
                pass
            if os.path.exists(bak):
                try:
                    route = self._read_route_file(bak)
                    shutil.copy2(bak, path)
                    self._route_note(("restored", path), f"Route '{label}' was damaged - using its backup "
                                                         f"(the damaged file is kept as route.json.broken).")
                    return route
                except Exception:
                    pass
            self._route_note(("broken", path), f"Route '{label}' is damaged and has no usable backup - record it "
                                               f"again (the damaged file is kept as route.json.broken).")
            return None

    def save_route(self, route, name=None):
        if self.is_locked(name):
            return
        path = os.path.join(self.route_dir(name), "route.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(route, f, indent=1)
        if os.path.exists(path):
            try:
                shutil.copy2(path, path + ".bak")
            except OSError:
                pass
        os.replace(tmp, path)
        self.__dict__.get("_route_notes", set()).clear()


    def _screen(self):
        return self.utils.capture_screen_bgr(self.get_roblox_window_region())

    def game_view_clear(self):
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
            return True

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
            if cv2.imwrite(path, self._screen()):
                return True
            self.app.log(f"   !! {os.path.basename(path)} couldn't be saved to {os.path.dirname(path)}")
            return False
        self.app.log(f"   !! {os.path.basename(path)} not saved: game was covered")
        return False

    def _ok_pause(self, held, alive):
        if not self.ok_busy.is_set():
            return 0.0
        t0 = time.perf_counter()
        since = getattr(self, "_popup_since", None)
        before = min(1.0, max(0.0, t0 - since)) if since else 0.0
        for k in held:
            press_key(k, False)
        self.app.log(f"   Pop up: route paused (frozen ~{before:.1f} s before it was seen - walking that again)")
        while self.ok_busy.is_set() and alive():
            time.sleep(0.05)
        time.sleep(0.3)
        for k in held:
            press_key(k, True)
        return time.perf_counter() - t0 + before

    def hold_key(self, key, seconds, alive=None):
        alive = alive or (lambda: self.running)
        if seconds <= 0:
            return alive()
        self.walking = True
        press_key(key, True)
        end = time.perf_counter() + seconds
        try:
            while alive() and time.perf_counter() < end:
                end += self._ok_pause([key], alive)
                time.sleep(min(0.02, max(0.0, end - time.perf_counter())))
        finally:
            press_key(key, False)
            self.walking = False
        return alive()

    def _wait_still(self, max_wait=0.5, alive=None):
        alive = alive or (lambda: self.running)
        end = time.perf_counter() + min(max_wait, 0.5)
        while alive() and time.perf_counter() < end:
            time.sleep(0.02)

    def route_checks(self):
        return True

    @staticmethod
    def _edges(img_bgr):
        g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (g.shape[1] // 2, g.shape[0] // 2), interpolation=cv2.INTER_AREA)
        g = cv2.GaussianBlur(g, (3, 3), 0)
        e = cv2.Canny(g, 20, 60)
        return cv2.dilate(e, np.ones((3, 3), np.uint8)).astype(np.float32)

    @classmethod
    def measure_offset(cls, snap_bgr, cur_bgr):
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
            if prev_err is not None and err <= tol * 2 and err >= prev_err - 4:
                self.app.log(f"   {label}: close enough ({dx}, {dy}) px, accepting")
                return "ok"
            prev_err = err
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
            moved = abs(before - (dx2, dy2)[axis])
            if s2 >= self.SNAP_MIN_SCORE and moved > 8:
                pps = min(2000.0, max(60.0, 0.5 * pps + 0.5 * (moved / secs)))
        return "unsettled"

    def _home_path(self):
        return os.path.join(self.route_dir(), "home.png")

    def has_home(self):
        return bool(self.active_route()) and os.path.exists(self._home_path())

    def align_home(self, alive=None):
        alive = alive or (lambda: self.running)
        if not self.route_checks():
            return alive()
        if not self.has_home():
            return True
        if not self.USE_ALIGNMENT:
            score, _, _ = self.measure_offset(cv2.imread(self._home_path()), self._screen())
            if score < self.SNAP_MIN_SCORE:
                self.app.log(f"   ! start spot not recognised (match {score:.2f}) - continuing anyway")
            return True
        result = self.align_to(cv2.imread(self._home_path()), "home", alive)
        if result == "lost":
            self.app.log("   start spot not recognised - continuing anyway")
        return alive()

    _VK = {"space": 0x20, "shift": 0x10, "left shift": 0xA0, "right shift": 0xA1}

    @classmethod
    def _key_is_down(cls, name):
        vk = cls._VK.get(name)
        if vk is None and key_scan_code(name):
            try:
                import ctypes
                vk = ctypes.windll.user32.MapVirtualKeyW(key_scan_code(name), 1) or None
            except Exception:
                vk = None
        if vk is None:
            return True
        try:
            import ctypes
            return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return True
    def _record_key_backup(self, watch, seen, on_event, stop):
        from types import SimpleNamespace
        from utils import key_down
        state = {k: key_down(k) for k in watch}
        pending, said = [], False
        while not stop.is_set() and not self._rec_stop:
            time.sleep(0.01)
            now = time.perf_counter()
            for k in watch:
                d = key_down(k)
                if d != state[k]:
                    state[k] = d
                    pending.append((now, k, "down" if d else "up"))
            while pending and now - pending[0][0] >= 0.12:
                t0, k, kind = pending.pop(0)
                if seen.get(k, 0.0) < t0 - 0.25:
                    if not said:
                        said = True
                        self.app.log("   (the key hook missed a key - the backup key check is recording it)")
                    on_event(SimpleNamespace(name=k, scan_code=key_scan_code(k) or 0, event_type=kind,
                                             is_keypad=False, _t=t0))

    def is_recording(self):
        return self._rec_thread is not None and self._rec_thread.is_alive()

    def rec_key(self):
        k = (self.app.settings.get("hotkeys", {}) or {}).get("record") or "f9"
        return "+".join(p.upper() if len(p) <= 3 and p[:1] in "fF" and p[1:].isdigit() or len(p) == 1 else p.capitalize()
                        for p in k.split("+"))

    def toggle_recording(self, from_ore=None):
        if self.is_recording():
            if not getattr(self, "_rec_live", False):
                self.app.log(f"Recording is still starting - walk once it says RECORDING, then {self.rec_key()} "
                             "to finish.")
                return
            self._rec_stop = True
            return
        if self.running:
            self.app.log("Stop the macro before recording.")
            return
        if self.is_locked() or not self.active_route():
            old = self.active_route()
            new = self.create_route(self.free_route_name())
            if old:
                self.app.log(f"'{old}' is built-in - recording into a new route '{new}' instead.")
            if hasattr(self.app, "refresh_routes"):
                self.app.root.after(0, self.app.refresh_routes)
        self._rec_stop = False
        self._rec_live = False
        self._rerecord_from = from_ore if from_ore and from_ore > 1 else None
        self._rec_thread = threading.Thread(target=self._record_safe, daemon=True)
        self._rec_thread.start()

    def _record_safe(self):
        try:
            self._record()
        except Exception as e:
            self.app.log(f"!! Recording failed and was NOT saved ({type(e).__name__}: {e}). "
                         "Your previous recording of this route is kept.")
            if hasattr(self.app, "set_recording_ui"):
                self.app.root.after(0, lambda: self.app.set_recording_ui(False))
        finally:
            self._rec_live = False

    def _record(self):
        name = self.active_route()
        home_dir = self.route_dir(name)
        if not self.check_focus():
            self.app.log("Recording: click into Roblox now - starting in 3s...")
            time.sleep(3)
        if not self.game_view_clear():
            self.app.log("Recording: something is covering the Roblox window - move it away (waiting up to 15 s)...")
            if not self.wait_for_clear_view(alive=lambda: not self._rec_stop, timeout=15.0):
                self.app.log(f"!! Recording NOT started: Roblox stayed covered. Nothing was changed - press "
                             f"{self.rec_key()} again once Roblox is uncovered.")
                return
        old = self.load_route(name) or {}
        old_timers = [(s.get("mine_hold"), s.get("mine_wait")) for s in old.get("segments", [])]
        from_ore = getattr(self, "_rerecord_from", None)
        keep = list(old.get("segments", []))[:from_ore - 1] if from_ore else []
        if from_ore and len(keep) < from_ore - 1:
            self.app.log(f"!! The route has only {len(keep)} ore(s) - can't re-record from ore {from_ore}. "
                         f"Nothing was changed.")
            return
        offset = len(keep)
        folder = os.path.join(home_dir, "_recording")
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
        if not keep:
            self.save_snapshot(os.path.join(folder, "home.png"))
        self._rec_stop = False
        self._rec_live = True

        st = {"seg_start": time.perf_counter(), "last_mark": 0.0,
              "idle_since": time.perf_counter(), "idle_t": 0.0, "cp_taken": True}
        segments, events, checkpoints, held = [], [], [], set()
        lock = threading.Lock()
        if keep:
            self.app.log(f"● RE-RECORDING '{name}' from ore {offset + 1} ({'ore 1 is' if offset == 1 else f'ores 1-{offset} are'} kept). Walk on from "
                         f"here, TAP E at each ore, walk back to the start and press {self.rec_key()}.")
        elif self.ROUTE_TARGET == "ore":
            self.app.log(f"● RECORDING '{name}'. Walk the route, TAP E at each ore (as many as you like), then walk "
                         f"back to the start and press {self.rec_key()}. Everything after the last E = the walk back.")
        else:
            self.app.log(f"● RECORDING '{name}'. Walk to the {self.ROUTE_TARGET} (jumps, E... all recorded), "
                         f"then press {self.rec_key()} there.")
        if hasattr(self.app, "set_recording_ui"):
            self.app.root.after(0, lambda: self.app.set_recording_ui(True))

        def close_segment(now):
            for k in list(held):
                events.append([round(now - st["seg_start"], 3), k, "up"])
            dur = round(now - st["seg_start"], 3)
            cps = [c for c in checkpoints if dur - c["t"] > 1.0]
            seg = {"events": list(events), "duration": dur, "checkpoints": cps}
            events.clear(); checkpoints.clear()
            st["seg_start"] = now
            for k in held:
                events.append([0.0, k, "down"])
            return seg

        turns = self.turn_keys()

        def on_event(ev):
            raw = (ev.name or "").lower()
            name_ = position_name(ev)
            now = getattr(ev, "_t", None) or time.perf_counter()
            with lock:
                if raw in turns:
                    name_ = raw
                if name_ in turns:
                    if ev.event_type == "down" and not st.get("turn_held_" + name_):
                        st["turn_held_" + name_] = True
                        events.append([round(now - st["seg_start"], 3), f"turn:{turns[name_]}", "turn"])
                        self.app.log(f"   camera turn {turns[name_]:+d} degrees recorded")
                    elif ev.event_type == "up":
                        st["turn_held_" + name_] = False
                    return
                if name_ == "e" and not self.E_MARKS_TARGET:
                    pass
                elif name_ == "e" and ev.event_type == "up":
                    st["e_held"] = False
                    return
                elif name_ == "e" and ev.event_type == "down":
                    if st.get("e_held") or now - st["last_mark"] < 0.3:
                        return
                    st["e_held"] = True
                    st["last_mark"] = now
                    seg = close_segment(now)
                    idx = offset + len(segments) + 1
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
                        self.app.log(f"   {self.ROUTE_TARGET} reached ({seg['duration']:.1f}s walk) — press {self.rec_key()} to finish")
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

        seen = {}

        def hooked(ev):
            seen[position_name(ev)] = seen[(ev.name or "").lower()] = time.perf_counter()
            on_event(ev)
        hook = keyboard.hook(hooked)
        watch = sorted((set(self.RECORD_KEYS) - {"left shift"}) | {"e"} | set(turns))
        stop_backup = threading.Event()
        threading.Thread(target=self._record_key_backup, args=(watch, seen, on_event, stop_backup),
                         daemon=True).start()
        try:
            while not self._rec_stop:
                time.sleep(0.05)
                with lock:
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
                        seg_no, cp_no, t = offset + len(segments) + 1, len(checkpoints) + 1, st["idle_t"]
                if ready:
                    fname = f"cp_{seg_no}_{cp_no}.png"
                    if self.save_snapshot(os.path.join(folder, fname)):
                        with lock:
                            checkpoints.append({"t": t, "file": fname})
                        self.app.log(f"   checkpoint {seg_no}.{cp_no} saved")
        finally:
            keyboard.unhook(hook)
            stop_backup.set()
            if hasattr(self.app, "set_recording_ui"):
                self.app.root.after(0, lambda: self.app.set_recording_ui(False))
        with lock:
            ret = close_segment(time.perf_counter())
        segments = keep + segments
        route = {"ores": len(segments), "segments": segments, "return": ret}
        moved = sum(1 for sg in segments + [ret] for e in sg["events"] if e[2] in ("down", "turn"))
        if len(segments) == len(keep) and not moved:
            shutil.rmtree(folder, ignore_errors=True)
            self.app.log(f"Recording of '{name}' had no key presses - NOT saved, your previous recording is kept.")
            return
        time.sleep(0.5)
        def replaced(f):
            if not keep:
                return True
            import re
            m = re.match(r"(?:ore|cp)_(\d+)", f)
            return bool(m) and int(m.group(1)) > offset
        for f in os.listdir(home_dir):
            if f == "route.json":
                os.replace(os.path.join(home_dir, f), os.path.join(home_dir, "route.json.bak"))
            elif f.endswith(".png") and replaced(f):
                os.remove(os.path.join(home_dir, f))
        for f in os.listdir(folder):
            shutil.move(os.path.join(folder, f), os.path.join(home_dir, f))
        shutil.rmtree(folder, ignore_errors=True)
        self.save_route(route, name)
        if not self.load_route(name):
            raise IOError(f"route.json couldn't be read back from {home_dir}")
        n_cp = sum(len(sg["checkpoints"]) for sg in segments) + len(ret["checkpoints"])
        if keep:
            self.app.log(f"Route '{name}' saved: {'ore 1' if offset == 1 else f'ores 1-{offset}'} kept, re-recorded from ore {offset + 1} - "
                         f"{len(segments)} ores in all + the walk back ({ret['duration']:.1f}s).")
        elif self.ROUTE_TARGET == "ore":
            self.app.log(f"Route '{name}' saved: {len(segments)} ore{'s' if len(segments) != 1 else ''} "
                         f"+ the walk back to the start ({ret['duration']:.1f}s), {n_cp} checkpoints.")
        elif not self.E_MARKS_TARGET:
            n_keys = sum(1 for e in ret["events"] if e[2] == "down")
            n_turns = sum(1 for e in ret["events"] if e[2] == "turn")
            self.app.log(f"Route '{name}' saved: walk to the {self.ROUTE_TARGET} ({ret['duration']:.1f}s, "
                         f"{n_keys} key presses incl. jumps / E" + (f", {n_turns} camera turn(s)" if n_turns else "") + ").")
        elif segments:
            self.app.log(f"Route '{name}' saved: walk to the {self.ROUTE_TARGET} ({segments[0]['duration']:.1f}s).")
        else:
            self.app.log(f"Route '{name}' saved, but E was never tapped — the whole walk "
                         f"({ret['duration']:.1f}s) will be used to reach the {self.ROUTE_TARGET}.")
        if hasattr(self.app, "refresh_routes"):
            self.app.root.after(0, self.app.refresh_routes)

    def turn_keys(self):
        return {}

    def rotate_camera(self, degrees):
        pass

    def play_segment(self, seg, label="", alive=None):
        alive = alive or (lambda: self.running)
        events = sorted(seg["events"], key=lambda e: e[0])
        cps = (sorted(seg.get("checkpoints", []), key=lambda c: c["t"])
               if self.USE_ALIGNMENT and self.route_checks() else [])
        folder = self.route_dir()
        start = time.perf_counter()
        shift = 0.0
        down, ei, ci = set(), 0, 0
        pressed_at = {}
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
                    if kind == "turn":
                        deg = int(key.split(":", 1)[1])
                        threading.Thread(target=self.rotate_camera, args=(deg,), daemon=True).start()
                        continue
                    if kind == "down":
                        if key in down:
                            press_key(key, False)
                            time.sleep(0.02)
                        press_key(key, True); down.add(key)
                        pressed_at[key] = time.perf_counter()
                    else:
                        held_for = time.perf_counter() - pressed_at.get(key, 0)
                        if held_for < self.MIN_TAP:
                            time.sleep(self.MIN_TAP - held_for)
                            shift += self.MIN_TAP - held_for
                        press_key(key, False); down.discard(key)
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
                press_key(k, False)
        return alive()





    def _new_lap(self):
        self.lap = {"start": time.perf_counter(), "mined": 0, "targets": 0, "nudges": 0,
                    "misses": 0, "corrections": 0}




