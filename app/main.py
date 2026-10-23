import customtkinter as ctk
from gui import SpatialGUI, MacroSelector
import sys
import ctypes
import os

VERSION = "6.3.7"

def get_resource_path(relative_path):
    
    try:
        
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

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

    def launch_macro(self, title, logic_class, tabs=None, tutorial_url="#", gui_class=None):
        self.clear_screen()
        if gui_class:
            self.app = gui_class(self.root, title=title, on_back=self.show_selector)
            return
        self.app =SpatialGUI(self.root, title=title, logic_class=logic_class, on_back=self.show_selector, tabs=tabs, tutorial_url=tutorial_url)

def main():
    import links
    links.refresh_async()             # newest links.txt from GitHub (videos, Discord, donate)

    def warm_keyboard():
        # the key hook's first start builds Windows' key-name tables (~1 s); do it now, not when a macro opens
        try:
            import keyboard
            keyboard._listener.start_if_necessary()
        except Exception:
            pass
    import threading
    threading.Thread(target=warm_keyboard, daemon=True).start()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = ctk.CTk()
    
    from updater import SpatialUpdater
    updater = SpatialUpdater(VERSION, "Vunoxoulia", "Clover-Retribution-Macro-App")
    icon_path = updater.download_icon_from_github()
    
    if not icon_path:
        icon_path = get_resource_path("Vunoxoulia.ico")
        
    if icon_path and os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not load icon: {e}")

    app = SpatialApp(root)
    # load the text reader in the background once the menu is up (loading it earlier held the menu up ~1 s),
    # so Start doesn't freeze later
    from utils import SpatialUtils
    root.after(300, SpatialUtils.preload_ocr)
    root.mainloop()

if __name__ == "__main__":
    main()