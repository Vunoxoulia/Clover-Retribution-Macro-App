import time
import keyboard
from logic_base import BaseLogic

class TundraLogic(BaseLogic):
    def __init__(self, app):
        super().__init__(app)

    def test_detection(self):
        self.app.log("Testing FULL SCREEN OCR for 'Interact'...")
        results = self.utils.get_text_from_region(None) 
        found = False
        for bbox, text, conf in results:
            if "interact" in text.lower():
                self.app.log(f"Test: SUCCESS! Found 'Interact' (Conf: {conf:.2f})")
                found = True
                break
        
        if not found:
            detected = ", ".join([res[1] for res in results])
            self.app.log(f"Test: FAILED. Saw: [{detected}]")

    def test_movement(self):
        
        if not self.check_focus():
            self.app.log("Please focus Roblox before testing!")
            return

        self.app.log("--- Starting Movement Test ---")
        try:
            self.app.log("Adjusting to optimal position...")
            keyboard.press('a')
            time.sleep(0.15)
            keyboard.press('w')
            time.sleep(1)
            keyboard.release('w')
            time.sleep(0.15)
            keyboard.release('a')
            time.sleep(0.5)

            self.handle_ok_popup()
        
            self.app.log("Travelling pathway (Forward)")
            keyboard.press('d')
            time.sleep(0.3)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (1/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            self.app.log("Travelling pathway (Forward)")
            keyboard.press('d')
            time.sleep(4.0)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (2/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            self.app.log("Travelling pathway (S + D Adjustment)")
            keyboard.press('s')
            time.sleep(0.25)
            keyboard.release('s')
            time.sleep(0.5)

            keyboard.press('d')
            time.sleep(0.55)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (3/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)
            
            keyboard.press('w')
            time.sleep(1.5)
            keyboard.release('w')
            time.sleep(0.5)

            keyboard.press('d')
            time.sleep(0.3)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (4/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('d')
            time.sleep(12)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (5/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('d')
            time.sleep(1)
            keyboard.release('d')
            time.sleep(0.5)

            keyboard.press('w')
            time.sleep(0.4)
            keyboard.release('w')
            time.sleep(0.5)

            keyboard.press('d')
            time.sleep(0.1)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (6/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('a')
            time.sleep(0.2)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('w')
            time.sleep(1)
            keyboard.release('w')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (7/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('a')
            time.sleep(1.25)
            keyboard.release('a')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (8/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('a')
            time.sleep(0.5)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('s')
            time.sleep(2.5)
            keyboard.release('s')
            time.sleep(0.5)

            keyboard.press('a')
            time.sleep(1.55)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('s')
            time.sleep(3.6)
            keyboard.release('s')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (9/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('a')
            time.sleep(0.70)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('s')
            time.sleep(2.4)
            keyboard.release('s')
            time.sleep(0.5)

            keyboard.press('d')
            time.sleep(0.35)
            keyboard.release('d')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (10/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            keyboard.press('a')
            time.sleep(1.35)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('s')
            time.sleep(2)
            keyboard.release('s')
            time.sleep(0.5)

            self.app.log("Action: Mining ore (11/11)")
            keyboard.press('e')
            time.sleep(3.0)
            keyboard.release('e')
            time.sleep(1.75)

            
            keyboard.press('w')
            time.sleep(5)
            keyboard.release('w')
            time.sleep(0.5)

            keyboard.press('a')
            time.sleep(7)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('w')
            time.sleep(3)
            keyboard.release('w')
            time.sleep(0.5)

            keyboard.press('a')
            time.sleep(7)
            keyboard.release('a')
            time.sleep(0.5)

            keyboard.press('a')
            time.sleep(0.15)
            keyboard.press('w')
            time.sleep(1)
            keyboard.release('w')
            time.sleep(0.15)
            keyboard.release('a')
            time.sleep(0.5)
            
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
            time.sleep(0.15)
            keyboard.press('w')
            time.sleep(1)
            keyboard.release('w')
            time.sleep(0.15)
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
                time.sleep(0.3)
                keyboard.release('d')
                time.sleep(0.5)

                if not self.running: break

                
                self.app.log("Loop: Waiting for 'Interact' to appear...")
                while self.running:
                    if not self.check_focus():
                        if not self.wait_for_roblox_focus(): 
                            break

                    results = self.utils.get_text_from_region(None)
                    interact_found = any("interact" in item[1].lower() for item in results)

                    if interact_found:
                        self.app.log("-> 'Interact' detected! Breaking scan loop to mine.")
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
                time.sleep(4.0)
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
                time.sleep(0.25)
                keyboard.release('s')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(0.55)
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
                time.sleep(1.5)
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(0.3)
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
                time.sleep(12)
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
                time.sleep(1)
                keyboard.release('d')
                time.sleep(0.5)

                keyboard.press('w')
                time.sleep(0.4)
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(0.1)
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
                time.sleep(0.2)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('w')
                time.sleep(1)
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
                time.sleep(1.25)
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
                time.sleep(0.5)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(2.5)
                keyboard.release('s')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(1.55)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(3.6)
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
                time.sleep(0.70)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(2.4)
                keyboard.release('s')
                time.sleep(0.5)

                keyboard.press('d')
                time.sleep(0.35)
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
                time.sleep(1.35)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('s')
                time.sleep(2)
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
                time.sleep(5)
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(7)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('w')
                time.sleep(3)
                keyboard.release('w')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(7)
                keyboard.release('a')
                time.sleep(0.5)

                keyboard.press('a')
                time.sleep(0.15)
                keyboard.press('w')
                time.sleep(1)
                keyboard.release('w')
                time.sleep(0.15)
                keyboard.release('a')
                time.sleep(0.5)
                
                
        except Exception as e:
            self.app.log(f"Tundra Logic Error: {e}")
