import time
import keyboard
from logic_base import BaseLogic

class TundraLogic(BaseLogic):
    def __init__(self, app):
        super().__init__(app)

    def _spd(self):
        """Return the current speed multiplier (divides travel sleep durations)."""
        return max(0.1, float(self.app.settings.get("speed_multiplier", 1.0)))

    def _t(self, seconds):
        """Scale a travel sleep duration by the speed multiplier."""
        return seconds / self._spd()

    def test_detection(self):
        self.app.log("Testing screen for white color/text...")
        tolerance = self.app.settings.get("color_tolerance", 25)
        white_color = (255, 255, 255)

        region = self.app.settings.get("regions", {}).get("tundra_detection_region")
        if region and not all(v == 0 for v in region):
            test_region = region
            self.app.log(f"Using Tundra detection region for white test: {test_region}")
        else:
            screen_w, screen_h = self.utils.get_screen_size()
            test_region = [0, 0, screen_w, screen_h]
            self.app.log(f"Tundra detection region not set; using full screen: {test_region}")

        found = self.utils.pixel_search_region(test_region, white_color, tolerance=tolerance)
        if found:
            first_pos = found[0]
            self.utils.mouse_move(first_pos[0], first_pos[1])
            self.app.log(f"Test: SUCCESS! Found white target at {first_pos} with tolerance {tolerance}.")
        else:
            self.app.log(f"Test: FAILED. No white pixels found with tolerance {tolerance}. Try increasing the variance slider.")

    def test_movement(self):
        if not self.check_focus():
            self.app.log("Please focus Roblox before testing!")
            return

        self.app.log(f"--- Starting Movement Test (speed: {self._spd():.2f}x) ---")

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

            steps = [
                ('d', self._t(0.3)), None,
                ('d', self._t(4.0)), None,
                ('s', self._t(0.25)), ('d', self._t(0.55)), None,
                ('w', self._t(1.5)), ('d', self._t(0.3)), None,
                ('d', self._t(12)), None,
                ('d', self._t(1)), ('w', self._t(0.4)), ('d', self._t(0.1)), None,
                ('a', self._t(0.2)), ('w', self._t(1)), None,
                ('a', self._t(1.25)), None,
                ('a', self._t(0.5)), ('s', self._t(2.5)), ('a', self._t(1.55)), ('s', self._t(3.6)), None,
                ('a', self._t(0.70)), ('s', self._t(2.4)), ('d', self._t(0.35)), None,
                ('a', self._t(1.35)), ('s', self._t(2)), None,
                ('w', self._t(5)), ('a', self._t(7)), ('w', self._t(3)), ('a', self._t(7)),
            ]

            for step in steps:
                if not self.test_running: return
                if step is None:
                    if not self._sleep(1.75): return
                else:
                    if not move(step[0], step[1]): return

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

                self.app.log("Travelling pathway (Forward)")
                keyboard.press('d')
                time.sleep(self._t(0.31))
                keyboard.release('d')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(self._t(0.05))
                keyboard.release('s')
                time.sleep(0.5)

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

                self.app.log("Action: Mining ore (1/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                self.app.log("Travelling pathway (Forward)")
                keyboard.press('d')
                time.sleep(self._t(4.0))
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (2/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                self.app.log("Travelling pathway (S + D Adjustment)")
                keyboard.press('s')
                time.sleep(self._t(0.25))
                keyboard.release('s')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(self._t(0.55))
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (3/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('w')
                time.sleep(self._t(1.5))
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(self._t(0.3))
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (4/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('d')
                time.sleep(self._t(12))
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (5/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('d')
                time.sleep(self._t(1))
                keyboard.release('d')
                time.sleep(0.5)

                keyboard.press('w')
                time.sleep(self._t(0.4))
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(self._t(0.1))
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (6/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('a')
                time.sleep(self._t(0.2))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('w')
                time.sleep(self._t(1))
                keyboard.release('w')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (7/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('a')
                time.sleep(self._t(1.25))
                keyboard.release('a')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (8/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('a')
                time.sleep(self._t(0.5))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(self._t(2.5))
                keyboard.release('s')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(self._t(1.55))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(self._t(3.6))
                keyboard.release('s')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (9/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('a')
                time.sleep(self._t(0.70))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(self._t(2.4))
                keyboard.release('s')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(self._t(0.35))
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (10/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

                keyboard.press('a')
                time.sleep(self._t(1.35))
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(self._t(2))
                keyboard.release('s')
                time.sleep(0.5)

                if not self.running: break

                self.app.log("Action: Mining ore (11/11)")
                keyboard.press('e')
                time.sleep(3.0)
                keyboard.release('e')
                time.sleep(1.75)

                if not self.running: break

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