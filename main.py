import customtkinter as ctk
from gui import SpatialGUI, MacroSelector
import sys
import ctypes
import os

VERSION = "5.6"

def get_resource_path(relative_path):
    
    try:
        
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class SpatialApp:
    def __init__(self, root):
        self.root = root
        self.show_selector()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_selector(self):
        self.clear_screen()
        self.selector = MacroSelector(self.root, self.launch_macro, VERSION)

    def launch_macro(self, title, logic_class, tabs=None, tutorial_url="#"):
        self.clear_screen()
        self.app = SpatialGUI(self.root, title=title, logic_class=logic_class, on_back=self.show_selector, tabs=tabs, tutorial_url=tutorial_url)

def main():
    if sys.platform.startswith('win'):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

    root = ctk.CTk()
    
    from updater import SpatialUpdater
    updater = SpatialUpdater(VERSION, "Vunoxoulia", "Clover-Retribution-Macro-App")
    icon_path = updater.download_icon_from_github()
    
    if not icon_path:
        icon_path = get_resource_path("Vunoxoulia.ico")
        
    if icon_path and os.path.exists(icon_path):
        try:
            if sys.platform.startswith('win'):
                root.iconbitmap(icon_path)
            else:
                from PIL import Image, ImageTk
                img = Image.open(icon_path)
                photo = ImageTk.PhotoImage(img)
                root.wm_iconphoto(True, photo)
        except Exception as e:
            print(f"Could not load icon: {e}")

    app = SpatialApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()