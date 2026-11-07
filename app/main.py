import sys

PY_MIN, PY_MAX = (3, 11), (3, 14)


def _python_ok():
    v = sys.version_info[:2]
    if PY_MIN <= v <= PY_MAX and sys.maxsize > 2 ** 32:
        return True
    bits = 64 if sys.maxsize > 2 ** 32 else 32
    msg = (f"This Python is {sys.version.split()[0]} ({bits}-bit), but the macro needs the 64-bit Python "
           f"{PY_MIN[0]}.{PY_MIN[1]} - {PY_MAX[0]}.{PY_MAX[1]}. Install Python 3.12 (Windows installer, 64-bit) "
           f"from python.org - it can sit next to your current Python - then start the macro with "
           f"Windows_Launcher.bat.")
    print(msg)
    try:
        import tkinter
        from tkinter import messagebox
        r = tkinter.Tk(); r.withdraw()
        messagebox.showerror("VunVun's Macro - wrong Python", msg)
        r.destroy()
    except Exception:
        pass
    return False


if __name__ == "__main__" and not _python_ok():
    sys.exit(1)

import customtkinter as ctk
import tkinter as tk
import time
from gui import SpatialGUI, MacroSelector
import sys
import ctypes
import os

VERSION = "6.5"

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
        sel = getattr(self, "selector", None)
        keep = sel.frame if sel is not None and sel.frame.winfo_exists() else None
        old = []
        for widget in self.root.winfo_children():
            if widget is keep:
                widget.pack_forget()
            elif getattr(widget, "_buried", False):
                continue
            elif isinstance(widget, tk.Toplevel):
                widget.destroy()
            else:
                for forget in (widget.pack_forget, widget.grid_forget, widget.place_forget):
                    try:
                        forget()
                    except Exception:
                        pass
                widget._buried = True
                old.append(widget)
        self._bury(old)
        return keep

    def _bury(self, widgets):
        stack = list(widgets)

        def chunk():
            t0 = time.perf_counter()
            while stack and time.perf_counter() - t0 < 0.01:
                w = stack[-1]
                try:
                    kids = w.winfo_children()
                except Exception:
                    stack.pop()
                    continue
                leaf = isinstance(w, ctk.windows.widgets.core_widget_classes.CTkBaseClass) and not isinstance(
                    w, (ctk.CTkFrame, ctk.CTkScrollableFrame))
                if kids and not leaf and not getattr(w, "_buried_kids", False):
                    w._buried_kids = True
                    for k in kids:
                        if isinstance(k, tk.Canvas):
                            try:
                                k.configure(yscrollcommand="", xscrollcommand="")
                            except Exception:
                                pass
                    stack.extend(kids)
                    continue
                stack.pop()
                try:
                    w.destroy()
                except Exception:
                    pass
            if stack:
                self.root.after(10, chunk)
        if stack:
            self.root.after(30, chunk)

    def show_selector(self):
        if self.clear_screen() is not None:
            self.selector.show()
        else:
            self.selector = MacroSelector(self.root, self.launch_macro, VERSION)

    def launch_macro(self, title, logic_class, tabs=None, tutorial_url="#", gui_class=None, spatial_class=None):
        self.clear_screen()
        if gui_class:
            self.app = gui_class(self.root, title=title, on_back=self.show_selector)
            return
        cls = spatial_class or SpatialGUI
        self.app = cls(self.root, title=title, logic_class=logic_class, on_back=self.show_selector, tabs=tabs,
                       tutorial_url=tutorial_url)

def main():
    import applog
    applog.start(VERSION)
    import links
    links.refresh_async()

    def warm_keyboard():
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
    from ui_style import faster_resizing
    faster_resizing(root)

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
    from utils import SpatialUtils
    root.after(1500, SpatialUtils.preload_ocr)
    root.mainloop()

if __name__ == "__main__":
    main()