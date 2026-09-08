import time
import keyboard
from logic_base import BaseLogic

# Canonical WASD key + hold-duration (seconds) sequence used to walk from the
# previous spot to each node. These are the values shown/edited in the
# Settings tab and are exactly what gets pressed in-game - no multiplier.
DEFAULT_NODE_STEPS = {
    "1": [("d", 0.23), ("s", 0.0)],
    "2": [("d", 4.0)],
    "3": [("s", 0.25), ("d", 0.55)],
    "4": [("w", 1.5), ("d", 0.3)],
    "5": [("d", 12.0)],
    "6": [("d", 1.0), ("w", 0.4), ("d", 0.1)],
    "7": [("a", 0.2), ("w", 1.0)],
    "8": [("a", 1.25)],
    "9": [("a", 0.5), ("s", 2.5), ("a", 1.55), ("s", 3.6)],
    "10": [("a", 0.70), ("s", 2.4), ("d", 0.35)],
    "11": [("a", 1.35), ("s", 2.0)],
}

class TundraLogic(BaseLogic):
    def __init__(self, app):
        super().__init__(app)

    def _sprint_delay(self):
        return max(0.0, float(self.app.settings.get("sprinting_delay", 0.25)))

    def _t(self, seconds):
        """Fixed (non-per-node) hold duration plus sprint compensation."""
        return seconds + self._sprint_delay()

    def get_node_timer(self, node_idx):
        """Fetch mining hold/wait timers (raw seconds) for node 1..11."""
        node_timers = self.app.settings.get("node_timers", {})
        config = node_timers.get(str(node_idx), {})
        return {
            "mine_hold": float(config.get("mine_hold", 3.0)),
            "mine_wait": float(config.get("mine_wait", 1.75)),
        }

    def get_node_steps(self, node_idx):
        """Fetch the exact key/duration sequence used to walk to this node, in raw seconds."""
        node_timers = self.app.settings.get("node_timers", {})
        config = node_timers.get(str(node_idx), {})
        steps = config.get("steps")
        if not steps:
            steps = [{"key": k, "seconds": s} for k, s in DEFAULT_NODE_STEPS[str(node_idx)]]
        return [(s["key"], max(0.0, float(s["seconds"]))) for s in steps]

    def mine_node(self, node_idx):
        """Perform mining action for specified node index using per-node hold & wait timers."""
        timers = self.get_node_timer(node_idx)
        self.app.log(f"Action: Mining ore ({node_idx}/11) [Mining: {timers['mine_hold']:.2f}s | Wait: {timers['mine_wait']:.2f}s]")
        keyboard.press('e')
        time.sleep(timers['mine_hold'])
        keyboard.release('e')
        time.sleep(timers['mine_wait'])

    def travel_to_node(self, node_idx, label=None):
        """Walk the exact configured WASD key sequence for a node."""
        self.app.log(label or f"Travelling pathway to Node {node_idx}")
        for key, seconds in self.get_node_steps(node_idx):
            if not self.running:
                return
            keyboard.press(key)
            time.sleep(seconds + self._sprint_delay())
            keyboard.release(key)
            time.sleep(0.5)

    def test_detection(self):
        self.app.log("Testing screen for white 'Interact' color/text...")
        tolerance = self.app.settings.get("color_tolerance", 25)
        white_color = (255, 255, 255)

        region = self.app.settings.get("regions", {}).get("tundra_detection_region")
        if region and not all(v == 0 for v in region):
            test_region = region
            self.app.log(f"Using calibrated Tundra detection region: {test_region}")
        else:
            screen_w, screen_h = self.utils.get_screen_size()
            test_region = [0, 0, screen_w, screen_h]
            self.app.log("Tundra Detection Region is set to [0,0,0,0]. Scanning full screen — please set Detection Region in Settings tab.")

        found = self.utils.pixel_search_region(test_region, white_color, tolerance=tolerance)
        if found:
            first_pos = found[0]
            self.utils.mouse_move(first_pos[0], first_pos[1])
            self.app.log(f"White Text Test: SUCCESS! Found 'Interact' white text at {first_pos}.")
        else:
            self.app.log("White Text Test: FAILED! 'Interact' white text was not detected. Please set your Tundra Detection Region in Settings tab or increase Tolerance.")

    def test_movement(self):
        if not self.check_focus():
            self.app.log("Please focus Roblox before testing!")
            return

        self.app.log("--- Starting Movement Test (using per-node timers) ---")

        def move(key, duration):
            if not self.test_running:
                return False
            keyboard.press(key)
            ok = self._sleep(duration)
            keyboard.release(key)
            if not ok:
                return False
            return self._sleep(0.5)

        try:
            self.app.log("Adjusting to optimal position...")
            keyboard.press('a')
            if not self._sleep(self._t(0.15)):
                keyboard.release('a'); return
            keyboard.press('w')
            if not self._sleep(self._t(1)):
                keyboard.release('w'); keyboard.release('a'); return
            keyboard.release('w')
            if not self._sleep(self._t(0.15)):
                keyboard.release('a'); return
            keyboard.release('a')
            if not self._sleep(0.5): return

            for node_idx in range(1, 12):
                if not self.test_running: return
                for key, seconds in self.get_node_steps(node_idx):
                    if not move(key, seconds + self._sprint_delay()): return
                # Simulate node mining wait
                wait_t = self.get_node_timer(node_idx)["mine_wait"]
                if not self._sleep(wait_t): return

            # Return trip steps
            return_steps = [
                ('w', self._t(5)), ('a', self._t(7)), ('w', self._t(3)), ('a', self._t(7))
            ]
            for key, dur in return_steps:
                if not move(key, dur): return

            keyboard.press('a')
            if not self._sleep(self._t(0.15)):
                keyboard.release('a'); return
            keyboard.press('w')
            if not self._sleep(self._t(1)):
                keyboard.release('w'); keyboard.release('a'); return
            keyboard.release('w')
            if not self._sleep(self._t(0.15)):
                keyboard.release('a'); return
            keyboard.release('a')

            self.app.log("--- Movement Test Complete ---")
        except Exception as e:
            self.app.log(f"Test Error: {e}")

    def main_loop(self):
        try:
            if not self.wait_for_roblox_focus():
                return

            time.sleep(0.5)
            self.app.log("Starting Tundra sequence...")

            self.app.log("Initialization: Pressing ',' (1/2)")
            self.utils.send_key(',')
            time.sleep(1.5)

            if not self.running: return

            self.app.log("Initialization: Pressing ',' (2/2)")
            self.utils.send_key(',')
            time.sleep(1.5)

            self.app.log("Adjusting to optimal position...")
            keyboard.press('a')
            time.sleep(self._t(0.15))
            keyboard.press('w')
            time.sleep(self._t(1))
            keyboard.release('w')
            time.sleep(self._t(0.15))
            keyboard.release('a')
            time.sleep(0.5)

            self.handle_ok_popup()

            if not self.running: return

            self.app.log("Entering Tundra main loop...")
            while self.running:
                if not self.check_focus():
                    if not self.wait_for_roblox_focus():
                        break

                self.travel_to_node(1, label="Travelling pathway (Forward to Node 1)")
                if not self.running: break

                self.app.log("Loop: Waiting for white text to appear...")
                tolerance = self.app.settings.get("color_tolerance", 25)
                white_color = (255, 255, 255)
                detection_region = self.app.settings.get("regions", {}).get("tundra_detection_region")

                if not detection_region or all(v == 0 for v in detection_region):
                    screen_w, screen_h = self.utils.get_screen_size()
                    detection_region = [0, 0, screen_w, screen_h]

                while self.running:
                    if not self.check_focus():
                        if not self.wait_for_roblox_focus():
                            break
                    found = self.utils.pixel_search_region(detection_region, white_color, tolerance=tolerance)
                    if found:
                        self.app.log("-> White text detected! Breaking scan loop to mine.")
                        break
                    time.sleep(0.5)

                if not self.running: break

                self.mine_node(1)

                for node_idx in range(2, 12):
                    if not self.running: break
                    self.travel_to_node(node_idx)
                    if not self.running: break
                    self.mine_node(node_idx)

                if not self.running: break

                # Return pathway
                self.app.log("Returning to starting position...")
                keyboard.press('w')
                time.sleep(self._t(5))
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(self._t(7))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('w')
                time.sleep(self._t(3))
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(self._t(7))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(self._t(0.15))
                keyboard.press('w')
                time.sleep(self._t(1))
                keyboard.release('w')
                time.sleep(self._t(0.15))
                keyboard.release('a')
                time.sleep(0.5)

        except Exception as e:
            self.app.log(f"Tundra Logic Error: {e}")
