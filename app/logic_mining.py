import os
import json
import shutil
import time
import keyboard
from utils import game_key
import cv2
from route_nav import RouteNav, DEFAULT_MINE_HOLD, DEFAULT_MINE_WAIT


class MiningLogic(RouteNav):
    """Mining by recorded route.

    You walk a route once (Ctrl+P to start/stop recording), tapping E at each ore.
    Playback replays your keys, lines up on a snapshot at every ore and at every
    spot you paused while recording, then mines.
    Routes are stored per name in routes/<name>/, so one macro covers any area."""

    def __init__(self, app):
        super().__init__(app)
        self._migrate_old_tundra_route()

    def _migrate_old_tundra_route(self):
        """One-time: move the pre-routes Tundra recording into routes/Tundra."""
        from settings import get_base_path
        base = get_base_path()
        old = os.path.join(base, "tundra_route.json")
        if not os.path.exists(old) or self.list_routes():
            return
        try:
            with open(old, encoding="utf-8") as f:
                route = json.load(f)
            dest = os.path.join(self._routes_dir(), "Tundra")
            os.makedirs(dest, exist_ok=True)
            timers = self.app.settings.get("node_timers", {})
            for i, seg in enumerate(route["segments"], start=1):
                cfg = timers.get(str(i), {})
                seg.setdefault("mine_hold", float(cfg.get("mine_hold", DEFAULT_MINE_HOLD)))
                seg.setdefault("mine_wait", float(cfg.get("mine_wait", DEFAULT_MINE_WAIT)))
                seg.setdefault("checkpoints", [])
            route["return"].setdefault("checkpoints", [])
            with open(os.path.join(dest, "route.json"), "w", encoding="utf-8") as f:
                json.dump(route, f, indent=1)
            if os.path.exists(os.path.join(base, "tundra_home.png")):
                shutil.copy(os.path.join(base, "tundra_home.png"), os.path.join(dest, "home.png"))
            snaps = os.path.join(base, "tundra_snapshots")
            if os.path.isdir(snaps):
                for f in os.listdir(snaps):
                    if f.startswith("rec_ore_"):
                        shutil.copy(os.path.join(snaps, f), os.path.join(dest, f[len("rec_"):]))
            self.set_active_route("Tundra")
        except Exception as e:
            print(f"Route migration failed: {e}")


    def mine(self, ore_idx, seg):
        hold = float(seg.get("mine_hold", DEFAULT_MINE_HOLD))
        wait = float(seg.get("mine_wait", DEFAULT_MINE_WAIT))
        if getattr(self, "_dry_run", False):
            self.app.log(f"   (Test Path: would mine ore {ore_idx} here)")
            time.sleep(wait)
            return
        self.app.log(f"Mining ore {ore_idx} [{hold:.2f}s, then wait {wait:.2f}s]")
        keyboard.press(game_key('e'))
        time.sleep(hold)
        keyboard.release(game_key('e'))
        time.sleep(wait)


    def route_checks(self):
        """Mining just follows the recorded path and presses E (no snapshot line-ups)."""
        return False

    def _mine_here(self, ore_idx, seg):
        self.lap["targets"] += 1
        self._wait_still()
        self.mine(ore_idx, seg)
        self.lap["mined"] += 1
        return True

    # ----- Wait for Interact (start spot) -----
    def wait_interact_on(self):
        return bool(self.app.settings.get("mining_wait_interact", False))

    def interact_visible(self):
        """The 'E Interact' prompt is on screen: read in your box (Set area), else the lower middle of the window."""
        area = self.app.settings.get("regions", {}).get("mining_interact") or [0, 0, 0, 0]
        if not (area[2] > area[0] and area[3] > area[1]):
            l, t, r, b = self.get_roblox_window_region()
            W, H = r - l, b - t
            area = [int(l + W * 0.3), int(t + H * 0.5), int(l + W * 0.7), int(t + H * 0.85)]
        img = self.utils.capture_screen_bgr(area)
        # The prompt's text is white: no white pixels = no prompt, so the (heavy) text reader isn't run at all
        if img is None or not img.size or int((img.min(axis=2) > 200).sum()) < 80:
            return False
        from utils import SpatialUtils
        reader = SpatialUtils.load_ocr()
        try:
            res = reader(img)[0] if reader else None
        except Exception:
            res = None
        return any("interact" in (r[1] or "").lower() for r in (res or []))

    def wait_for_interact(self):
        """At the start spot: wait until the Interact prompt shows (the ore has respawned). Stop = False."""
        if self.interact_visible():
            return True
        self.app.log("Waiting for the Interact prompt at the start...")
        since, note = time.time(), 60
        while self.running:
            time.sleep(0.7)
            if self.interact_visible():
                self.app.log(f"Interact seen after {time.time() - since:.0f}s - starting the route.")
                return True
            if time.time() - since >= note:
                self.app.log(f"   still waiting for Interact ({time.time() - since:.0f}s)")
                note += 60
            self.handle_ok_popup()
        return False


    def run_lap(self, route):
        self._new_lap()
        for i, seg in enumerate(route["segments"], start=1):
            if not self.running: return
            self.app.log(f"[{self.active_route()}] To ore {i}/{route['ores']}")
            if not self.play_segment(seg, label=str(i)): return
            self._mine_here(i, seg)
        self.app.log(f"[{self.active_route()}] Returning to start")
        self.play_segment(route["return"], label="home")
        self._end_lap()
        if self.has_home():
            self.align_home()                            # small line-up on the start spot, never stops the lap

    # ----- Lap statistics -----

    def _end_lap(self):
        self.lap_no += 1
        L = self.lap
        self.app.log(f"=== Lap {self.lap_no} [{self.active_route()}]: {L['mined']}/{L['targets']} mined, "
                     f"{L['misses']} misses, {L['nudges']} nudges, {L['corrections']} snapshot fixes, "
                     f"{time.perf_counter() - L['start']:.1f}s ===")


    def test_movement(self):
        """Test Path: one lap of the selected route without mining."""
        route = self.load_route()
        if not route:
            self.app.log(f"No recorded route yet. Select a route and press {self.rec_key()} to record.")
            return
        if not self.wait_focus_for_test():
            return
        self.app.log(f"--- Test Path [{self.active_route()}]: one lap, no mining ---")
        self._dry_run = True
        self.running = True   # the lap code runs while this is set; Stop clears it
        self._probe_region = None
        try:
            if self.align_home():
                self.run_lap(route)
                self.app.log("--- Test Path complete ---")
        except Exception as e:
            self.app.log(f"Test Error: {e}")
        finally:
            self._dry_run = False
            self.running = False


    def main_loop(self):
        from logic_events import WATCHER
        WATCHER.hold("Mining")              # event checks only between laps (see checkpoint below)
        try:
            self._mining_loop()
        finally:
            WATCHER.release("Mining")

    def _mining_loop(self):
        from logic_events import WATCHER
        try:
            if self.is_recording():
                self.app.log(f"Finish the recording ({self.rec_key()}) before starting.")
                return
            route = self.load_route()
            if not route:
                self.app.log(f"No recorded route yet. Select a route and press {self.rec_key()} to record.")
                return
            if not self.wait_for_roblox_focus():
                return
            time.sleep(0.5)
            self._probe_region = None
            self.lap_no = 0
            self.app.log(f"Starting route '{self.active_route()}' ({route['ores']} ores)...")

            # ',' locks the camera top-down and facing the same way
            for i in ((1, 2) if self.app.settings.get("mining_press_comma", True) else ()):
                self.app.log(f"Initialization: Pressing ',' ({i}/2)")
                self.utils.send_key(',')
                time.sleep(1.5)
                if not self.running: return

            if not self.align_home(): return
            self.handle_ok_popup()
            while self.running:
                if not self.check_focus() and not self.wait_for_roblox_focus():
                    break
                route = self.load_route() or route       # edits made while running apply from the next lap
                if self.wait_interact_on() and not self.wait_for_interact():
                    break
                self.run_lap(route)
                if self.running:
                    WATCHER.checkpoint("Mining")   # one full lap done: safe moment to check chat
        except Exception as e:
            self.app.log(f"Mining Logic Error: {e}")

