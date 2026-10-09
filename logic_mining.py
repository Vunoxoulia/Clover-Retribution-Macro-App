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
    spot you paused while recording, confirms the Interact prompt, then mines.
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


    def _mine_here(self, ore_idx, seg):
        """Line up on the ore snapshot, confirm the Interact prompt, mine."""
        self.lap["targets"] += 1
        self._wait_still()
        snap = os.path.join(self.route_dir(), f"ore_{ore_idx}.png")
        if os.path.exists(snap):
            if self.align_to(cv2.imread(snap), f"ore {ore_idx}", max_tries=8) == "lost":
                self.app.log(f"   ore {ore_idx}: snapshot not recognised (off by >150px?)")
        if not self.confirm_arrival(ore_idx):
            self.lap["misses"] += 1
            self.app.log(f"   x Ore {ore_idx}: not found, skipping")
            return False
        self.mine(ore_idx, seg)
        self.lap["mined"] += 1
        return True


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
        if self.has_home() and not self.align_home():
            self.running = False

    # ----- Lap statistics -----

    def _end_lap(self):
        self.lap_no += 1
        L = self.lap
        self.app.log(f"=== Lap {self.lap_no} [{self.active_route()}]: {L['mined']}/{L['targets']} mined, "
                     f"{L['misses']} misses, {L['nudges']} nudges, {L['corrections']} snapshot fixes, "
                     f"{time.perf_counter() - L['start']:.1f}s ===")


    def test_detection(self):
        hit = self.prompt_near_player()
        self.app.log(f"Interact prompt near character: {'FOUND at ' + str(hit) if hit else 'not found'}")


    def test_home(self):
        if not self.has_home():
            self.app.log("No start spot saved for this route yet (it's saved when you record).")
            return
        score, dx, dy = self.measure_offset(cv2.imread(self._home_path()), self._screen())
        ok = score >= self.SNAP_MIN_SCORE
        self.app.log(f"Start spot {'recognised' if ok else 'NOT recognised'}: match {score:.2f}, off by ({dx}, {dy}) px")
        if ok and self.check_focus():
            self.app.log("Walking back onto the start spot...")
            self.align_to(cv2.imread(self._home_path()), "home", alive=lambda: self.test_running)


    def test_movement(self):
        """Test Path: one lap of the selected route without mining."""
        route = self.load_route()
        if not route:
            self.app.log("No recorded route yet. Select a route and press Ctrl+P to record.")
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
                self.app.log("Finish the recording (Ctrl+P) before starting.")
                return
            route = self.load_route()
            if not route:
                self.app.log("No recorded route yet. Select a route and press Ctrl+P to record.")
                return
            if not self.wait_for_roblox_focus():
                return
            time.sleep(0.5)
            self._probe_region = None
            self.lap_no = 0
            self.app.log(f"Starting route '{self.active_route()}' ({route['ores']} ores)...")

            # ',' locks the camera top-down and facing the same way
            for i in (1, 2):
                self.app.log(f"Initialization: Pressing ',' ({i}/2)")
                self.utils.send_key(',')
                time.sleep(1.5)
                if not self.running: return

            if not self.align_home(): return
            self.handle_ok_popup()
            while self.running:
                if not self.check_focus() and not self.wait_for_roblox_focus():
                    break
                self.run_lap(route)
                if self.running:
                    WATCHER.checkpoint("Mining")   # one full lap done: safe moment to check chat
        except Exception as e:
            self.app.log(f"Mining Logic Error: {e}")

