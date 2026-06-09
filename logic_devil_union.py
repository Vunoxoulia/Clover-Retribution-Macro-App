import time
import keyboard
from logic_base import BaseLogic

class DevilUnionLogic(BaseLogic):
    def __init__(self, app):
        super().__init__(app)

    def test_detection(self):
        self.app.log("Test: Devil Union OCR Detection not yet implemented.")

    def main_loop(self):
        self.app.log("Devil Union Macro Started (Coming Soon)")
        while self.running:
            if not self.wait_for_roblox_focus():
                break
            
            
            self.app.log("Devil Union Training Cycle...")
            time.sleep(2.0)
            
            if not self.running:
                break
        
        self.app.log("Devil Union Macro Stopped")
