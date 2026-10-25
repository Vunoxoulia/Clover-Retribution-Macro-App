import customtkinter as ctk
import tkinter as tk
from settings import SpatialSettings
from overlay import Overlay, PointSelector, ColorPicker, PersistentOverlay
from updater import SpatialUpdater
from logic_library import LibraryLogic
from logic_mining import MiningLogic
from logic_fishing import FishingLogic
from logic_umbral_abyss import UmbralAbyssLogic
import keyboard
from ui_style import big_toggle, style_toggle, save_while_typing, sound_picker, fast_scroll_frame, seconds_combo, help_box
import os
import links
import time
import threading

def umbral_beta():
    """Umbral Abyss Stone isn't released yet: it only opens on a PC with data/umbral_beta.txt (data/ is never
    pushed, so players see it greyed out)."""
    from settings import get_base_path
    return os.path.exists(os.path.join(get_base_path(), "umbral_beta.txt"))


class MacroSelector:
    def __init__(self, root, on_select, current_version):
        self.root = root
        self.on_select = on_select
        self.current_version = current_version
        self.root.title("VunVun's Macro Hub")
        self.root.geometry("820x520")
        
        self.updater = SpatialUpdater(current_version, "Vunoxoulia", "Clover-Retribution-Macro-App")
        self.setup_ui()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        head = ctk.CTkFrame(self.root, fg_color="transparent")
        head.pack(fill="x", padx=32, pady=(26, 4))
        ctk.CTkLabel(head, text="Select a macro", font=("Arial", 26, "bold"), text_color="#0d6efd").pack(side="left")
        ctk.CTkLabel(head, text=f"v{self.current_version}", font=("Arial", 12),
                     text_color="#adb5bd").pack(side="left", padx=10, pady=(8, 0))

        self.cards_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.cards_frame.pack(expand=True, fill="both", padx=20, pady=(6, 4))
        from logic_events import WATCHER
        cards = [
            ("Library", "📚", "Auto spell clover mastery",
             lambda: self.on_select("Library Macro", LibraryLogic,
                                    tabs=["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"],
                                    tutorial_url="video_library")),
            ("Skill", "⚔", "AFK rotation, combos and item use", self.launch_smart),
            ("Event Notifier", "🔔", "Posts chat events to Discord", self.launch_events),
            ("Mining", "⛏", "Mining away",
             lambda: self.on_select("Mining Macro", MiningLogic, tabs=["Main", "Settings", "Hotkeys"],
                                    tutorial_url="video_mining")),
            ("Fishing", "🎣", "Auto fishy",
             lambda: self.on_select("Fishing Macro", FishingLogic, tabs=["Main", "Fishing Settings", "Hotkeys"],
                                    tutorial_url="video_fishing")),
            ("Umbral Abyss Stone", "🔥", "Auto farm lesser devil Juggernaut",
             (lambda: self.on_select("Umbral Abyss Stone", UmbralAbyssLogic, tabs=["Main", "Routes", "Moves", "Juggernaut",
                                                                        "Spawn", "Server reset", "Hotkeys"]))
             if umbral_beta() else None),       # not released yet: greyed out unless data/umbral_beta.txt exists
        ]
        for k, (title, icon, desc, cmd) in enumerate(cards):
            badge = "on" if title == "Event Notifier" and WATCHER.running else None
            self.create_card(title, icon, desc, cmd, k // 3, k % 3, badge)

        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=(4, 14), padx=24)
        small = dict(height=28, font=("Arial", 12), corner_radius=6)
        ctk.CTkButton(footer, text="↻  Check for updates", width=150, fg_color="#343a40", hover_color="#495057",
                      command=self.check_updates, **small).pack(side="left", padx=(0, 6))
        ctk.CTkButton(footer, text="Patch notes", width=100, fg_color="#343a40", hover_color="#495057",
                      command=self.show_patch_notes, **small).pack(side="left")

        links_frame = ctk.CTkFrame(footer, fg_color="transparent")
        links_frame.pack(side="right")
        link_btn = dict(small, width=96, fg_color="#343a40")
        ctk.CTkButton(links_frame, text="▶  YouTube", hover_color="#9e2622", text_color="#ff6b6b", **link_btn,
                      command=lambda: links.open_link("youtube")).pack(side="left", padx=3)
        ctk.CTkButton(links_frame, text="Discord", hover_color="#4752c4", text_color="#8e96ff", **link_btn,
                      command=lambda: links.open_link("discord")).pack(side="left", padx=3)

        # Donate: pick Robux (Roblox group store) or real money (Ko-fi)
        donate_menu = tk.Menu(self.root, tearoff=0, bg="#212529", fg="#e9ecef", activebackground="#0d6efd",
                              activeforeground="#ffffff", font=("Arial", 12))
        donate_menu.add_command(label="  Robux  (Roblox store)", command=lambda: links.open_link("donate_robux"))
        donate_menu.add_command(label="  Real money  (Ko-fi)", command=lambda: links.open_link("donate_money"))
        donate_btn = ctk.CTkButton(links_frame, text="♥  Donate ▾", hover_color="#e0a800", text_color="#ffc107",
                                   **link_btn)
        donate_btn.configure(command=lambda: donate_menu.tk_popup(donate_btn.winfo_rootx(),
                                                                  donate_btn.winfo_rooty() + donate_btn.winfo_height()))
        donate_btn.pack(side="left", padx=3)

    def launch_events(self):
        from gui_events import EventsOnlyLogic
        self.on_select("Event Notifier", EventsOnlyLogic, tabs=["Events"])

    def launch_smart(self):
        from gui_smart import SmartMacroGUI  # lazy: gui_smart imports from this module
        self.on_select("Skill Macro", None, gui_class=SmartMacroGUI)

    def show_patch_notes(self):
        import requests
        from tkinter import messagebox
        notes_url = "https://raw.githubusercontent.com/Vunoxoulia/Clover-Retribution-Macro-App/main/docs/PATCH_NOTES.txt"
        try:
            response = requests.get(notes_url, timeout=5)
            if response.status_code == 200:
                notes_window = ctk.CTkToplevel(self.root)
                notes_window.title("Latest Patch Notes")
                notes_window.geometry("600x400")
                notes_window.attributes("-topmost", True)
                textbox = ctk.CTkTextbox(notes_window, font=("Consolas", 14), fg_color="#212529", text_color="#f8f9fa")
                textbox.pack(expand=True, fill="both", padx=20, pady=20)
                textbox.insert("0.0", response.text)
                textbox.configure(state="disabled")
            else:
                messagebox.showerror("Error", "Could not fetch patch notes.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")

    def check_updates(self):
        url, version = self.updater.check_for_updates()
        if url: self.updater.install_update(url)

    def create_card(self, title, icon, description, command, row, column, badge=None):
        card = ctk.CTkFrame(self.cards_frame, corner_radius=10, fg_color="#212529", border_color="#343a40",
                            border_width=1)
        card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text=icon, width=38, height=38, corner_radius=8, fg_color="#0b2a4a",
                     text_color="#6ea8fe", font=("Segoe UI Emoji", 18)).pack(side="left")
        ctk.CTkLabel(top, text=title, font=("Arial", 15, "bold"), text_color="#ffffff").pack(side="left", padx=10)
        if badge:
            ctk.CTkLabel(top, text=badge, font=("Arial", 11, "bold"), fg_color="#0f5132", text_color="#75b798",
                         corner_radius=6, width=34, height=20).pack(side="right")
        ctk.CTkLabel(card, text=description, font=("Arial", 12), text_color="#adb5bd", justify="left",
                     anchor="w", wraplength=200).pack(fill="x", padx=14)
        btn = ctk.CTkButton(card, text="Launch", command=command, height=30,
                            font=("Arial", 13, "bold"), fg_color="#0d6efd", hover_color="#0b5ed7")
        if command is None:
            btn.configure(state="disabled", fg_color="#343a40", text_color_disabled="#868e96")
        btn.pack(side="bottom", fill="x", padx=14, pady=14)
        self.cards_frame.grid_columnconfigure(column, weight=1, uniform="card")
        self.cards_frame.grid_rowconfigure(row, weight=1, uniform="card")

NAV_ICONS = {
    "Main": "", "Settings": "", "Areas": "", "Clover Clicker": "",
    "Fishing Settings": "", "Pop Up": "", "Events": "", "Hotkeys": "", "Statistics": "",
}

class SidebarNav:
    """Left-hand navigation with one page per entry. Mirrors the CTkTabview
    add()/tab()/set() API so existing setup_*_tab code works unchanged."""
    def __init__(self, root, title):
        self.root = root
        self.sidebar = ctk.CTkFrame(root, width=150, corner_radius=0, fg_color="#16191c")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkLabel(self.sidebar, text=title, font=("Arial", 14, "bold"), text_color="#0d6efd",
                     wraplength=130, justify="left").pack(anchor="w", padx=14, pady=(16, 12))
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=8)
        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=8, pady=10)
        self.content = ctk.CTkFrame(root, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        self.pages, self.buttons, self.current = {}, {}, None
        self._builders = {}                  # pages built the first time they're opened (opening a macro was slow)

    def add(self, name):
        page = ctk.CTkFrame(self.content, fg_color="#1e2124", corner_radius=10)
        btn = ctk.CTkButton(self.nav_frame, text=f"  {name}", anchor="w",
                            height=34, corner_radius=8, font=("Arial", 13),
                            fg_color="transparent", hover_color="#2b3035", text_color="#ced4da",
                            command=lambda n=name: self.set(n))
        btn.pack(fill="x", pady=2)
        self.pages[name], self.buttons[name] = page, btn
        if self.current is None:
            self.set(name)
        return page

    def tab(self, name):
        return self.pages[name]

    def set(self, name):
        if self.current:
            self.pages[self.current].pack_forget()
            self.buttons[self.current].configure(fg_color="transparent", text_color="#ced4da", font=("Arial", 13))
        self.pages[name].pack(fill="both", expand=True)
        self.buttons[name].configure(fg_color="#0d6efd", text_color="#ffffff", font=("Arial", 13, "bold"))
        self.current = name
        self._build(name)

    def lazy(self, name, builder):
        """Build page `name` only when it's first shown (right away if it's showing now)."""
        self._builders[name] = builder
        if name == self.current:
            self._build(name)

    def _build(self, name):
        fn = self._builders.pop(name, None)
        if fn:
            try:
                fn()
            except Exception as e:
                print(f"Couldn't build page {name}: {e}")

    def get(self):
        return self.current

class SpatialGUI:
    def __init__(self, root, title="Spatial Macro", logic_class=LibraryLogic, on_back=None, tabs=None, tutorial_url="#"):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        self.root.geometry("720x720" if "Mining" in title else "800x760" if "Umbral" in title else "650x700")
        self.tutorial_url = tutorial_url
        self.settings = SpatialSettings()
        self.logic = logic_class(self)
        self.overlays = {} 
        self.tabs_to_show = list(tabs) if tabs else ["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"]
        # Shared OK popup setup page: every macro gets it, placed before Hotkeys
        # (not Umbral Abyss Stone: it doesn't use OK popups or the Event Notifier)
        if "Pop Up" not in self.tabs_to_show and not self._no_ok_events:
            idx = self.tabs_to_show.index("Hotkeys") if "Hotkeys" in self.tabs_to_show else len(self.tabs_to_show)
            self.tabs_to_show.insert(idx, "Pop Up")
        # Shared Event Notifier page: every macro gets it too (runs alongside the macro)
        if "Events" not in self.tabs_to_show and not self._no_ok_events:
            self.tabs_to_show.insert(self.tabs_to_show.index("Pop Up") + 1, "Events")
        self.DEFAULT_CLOVER_COLORS = {"gold": (255, 180, 51), "silver": (164, 178, 178), "bronze": (198, 62, 37)}
        self.DEFAULT_CLOVER_TOLERANCES = {"gold": 5, "silver": 5, "bronze": 5}
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.setup_ui()
        self.register_hotkeys()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.tabview = SidebarNav(self.root, self.root.title())
        for tab_name in self.tabs_to_show: self.tabview.add(tab_name)
        if self.on_back:
            ctk.CTkButton(self.tabview.footer, text="←  Back to Menu", anchor="w", height=32,
                          fg_color="transparent", border_color="#495057", border_width=1,
                          hover_color="#2b3035", text_color="#e9ecef", command=self.go_back).pack(fill="x")
        from logic_events import WATCHER
        if not self._no_ok_events:
            WATCHER.attach(self.settings)    # event checks work before the Events page is ever opened
        # Only the page you see is built now; the others the first time you open them (building every
        # page up front froze the window for seconds when a macro was opened)
        builders = {"Main": self.setup_main_tab, "Settings": self.setup_settings_tab, "Areas": self.setup_areas_tab,
                    "Clover Clicker": self.setup_clover_tab, "Fishing Settings": self.setup_fishing_settings_tab,
                    "Pop Up": self.setup_ok_tab, "Events": self.setup_events_tab,
                    "Hotkeys": self.setup_hotkeys_tab, "Statistics": self.setup_statistics_tab}
        for name in self.UMBRAL_PAGES:
            builders[name] = lambda n=name: self.umbral_page(n)
        for name in self.tabs_to_show:
            if name in builders:
                self.tabview.lazy(name, builders[name])
        if self._is_library:
            self.root.after(1500, self._ocr_check_on_open)

    @property
    def _no_ok_events(self):
        """Umbral Abyss Stone has no OK Popup / Events pages (they aren't used there)."""
        return "Umbral" in self.root.title()

    @property
    def _is_library(self):
        """This window runs the Library macro (not Mining / Fishing, which share this GUI)."""
        from logic_library import LibraryLogic
        return isinstance(self.logic, LibraryLogic)

    def _num_combo(self, parent, key, values, current, minimum=0.0):
        """A seconds box: pick from the list or type any number; saved as you type (not below `minimum`)."""
        def save(v):
            try:
                self.settings.set(key, max(minimum, float(str(v).strip())))
            except (TypeError, ValueError):
                pass
        return seconds_combo(parent, values, current, save)

    def _ocr_check_on_open(self):
        """Library opened: read the WHOLE screen (whatever is on it - this window, Roblox's buttons and
        hotbar, anything) and show a few of the words it read, as proof text reading works on THIS PC,
        screen capture included. Nothing readable on screen -> the built-in test word, then the popup."""
        try:
            region = [0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()]
        except Exception:
            return

        def run():
            from utils import SpatialUtils
            if SpatialUtils.load_ocr():
                ok, worded, lines = SpatialUtils.ocr_read_screen(self.logic.utils.capture_screen_bgr(region))
                if ok:
                    self.log(f"Text reading: OK - read {len(worded)} line(s) on screen, e.g. "
                             + ", ".join(f"'{ln}'" for ln in worded[:3]))
                    return
                self.log(f"Text reading: not enough words on screen (read: "
                         f"{', '.join(repr(ln) for ln in lines[:3]) or 'nothing'}) - trying the test word...")
            if self._ocr_ok():                           # (almost) nothing on screen: the built-in test word
                self.log("Text reading: OK (read the built-in test words 'Clover Training').")
            else:
                self.log("Text reading doesn't work - see the popup (Auto mode and Auto setup need it).")
        threading.Thread(target=run, daemon=True).start()

    def setup_main_tab(self):
        tab = self.tabview.tab("Main")
        ctk.CTkLabel(tab, text=self.root.title().upper(), font=("Arial", 22, "bold"), text_color="#0d6efd").pack(pady=(12, 6))

        self.calib_frame = ctk.CTkFrame(tab, fg_color="#842029", border_color="#f5c2c7", border_width=1, corner_radius=8)
        self.calib_label = ctk.CTkLabel(self.calib_frame, text="UNCALIBRATED SETTINGS DETECTED\nPlease go to Settings tabs to set up.", font=("Arial", 12, "bold"), text_color="#ea868f")
        self.calib_label.pack(padx=12, pady=8)
        self.check_calibration()

        status_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        status_card.pack(fill="x", padx=20, pady=15)
        self.status_label = ctk.CTkLabel(status_card, text="Status: <Not Started>", font=("Arial", 13, "bold"), text_color="#f8f9fa")
        self.status_label.pack(pady=12, padx=10)

        main_btn = dict(height=40, corner_radius=8, font=("Arial", 13, "bold"))      # same size as the big toggles
        # One Start/Stop toggle on one key (F6), like the Skill Macro
        self.start_btn = ctk.CTkButton(tab, text="", command=self.toggle_macro, **main_btn)
        self.start_btn.pack(pady=(6, 4), fill="x", padx=40)
        self._shown_running = None
        self._sync_start_btn()

        # Always-Click-OK toggle — works even when the macro is stopped or paused
        self._always_ok_on = False
        if not self._no_ok_events:
            self.always_ok_btn = big_toggle(tab, self.toggle_always_ok)
            self._ok_toggles = [self.always_ok_btn]
            style_toggle(self.always_ok_btn, False, "Always Click Pop Ups")
            self.always_ok_btn.pack(pady=4, fill="x", padx=40)
            ok_hint = ctk.CTkLabel(tab, text="Set up pop ups (OK and others) on the Pop Up page", font=("Arial", 12),
                                   text_color="#ced4da", cursor="hand2")
            ok_hint.pack(pady=(0, 8))
            ok_hint.bind("<Button-1>", lambda e: self.tabview.set("Pop Up"))
        for key, text in (("force_roblox_focus", "Keep Roblox in focus (brings it back to the front)"),
                          ("show_action_badge", "Show what the macro is doing on top of the game")):
            var = ctk.BooleanVar(value=bool(self.settings.get(key, True)))
            ctk.CTkCheckBox(tab, text=text, variable=var, font=("Arial", 12),
                            command=lambda k=key, v=var: self.settings.set(k, bool(v.get()))).pack(anchor="w", padx=42, pady=2)
        cd_row = ctk.CTkFrame(tab, fg_color="transparent"); cd_row.pack(anchor="w", padx=42, pady=2)
        ctk.CTkLabel(cd_row, text="Click delay: wait", font=("Arial", 12)).pack(side="left")
        self._num_combo(cd_row, "click_delay", ["0.3", "0.5", "0.75", "1", "1.5", "2"],
                        float(self.settings.get("click_delay", 1.0))).pack(side="left", padx=6)
        ctk.CTkLabel(cd_row, text="s after moving the mouse, before each click", font=("Arial", 12)).pack(side="left")
        if "Library" in self.root.title():
            sound_row = ctk.CTkFrame(tab, fg_color="transparent")

            def flip_sound():
                self.settings.set("sound_when_done", bool(snd.get()))
                sound_row.pack(pady=(0, 8), after=snd) if snd.get() else sound_row.pack_forget()
            snd = ctk.CTkCheckBox(tab, text="Play a sound when every move is trained (the macro stops)",
                                  font=("Arial", 12), command=flip_sound)
            if self.settings.get("sound_when_done", False):
                snd.select()
            snd.pack(pady=(0, 2))
            sound_picker(sound_row, "done").pack()
            if snd.get():
                sound_row.pack(pady=(0, 8), after=snd)

        tutorial_link = ctk.CTkLabel(tab, text="Video Tutorial", font=("Arial", 14, "underline"), text_color="#0dcaf0", cursor="hand2")
        tutorial_link.pack(side="bottom", pady=10)
        tutorial_link.bind("<Button-1>", lambda e: links.open_link(self.tutorial_url))   # name in links.txt

    # ================= Mining (recorded routes) =================
    def setup_mining_settings(self, tab):
        card = lambda: ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")

        rc = self._route_card(tab, None, None,
                         "Test Path (F2)", self.logic.test_movement,
                         f"Recording: stand at the start, press {self.logic.rec_key()}, walk the loop, TAP E once at each ore, "
                         f"pause ~0.5s at corners (checkpoints), press {self.logic.rec_key()} again back at the start.")

        share = ctk.CTkFrame(rc, fg_color="transparent"); share.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(share, text="Import route", width=100, command=self._import_route, **btn).pack(side="right")
        ctk.CTkButton(share, text="Export route", width=100, command=self._export_route, **btn).pack(side="right", padx=4)

        # Movement / alignment
        mc = card(); mc.pack(fill="x", padx=15, pady=4)
        # No checks = just follow the recorded path
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(6, 2))
        wait_sw = ctk.CTkSwitch(row, text="Wait for Interact at the start", font=("Arial", 12, "bold"),
                                command=lambda: self.settings.set("mining_wait_interact", bool(wait_sw.get())))
        if self.settings.get("mining_wait_interact", False): wait_sw.select()
        wait_sw.pack(side="left")
        help_box(mc, "Off (default) = start the next lap as soon as it's back at the start.\n"
                     "On = at the start spot, wait until the 'E Interact' prompt shows (the ore is back), "
                     "then walk the route. Record the route so it starts where that prompt shows.\n"
                     "Set area: drag a small box round the prompt - reading text is heavy, a small box is much "
                     "lighter on the PC. No box = the lower middle of the Roblox window.", wait_sw)
        arow = ctk.CTkFrame(mc, fg_color="transparent"); arow.pack(fill="x", padx=6, pady=(0, 4))
        ctk.CTkButton(arow, text="Set area", width=80, command=lambda: self.pick_region("mining_interact"),
                      **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"}).pack(side="left", padx=(42, 4))
        ctk.CTkButton(arow, text="Clear", width=56, command=self._clear_interact_area, **btn).pack(side="left")
        ctk.CTkButton(arow, text="Test", width=56, command=self._test_interact, **btn).pack(side="left", padx=4)
        self.interact_area_lbl = ctk.CTkLabel(arow, text="", font=("Arial", 12))
        self.interact_area_lbl.pack(side="left", padx=6)
        self._show_interact_area()
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(2, 6))
        comma = ctk.CTkSwitch(row, text="Press ',' when starting", font=("Arial", 12, "bold"),
                              command=lambda: self.settings.set("mining_press_comma", bool(comma.get())))
        if self.settings.get("mining_press_comma", True): comma.select()
        comma.pack(side="left")
        help_box(mc, "On (default) = press ',' twice at the start to lock the camera top-down, facing the same "
                     "way as when the route was recorded. Turn off if your camera is already set.", comma)


        # Recorded path per ore
        head = ctk.CTkFrame(tab, fg_color="transparent"); head.pack(fill="x", padx=15, pady=(6, 0))
        t = ctk.CTkLabel(head, text="Recorded Path", font=("Arial", 14, "bold"))
        t.pack(side="left")
        help_box(tab, "Each ore shows the keys you held to walk there (edit the hold time if you need to) "
                      "and how long to mine.", t)
        self.route_panel = ctk.CTkScrollableFrame(tab, fg_color="#1a1d20", corner_radius=8)
        self.route_panel.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        self.route_expanded = {}
        self.refresh_routes()

    def _route_card(self, tab, test1_text, test1_fn, test2_text, test2_fn, tip):
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        rc = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        rc.pack(fill="x", padx=15, pady=(8, 4))
        row = ctk.CTkFrame(rc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(6, 2))
        route_lbl = ctk.CTkLabel(row, text="Route", font=("Arial", 13, "bold"))
        route_lbl.pack(side="left", padx=(0, 6))
        help_box(rc, tip, route_lbl)
        self.route_menu = ctk.CTkOptionMenu(row, values=["(none)"], width=150, command=self._select_route)
        self.route_menu.pack(side="left")
        ctk.CTkButton(row, text="New", width=50, command=self._new_route, **btn).pack(side="left", padx=(6, 2))
        ctk.CTkButton(row, text="Rename", width=64, command=self._rename_route, **btn).pack(side="left", padx=2)
        ctk.CTkButton(row, text="Delete", width=56, command=self._delete_route,
                      **{**btn, "hover_color": "#bb2d3b"}).pack(side="left", padx=2)
        row = ctk.CTkFrame(rc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(2, 6))
        self.rec_label = ctk.CTkLabel(row, text="", font=("Arial", 12, "bold"))
        self.rec_label.pack(side="left")
        ctk.CTkButton(row, text=test2_text, width=110, command=lambda: self._run_test(test2_fn), **btn).pack(side="right")
        if test1_text:
            ctk.CTkButton(row, text=test1_text, width=136, command=lambda: self._run_test(test1_fn), **btn).pack(side="right", padx=4)
        ctk.CTkFrame(rc, fg_color="transparent", height=2).pack()
        return rc

    # ================= Library =================
    def setup_library_settings(self, tab):
        fa = self._full_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#0d6efd", border_width=1,
                                            corner_radius=8)
        fa.pack(fill="x", padx=15, pady=(8, 4))
        t = ctk.CTkLabel(fa, text="Full Auto Setup", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(6, 0))
        help_box(fa, "Record or pick your Route below first, and choose Auto or Image in Wisp dialogue. Then stand "
                              "at the desk and press the button: it finds your hotbar, walks to the wisp, reads every "
                              "move (Image: also takes each button's picture), sets the dialogue, catches "
                              "the minigame and plays the first one. You only choose which moves to train at the end.", t)
        ctk.CTkButton(fa, text="Start Full Auto Setup", height=32, font=("Arial", 13, "bold"), fg_color="#198754",
                      hover_color="#157347", command=self.full_auto_setup).pack(fill="x", padx=8, pady=(6, 8))
        self._route_card(tab, "Dialogue (F1)", self.logic.test_detection,
                         "Test Path (F3)", self.logic.test_path,
                         f"At the desk: {self.logic.rec_key()} → walk to the wisp (jumps and E are recorded too) → {self.logic.rec_key()}.")
        mc = self._moves_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        mc.pack(fill="x", padx=15, pady=4)
        t = ctk.CTkLabel(mc, text="Moves to train", font=("Arial", 13, "bold"))
        t.pack(anchor="w", padx=8, pady=(6, 4))
        ctk.CTkButton(mc, text="Auto setup", width=110, height=24, font=("Arial", 11, "bold"),
                      fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=self.auto_setup_moves).place(relx=1.0, x=-10, y=6, anchor="ne")
        self._moves_desc = help_box(mc, "", t)
        from logic_library import MAX_MOVES
        flags = self.logic.train_flags()
        names = self.logic.move_names()
        slots = self.logic._nine("gold_move_slots", lambda k: k + 1)
        self.train_vars, self.move_entries, self._move_rows = [], [], []
        for i in range(MAX_MOVES):
            row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            self._move_rows.append(row)
            var = ctk.BooleanVar(value=flags[i])
            ctk.CTkCheckBox(row, text=f"Move {i + 1}", variable=var, width=90, font=("Arial", 12, "bold"),
                            command=self._save_train_flags).pack(side="left")
            sel = ctk.CTkOptionMenu(row, values=[str(k) for k in range(1, MAX_MOVES + 1)], width=58, height=26,
                                    command=lambda v, idx=i: self.logic.set_move_slot(idx, v))
            sel.set(str(slots[i]))
            sel.pack(side="right")
            ctk.CTkLabel(row, text="slot", font=("Arial", 12)).pack(side="right", padx=(6, 3))
            e = ctk.CTkEntry(row, placeholder_text="name on the wisp's button", font=("Arial", 12))
            if names[i]: e.insert(0, names[i])
            e.pack(side="left", fill="x", expand=True, padx=(4, 0))
            e.bind("<FocusOut>", lambda ev, idx=i: self.update_move_name(idx))
            save_while_typing(e, lambda idx=i: self.update_move_name(idx))
            self.train_vars.append(var); self.move_entries.append(e)
        ctk.CTkLabel(mc, text="", height=4).pack()
        self.dialog_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        self.dialog_card.pack(fill="x", padx=15, pady=4)
        self.build_dialog_card()
        share = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        share.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(share, text="Share setup", font=("Arial", 13, "bold")).pack(side="left", padx=8, pady=6)
        ctk.CTkButton(share, text="Import", width=80, height=26, fg_color="#495057", hover_color="#343a40",
                      command=self.import_library_setup).pack(side="right", padx=(2, 8))
        ctk.CTkButton(share, text="Export", width=80, height=26, fg_color="#495057", hover_color="#343a40",
                      command=self.export_library_setup).pack(side="right", padx=2)
        ctk.CTkLabel(share, text="moves, dialogue, pictures + your route in one file", font=("Arial", 11),
                     text_color="#adb5bd").pack(side="left", padx=4)
        self.refresh_routes()

    def export_library_setup(self):
        from tkinter import filedialog, messagebox
        import setup_share
        path = filedialog.asksaveasfilename(parent=self.root, title="Export Library setup",
                                            defaultextension=".zip", initialfile="Library setup.zip",
                                            filetypes=[("Setup file", "*.zip")])
        if not path:
            return
        try:
            route = setup_share.export_library(self.logic, path)
        except Exception as e:
            messagebox.showerror("Export", f"Couldn't export: {e}", parent=self.root); return
        self.log(f"Library setup exported to {os.path.basename(path)}"
                 + (f" (with route '{route}')" if route else " (built-in route - not included, everyone has it)"))

    def import_library_setup(self):
        from tkinter import filedialog, messagebox
        import setup_share
        path = filedialog.askopenfilename(parent=self.root, title="Import Library setup",
                                          filetypes=[("Setup file", "*.zip")])
        if not path:
            return
        if not messagebox.askyesno("Import Library setup",
                                   "This REPLACES your Library setup (moves, dialogue mode, spots, pictures).\n"
                                   "Export yours first if you want to keep it.\n\nImport now?", parent=self.root):
            return
        try:
            route = setup_share.import_library(self.logic, path)
        except Exception as e:
            messagebox.showerror("Import", f"Couldn't import: {e}", parent=self.root); return
        self.reload_library_settings()
        messagebox.showinfo("Import", "Library setup imported" + (f", with route '{route}'" if route else "")
                            + ".\n\nSpots and pictures come from the other person's screen - if yours differs "
                              "(size / scaling), run Find moves or re-pick the spots.", parent=self.root)

    # ---------- Wisp dialogue: Auto / Image / Manual ----------
    DIALOG_HINTS = {
        "auto": "Finds the buttons by their shape and clicks by position. Works in any language — try this first.",
        "image": "With the dialogue open, drag a box around each button once. The macro clicks wherever that picture shows up.",
        "manual": "Click the exact spot of each button. Use it if Auto/Image miss. Don't move or resize Roblox afterwards.",
    }

    # 'Moves to train' explained for the selected Wisp dialogue mode (Manual doesn't use this card)
    MOVES_HINTS = {
        "auto": "Tick the moves to train and type ONE word that only that move's button has (e.g. 'Cage' for "
                "Sovereign Magic: Cage Gates) - or let Auto setup fill it in. Auto finds the move by that word, "
                "scrolling the list if needed. Slot = where it sits on your hotbar (for the gold clover check).",
        "image": "Tick the moves to train, then capture each move's button below (Capture). Image finds the move "
                 "by its PICTURE, scrolling the list if needed; the name is a backup if the picture isn't found. "
                 "Slot = where it sits on your hotbar (for the gold clover check).",
    }

    def _out_of_the_way(self, fn):
        """Run fn with the macro window hidden, so it can't cover the wisp's dialogue in the screenshots
        (called from a background thread). The window always comes back."""
        self.root.after(0, self.root.withdraw)
        time.sleep(0.35)
        try:
            return fn()
        finally:
            self.root.after(0, self.root.deiconify)

    def full_auto_setup(self):
        """One button: everything but the route. Runs in the background, F6 / Stop cancels it."""
        from tkinter import messagebox
        from logic_full_setup import FullSetup
        if self.logic.running:
            self.log("Stop the macro first (F6)."); return
        if not messagebox.askokcancel(
                "Full Auto Setup",
                "Stand at the desk (where your route starts), with your moves on the hotbar.\n\n"
                "Press OK - it switches to Roblox by itself. Don't touch the mouse / keyboard until it's done - "
                "F6 stops it. It walks to the wisp and plays one minigame.", parent=self.root):
            return
        runner = FullSetup(self.logic)

        def run():
            self.logic.running = True
            try:
                res = self._out_of_the_way(runner.run)
            except Exception as e:
                res = {"ok": False, "step": "?", "why": str(e), "notes": runner.notes}
            finally:
                self.logic.running = False
            self.root.after(0, lambda: self._full_setup_done(runner, res))
        threading.Thread(target=run, daemon=True).start()

    def _full_setup_done(self, runner, res):
        from tkinter import messagebox
        notes = "\n".join(res.get("notes") or [])
        if not res.get("ok"):
            runner.restore()
            messagebox.showwarning(
                "Full Auto Setup", f"Stopped at '{res.get('step')}': {res.get('why')}\n\n{notes}"
                + (f"\n\nWhat the macro saw: {res['debug']}" if res.get("debug") else "")
                + "\n\nYour old settings were put back.", parent=self.root)
            self.reload_library_settings()
            return
        win = ctk.CTkToplevel(self.root)
        win.title("Full Auto Setup - choose what to train")
        win.geometry("560x" + str(260 + 36 * len(res["chosen"])))
        win.transient(self.root); win.after(150, win.lift)
        ctk.CTkLabel(win, text=notes, font=("Arial", 12), justify="left", anchor="w").pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(win, text="Tick the moves to train (already maxed ones are unticked):",
                     font=("Arial", 12, "bold")).pack(anchor="w", padx=12)
        names = self.logic.move_names()
        ticks = []
        for c in res["chosen"]:
            i = c["move"]
            maxed = bool(res["gold"].get(i))
            row = ctk.CTkFrame(win, fg_color="#212529", corner_radius=6); row.pack(fill="x", padx=12, pady=2)
            var = ctk.BooleanVar(value=not maxed)
            ctk.CTkCheckBox(row, text=f"Move {i + 1} · slot {c['slot']}", variable=var, width=130,
                            font=("Arial", 12, "bold")).pack(side="left", padx=6, pady=5)
            ctk.CTkLabel(row, text=f"{c['name']}  (looks for '{names[i]}')" + ("   - already maxed" if maxed else ""),
                         font=("Arial", 12), text_color="#ffc107" if maxed else "#ced4da").pack(side="left", padx=6)
            ticks.append((i, var))

        def apply(start=False):
            flags = self.logic._nine("train_moves", False)
            for i, v in ticks:
                flags[i] = bool(v.get())
            self.settings.settings["capture_minigame_next"] = True   # the first minigame saves its snapshot
            self.logic.start_at_wisp = bool(start)             # still at the wisp: don't walk the route first
            self.settings.save()
            win.destroy()
            self.reload_library_settings()
            self.log("Full Auto Setup applied." + (" Setting up the minigame detector here at the wisp..."
                                                   if start else ""))
            if start:
                self.toggle_macro()

        def cancel():
            runner.restore()
            win.destroy()
            self.reload_library_settings()
            self.log("Full Auto Setup cancelled - old settings put back.")
        win.protocol("WM_DELETE_WINDOW", cancel)
        btns = ctk.CTkFrame(win, fg_color="transparent"); btns.pack(pady=10)
        ctk.CTkButton(btns, text="Apply", width=110, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=apply).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Apply + Set up minigame", width=170, fg_color="#198754", hover_color="#157347",
                      command=lambda: apply(True)).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Cancel", width=90, fg_color="#495057", hover_color="#343a40",
                      command=cancel).pack(side="left", padx=4)

    def _ocr_ok(self):
        """True when the text reader works. If not (usually the Visual C++ Redistributable is missing), say
        so plainly with the download link instead of reading everything as '(not readable)'."""
        from utils import SpatialUtils
        if SpatialUtils.ocr_works():
            return True
        why = SpatialUtils.ocr_error or ""

        def show():
            from tkinter import messagebox
            if messagebox.askyesno(
                    "Text reading isn't working",
                    "The macro can't read any text on screen, so it can't read the wisp's moves.\n\n"
                    + (why + "\n\n" if why else "") +
                    "Fix: install the Microsoft Visual C++ Redistributable (x64), then restart the macro.\n\n"
                    "Open the download page now?", parent=self.root):
                import webbrowser
                webbrowser.open("https://aka.ms/vs/17/release/vc_redist.x64.exe")
        self.root.after(0, show)
        return False

    def auto_setup_moves(self):
        """Auto setup: read the hotbar, then the wisp's move list, match them, and let the user confirm."""
        from tkinter import messagebox
        if self.logic.running:
            self.log("Stop the macro first."); return
        self.log("Auto setup: switching to Roblox (hotbar visible)...")

        from logic_library import MAX_MOVES
        flags = self.logic.train_flags()
        ticked = {self.logic.move_slot(i): i for i in range(MAX_MOVES) if flags[i]}   # hotbar slot -> Move row
        if not ticked:
            messagebox.showinfo("Auto setup", "Tick the moves you want first - each ticked Move reads the hotbar "
                                              "slot next to it (e.g. tick Move 4 with slot 4).", parent=self.root)
            return
        self._auto_rows = ticked

        def step1():
            if not self.logic.wait_focus_for_test():
                return
            hotbar = self.logic.read_hotbar_names(only_slots=set(ticked))
            if hotbar is not None and not any(t for _, t in hotbar) and not self._ocr_ok():
                return                                   # the text reader can't run: already explained
            if not hotbar:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Auto setup", "Couldn't find your hotbar. Click into Roblox with your skills on the hotbar, "
                                  "then try again.", parent=self.root))
                return
            listing = "\n".join(f"  slot {s}:  {t or '(not readable)'}" for s, t in hotbar)
            self.root.after(0, lambda: ask(hotbar, listing))

        def ask(hotbar, listing):
            ok = messagebox.askokcancel(
                "Auto setup - step 2",
                f"Read on your hotbar:\n{listing}\n\nNow talk to the wisp and open its MOVE LIST "
                f"(click 'Clover Training'). Leave it open and press OK - it switches to Roblox by itself.",
                parent=self.root)
            if ok:
                threading.Thread(target=lambda: step2(hotbar), daemon=True).start()

        def step2(hotbar):
            if not self.logic.wait_focus_for_test():
                return
            self.log("Auto setup: reading the move list (scrolling down)...")
            seen = {}

            def scan():
                out = self.logic.scan_move_list(alive=lambda: not self.logic.running)
                if not out:
                    seen["path"] = self.logic.save_debug_shot("auto_setup")   # what the macro saw, while hidden
                return out
            listed = self._out_of_the_way(scan)
            if not listed:
                where = seen.get("path")
                self.root.after(0, lambda: messagebox.showwarning(
                    "Auto setup", "Couldn't read the wisp's move list. Open it (Clover Training) and try again."
                    + (f"\n\nWhat the macro saw is saved here (send it if it keeps failing):\n{where}" if where else ""),
                    parent=self.root))
                return
            rows = self.logic.match_hotbar_to_list(hotbar, [n for n, _ in listed])
            pictures = {n: p for n, p in listed}
            self.root.after(0, lambda: self._auto_setup_confirm(rows, [n for n, _ in listed], pictures))

        threading.Thread(target=step1, daemon=True).start()

    def _auto_setup_confirm(self, rows, names, pictures):
        """Confirmation: one row per hotbar slot - tick, slot, matched move (changeable)."""
        win = ctk.CTkToplevel(self.root)
        win.title("Auto setup - confirm")
        win.geometry("660x" + str(190 + 40 * len(rows) + 20 * ((len(names) + 1) // 2)))
        win.transient(self.root); win.after(150, win.lift)
        ctk.CTkLabel(win, text="Check each slot's move. If one is wrong, just pick the right one from its list - "
                               "the list holds every move seen in the wisp's dialogue. Untick what you don't "
                               "want to train, then Apply.",
                     font=("Arial", 12), wraplength=620, justify="left").pack(anchor="w", padx=12, pady=(10, 4))
        seen = ctk.CTkFrame(win, fg_color="#1a1d20", corner_radius=6); seen.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(seen, text=f"Seen in the dialogue ({len(names)}):", font=("Arial", 11, "bold"),
                     text_color="#9ec5fe").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 0))
        for i, n in enumerate(names):
            key = getattr(self.logic, "_auto_keys", {}).get(n)
            ctk.CTkLabel(seen, text=f"• {n}" + (f"  → '{key.capitalize()}'" if key else "  → (no unique word)"),
                         font=("Arial", 11), text_color="#ced4da").grid(
                row=1 + i // 2, column=i % 2, sticky="w", padx=8, pady=0)
        ctk.CTkLabel(seen, text="").grid(row=99, column=0, pady=0)
        widgets = []
        for r in rows:
            row = ctk.CTkFrame(win, fg_color="#212529", corner_radius=6); row.pack(fill="x", padx=12, pady=2)
            var = ctk.BooleanVar(value=bool(r["match"]))
            mv = getattr(self, "_auto_rows", {}).get(r["slot"])
            ctk.CTkCheckBox(row, text=(f"Move {mv + 1} · slot {r['slot']}" if mv is not None else f"Slot {r['slot']}"),
                            variable=var, width=120,
                            font=("Arial", 12, "bold")).pack(side="left", padx=6, pady=6)
            pick = r["match"] or (r["suggest"][0] if r["suggest"] else "(skip)")
            note = ctk.CTkLabel(row, text="", font=("Arial", 11), wraplength=250, justify="left")

            def show_word(choice, r=r, note=note):
                key = getattr(self.logic, "_auto_keys", {}).get(choice)
                if choice == "(skip)":
                    note.configure(text="skipped", text_color="#adb5bd")
                elif not key:
                    note.configure(text="no word that's unique to this move - switch the Wisp dialogue to "
                                        "Image mode for it", text_color="#ffc107")
                elif choice == r["match"]:
                    note.configure(text=f"will look for '{key.capitalize()}'  (hotbar: {r['hotbar'][:20] or '?'})",
                                   text_color="#75b798" if r["score"] >= 0.7 else "#ffc107")
                else:
                    note.configure(text=f"will look for '{key.capitalize()}'  (picked by you)", text_color="#ced4da")
            # best guesses for this slot first, then every other move seen in the dialogue
            choices = list(dict.fromkeys([m for m in r["suggest"] if m in names] + names)) + ["(skip)"]
            om = ctk.CTkOptionMenu(row, values=choices, width=230, height=26, command=show_word)
            om.set(pick)
            om.pack(side="left", padx=4)
            note.pack(side="left", padx=6)
            show_word(pick)
            widgets.append((r, var, om))

        def apply():
            rows_of = getattr(self, "_auto_rows", {})
            chosen = [{"slot": r["slot"], "name": om.get(), "train": bool(v.get()),
                       **({"move": rows_of[r["slot"]]} if r["slot"] in rows_of else {})}
                      for r, v, om in widgets if om.get() != "(skip)"]
            for r, v, om in widgets:
                if om.get() == "(skip)":
                    self.log(f"Auto setup: slot {r['slot']} left on (skip) - nothing changed for it")
            self.logic.apply_auto_setup(chosen, pictures)
            win.destroy()
            self.log(f"Auto setup: {len(chosen)} move(s) filled in. Press Find moves to double-check.")
            self.reload_library_settings()
        ctk.CTkButton(win, text="Apply", width=120, fg_color="#198754", hover_color="#157347",
                      command=apply).pack(pady=10)

    def reload_library_settings(self):
        """Rebuild the Settings page (inside its scroll area) so the new names / slots / ticks show."""
        holder = self._moves_card.master
        for w in holder.winfo_children():
            w.destroy()
        self.setup_library_settings(holder)

    def test_find_moves(self, walk=False):
        """F4 (walk=False): find the moves in the move list that's ALREADY open - no walking, no clicks.
        F5 (walk=True): full test - walk the route, open the dialogue, then find the moves.
        Runs in the background and shows the result in a pop-up."""
        hk = self.settings.get("hotkeys", {})
        if walk:
            key = (hk.get("test_full") or "f5").upper()
            self.log(f"Full test: switching to Roblox (or press {key} while in Roblox) - it walks the route, "
                     "opens the wisp's dialogue and hovers each move it finds (no move is clicked).")
        else:
            key = (hk.get("test_find") or "f4").upper()
            self.log(f"Find moves (test): open the wisp's MOVE LIST, then it switches to Roblox (or press {key} "
                     "while in Roblox) - it hovers each move it finds (no walking, nothing is clicked).")
        name = "Full test" if walk else "Find moves"

        def run():
            res = self._out_of_the_way(lambda: self.logic.test_find_moves(walk=walk))
            if res["lines"]:
                from tkinter import messagebox
                title = f"{name} - all found" if res["ok"] else f"{name} - results"
                self.root.after(0, lambda: messagebox.showinfo(title, "\n\n".join(res["lines"]), parent=self.root))
        threading.Thread(target=run, daemon=True).start()

    def _apply_manual_limit(self):
        """Manual dialogue doesn't use 'Moves to train' at all (its 3 spots live in the Wisp dialogue card)."""
        mc = getattr(self, "_moves_card", None)
        if mc is None:
            return
        mode = self.logic.dialog_mode()
        fa = getattr(self, "_full_card", None)
        if fa is not None:                               # Full Auto Setup: Auto / Image only
            if mode == "manual":
                fa.pack_forget()
            elif not fa.winfo_ismapped():
                first = fa.master.pack_slaves()
                fa.pack(fill="x", padx=15, pady=(8, 4), **({"before": first[0]} if first else {}))
        if mode == "manual":
            mc.pack_forget()
            return
        if not mc.winfo_ismapped():
            mc.pack(fill="x", padx=15, pady=4, before=self.dialog_card)
        self._moves_desc.configure(text=self.MOVES_HINTS.get(mode, ""))

    def _dialog_preview(self, parent, key):
        """Show the captured button picture under its row, so you can see exactly what was saved."""
        try:
            from PIL import Image
            pic = Image.open(self.logic.dialog_template_path(key)).convert("RGB")
            pic.load()
            w, h = pic.size
            scale = min(220 / max(w, 1), 34 / max(h, 1), 2.0)
            size = (max(1, int(w * scale)), max(1, int(h * scale)))
            img = ctk.CTkImage(light_image=pic, dark_image=pic, size=size)
            holder = ctk.CTkFrame(parent, fg_color="transparent"); holder.pack(fill="x", padx=8, pady=(0, 4))
            ctk.CTkLabel(holder, text="", image=img).pack(side="left", padx=(158, 0))
        except Exception as e:
            print(f"preview {key}: {e}")

    def build_dialog_card(self):
        from logic_library import DIALOG_BUTTONS, MANUAL_MOVES
        self._apply_manual_limit()
        card = self.dialog_card
        for w in card.winfo_children():
            w.destroy()
        mode = self.logic.dialog_mode()
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 2))
        title = ctk.CTkLabel(head, text="Wisp dialogue", font=("Arial", 13, "bold"))
        title.pack(side="left")
        tips = [self.DIALOG_HINTS[mode]]
        if mode == "manual":
            tips.append("Ticked spots are trained in order: spot 1 until its gold clover shows (checked on its "
                        "hotbar slot), then spot 2, then 3. Just clicks - no reading, no scrolling.")
        if mode != "auto":
            tips.append("Talk to the wisp first so the buttons are on screen, then capture / pick. "
                        "Press Test Dialogue (F1) to check.")
        help_box(card, "\n\n".join(tips), title)
        tools = ctk.CTkFrame(card, fg_color="transparent"); tools.pack(fill="x", padx=8, pady=(0, 4))
        if mode != "manual":                             # manual never scrolls the move list
            ctk.CTkButton(tools, text="↕ Test scroll", width=100, height=24, font=("Arial", 11, "bold"), fg_color="#495057",
                          hover_color="#343a40", command=lambda: self._run_test(self.logic.test_scroll)).pack(side="right", padx=6)
        ctk.CTkButton(tools, text=f"{'Hover spots' if mode == 'manual' else 'Find moves'} ({(self.settings.get('hotkeys', {}).get('test_find') or 'f4').upper()})",
                      width=130, height=24, font=("Arial", 11, "bold"),
                      fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=self.test_find_moves).pack(side="right")
        ctk.CTkButton(tools, text=f"Full test ({(self.settings.get('hotkeys', {}).get('test_full') or 'f5').upper()})",
                      width=125, height=24, font=("Arial", 11, "bold"),
                      fg_color="#198754", hover_color="#157347",
                      command=lambda: self.test_find_moves(walk=True)).pack(side="right", padx=6)
        seg = ctk.CTkSegmentedButton(card, values=["Auto", "Image", "Manual"], font=("Arial", 12, "bold"),
                                     command=lambda v: (self.settings.set("dialog_mode", v.lower()), self.build_dialog_card()))
        seg.set(mode.capitalize())
        seg.pack(fill="x", padx=8, pady=2)
        flags = self.logic.train_flags()
        for key, label in (DIALOG_BUTTONS.items() if mode != "auto" else ()):   # Auto reads words: nothing to capture
            if key.startswith("move_") and not flags[int(key[-1]) - 1]:
                continue                                    # only the moves being trained
            if mode == "manual" and key.startswith("move_"):
                continue                                    # manual: its own 3 spots, built below
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            text = label if key == "clover_training" else self.logic.move_label(int(key[-1]) - 1)
            ctk.CTkLabel(row, text=text, width=150, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
            if mode == "image":
                ok = self.logic.has_dialog_template(key)
                ctk.CTkButton(row, text="Capture" if not ok else "Re-capture", width=110, height=26,
                              fg_color="#0d6efd", hover_color="#0b5ed7",
                              command=lambda k=key: self.capture_dialog_button(k)).pack(side="left", padx=4)
                ctk.CTkLabel(row, text="captured" if ok else "not captured", font=("Arial", 12),
                             text_color="#75b798" if ok else "#ea868f").pack(side="left", padx=6)
                if ok:
                    self._dialog_preview(card, key)
            else:
                pt = self.logic.manual_point(key)
                ctk.CTkButton(row, text="Pick spot", width=110, height=26, fg_color="#0d6efd", hover_color="#0b5ed7",
                              command=lambda k=key: self.pick_dialog_point(k)).pack(side="left", padx=4)
                ctk.CTkLabel(row, text=f"({pt[0]}, {pt[1]})" if pt else "not set", font=("Arial", 12),
                             text_color="#75b798" if pt else "#ea868f").pack(side="left", padx=6)
        if mode == "manual":
            mm = self.logic.manual_moves()
            for i in range(MANUAL_MOVES):
                key = f"move_{i + 1}"
                row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
                var = ctk.BooleanVar(value=bool(mm[i].get("train")))
                ctk.CTkCheckBox(row, text=f"Move spot {i + 1}", variable=var, width=122, font=("Arial", 12, "bold"),
                                command=lambda i=i, v=var: (self.logic.manual_moves()[i].__setitem__("train", bool(v.get())),
                                                            self.settings.save())).pack(side="left")
                pt = self.logic.manual_point(key)
                ctk.CTkButton(row, text="Pick spot", width=96, height=26, fg_color="#0d6efd", hover_color="#0b5ed7",
                              command=lambda k=key: self.pick_dialog_point(k)).pack(side="left", padx=2)
                ctk.CTkLabel(row, text=f"({pt[0]}, {pt[1]})" if pt else "not set", font=("Arial", 12),
                             text_color="#75b798" if pt else "#ea868f", width=62).pack(side="left", padx=2)
                sel = ctk.CTkOptionMenu(row, values=[str(k) for k in range(1, 10)], width=58, height=26,
                                        command=lambda v, i=i: (self.logic.manual_moves()[i].__setitem__("slot", int(v)),
                                                                self.settings.save()))
                sel.set(str(mm[i].get("slot") or i + 1))
                sel.pack(side="right")
                ctk.CTkLabel(row, text="slot", font=("Arial", 12)).pack(side="right", padx=(6, 3))
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 2))
            ctk.CTkLabel(row, text="Wait before each click (s)", font=("Arial", 12)).pack(side="left")
            self._num_combo(row, "dialog_wait", ["0.5", "1", "1.5", "2", "3", "5"],
                            self.settings.get("dialog_wait", 1.5)).pack(side="left", padx=6)
        if mode != "manual":
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 2))
            ctk.CTkLabel(row, text="Wait after Clover Training (s)", font=("Arial", 12)).pack(side="left")
            self._num_combo(row, "after_training_wait", ["0.5", "1", "1.5", "2", "3", "5"],
                            self.logic.after_training_wait()).pack(side="left", padx=6)
            ctk.CTkLabel(row, text="before reading the move list", font=("Arial", 11),
                         text_color="#adb5bd").pack(side="left")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 2))
        ctk.CTkLabel(row, text="Wait for the minigame up to (s)", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "minigame_start_wait", ["15", "20", "30", "45", "60"],
                        self.logic.minigame_start_wait(), minimum=5.0).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="it must SEE it start before it can end", font=("Arial", 11),
                     text_color="#adb5bd").pack(side="left")
        ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

    def capture_dialog_button(self, key):
        self._hide_for_pick()

        def done(x1, y1, x2, y2):
            self.root.after(150, lambda: finish(x1, y1, x2, y2))

        def finish(x1, y1, x2, y2):
            ok = self.logic.capture_dialog_button(key, [x1, y1, x2, y2])
            self.root.deiconify()
            self.log("Button captured." if ok else "Capture failed — drag a bigger box.")
            self.build_dialog_card()
        Overlay(done)

    def pick_dialog_point(self, key):
        self._hide_for_pick()

        def done(x, y):
            self.root.deiconify()
            self.settings.settings.setdefault("positions", {})[key] = [x, y]
            self.settings.save()
            self.build_dialog_card()
        PointSelector(done)

    def _save_train_flags(self):
        self.settings.set("train_moves", [bool(v.get()) for v in self.train_vars])
        if hasattr(self, "dialog_card"):
            self.build_dialog_card()

    def _export_route(self):
        from tkinter import filedialog
        name = self.logic.active_route()
        if not name or not self.logic.load_route():
            self.log("Nothing to export: pick a recorded route first.")
            return
        path = filedialog.asksaveasfilename(parent=self.root, title="Export route", defaultextension=".zip",
                                            initialfile=f"{name}.zip", filetypes=[("Route", "*.zip")])
        if path:
            ok = self.logic.export_route(path, name)
            self.log(f"Route '{name}' exported - others use Import route." if ok else "Couldn't export that route.")

    def _import_route(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(parent=self.root, title="Import route", filetypes=[("Route", "*.zip")])
        if not path:
            return
        try:
            name = self.logic.import_route(path)
        except Exception as e:
            messagebox.showerror("Import route", str(e), parent=self.root)
            return
        self.refresh_routes()
        self.log(f"Route imported as '{name}'. Test Path (F2) to check it lines up for you.")

    def refresh_routes(self):
        if not hasattr(self, "route_menu"):
            return
        for i, om in enumerate(getattr(self, "umbral_loc_menus", [])):   # Umbral: keep the location lists current
            try:
                om.configure(values=["(none)"] + self.logic.list_routes())
                cur = self.logic.location_routes()[i]
                om.set(cur if cur in self.logic.list_routes() else "(none)")
            except Exception:
                pass
        routes = self.logic.list_routes()
        active = self.logic.active_route()
        self.route_menu.configure(values=routes or ["(none)"])
        self.route_menu.set(active or "(none)")
        self.set_recording_ui(self.logic.is_recording())
        if hasattr(self, "route_panel"):
            self.build_route_panel()

    def set_recording_ui(self, recording):
        self._rec_badge(recording)
        if not hasattr(self, "rec_label"):
            return
        if recording:
            self.rec_label.configure(text=f"● RECORDING… ({self.logic.rec_key()} to finish)", text_color="#ea868f")
            return
        r = self.logic.load_route()
        if r:
            n_cp = sum(len(sg.get("checkpoints", [])) for sg in r["segments"]) + len(r["return"].get("checkpoints", []))
            what = (f"{r['ores']} ores, {n_cp} checkpoints" if "Mining" in self.root.title()
                    else f"recorded ({sum(s['duration'] for s in r['segments']) or r['return']['duration']:.1f}s walk)")
            lock = self.logic.is_locked()
            self.rec_label.configure(text=(f"built-in · {what} · {self.logic.rec_key()} records a new route of your own"
                                           if lock else what), text_color="#75b798")
        else:
            builtins = list(self.logic._builtins()) if hasattr(self.logic, "_builtins") else []
            if builtins:
                self.rec_label.configure(text=f"Not recorded — '{builtins[0]}' will be used ({self.logic.rec_key()} to record your own)",
                                         text_color="#ffc107")
            else:
                self.rec_label.configure(text=f"Not recorded yet — press {self.logic.rec_key()}", text_color="#ced4da")

    def _rec_badge(self, on):
        """Red '● REC' badge on top of the Roblox window while recording (never takes focus)."""
        old = getattr(self, "_badge", None)
        if old is not None:
            old.destroy(); self._badge = None
        if on:
            try:
                l, t, r, b = self.logic.get_roblox_window_region()
                from overlay import RecordingBadge
                self._badge = RecordingBadge((l + r) / 2, t + 40, key=self.logic.rec_key())
            except Exception as e:
                print(f"REC badge: {e}")

    def _select_route(self, name):
        if name in self.logic.list_routes():
            self.logic.set_active_route(name)
            self.refresh_routes()

    def _ask(self, title, text, initial=""):
        d = ctk.CTkInputDialog(title=title, text=text)
        try:
            if initial: d._entry.insert(0, initial)
        except Exception:
            pass
        return d.get_input()

    def _new_route(self):
        name = self._ask("New route", "Name for the new route (e.g. Tundra, Cave):")
        if name and self.logic.create_route(name):
            self.refresh_routes()
            self.log(f"Route '{name}' created. Stand at its start spot and press {self.logic.rec_key()} to record.")
        elif name:
            self.log("That name is empty or already used.")

    def _rename_route(self):
        old = self.logic.active_route()
        if not old: return
        if self.logic.is_locked(old):
            self.log(f"'{old}' is built in and can't be renamed. Press New to make your own route."); return
        new = self._ask("Rename route", f"New name for '{old}':", old)
        if new and self.logic.rename_route(old, new):
            self.refresh_routes()
        elif new:
            self.log("That name is empty or already used.")

    def _delete_route(self):
        from tkinter import messagebox
        name = self.logic.active_route()
        if self.logic.is_locked(name):
            self.log(f"'{name}' is built in and can't be deleted."); return
        if name and messagebox.askyesno("Delete route", f"Delete route '{name}' and its recording?"):
            self.logic.delete_route(name)
            self.refresh_routes()
            self.log(f"Route '{name}' deleted.")

    @staticmethod
    def _holds(seg):
        """Turn down/up events into [{key, start, dur, up}] where up = index of the release event."""
        holds, open_ = [], {}
        for i, (t, key, kind) in enumerate(seg["events"]):
            if kind == "down":
                open_[key] = (t, len(holds))
                holds.append({"key": key, "start": t, "dur": None, "up": None})
            elif key in open_:
                t0, h = open_.pop(key)
                holds[h].update(dur=t - t0, up=i)
        return [h for h in holds if h["dur"] is not None]

    def build_route_panel(self):
        for w in self.route_panel.winfo_children():
            w.destroy()
        route = self.logic.load_route()
        if not route:
            ctk.CTkLabel(self.route_panel, text=f"No recording for this route yet.\nStand at the start spot in-game and press {self.logic.rec_key()}.",
                         font=("Arial", 12), text_color="#ced4da").pack(pady=20)
            return
        items = [(f"Ore {i}", i - 1, seg) for i, seg in enumerate(route["segments"], start=1)]
        items.append(("Return to start", "return", route["return"]))
        for title, key, seg in items:
            c = ctk.CTkFrame(self.route_panel, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            c.pack(fill="x", padx=4, pady=3)
            summary = f"{title}   ·   walk {seg['duration']:.1f}s   ·   {len(seg.get('checkpoints', []))} checkpoints"
            open_ = self.route_expanded.get(key, False)
            hb = ctk.CTkButton(c, text=f"{summary}   {'▾' if open_ else '▸'}", anchor="w", height=32, corner_radius=6,
                               font=("Arial", 13, "bold"), fg_color="#0d6efd", hover_color="#0b5ed7")
            hb.pack(fill="x", padx=6, pady=6)
            body = ctk.CTkFrame(c, fg_color="transparent")
            hb.configure(command=lambda k=key: (self.route_expanded.__setitem__(k, not self.route_expanded.get(k, False)),
                                                self.build_route_panel()))
            if not open_:
                continue
            body.pack(fill="x", padx=8, pady=(0, 6))
            if key != "return":
                r = ctk.CTkFrame(body, fg_color="transparent"); r.pack(fill="x", pady=(0, 4))
                for label, field in (("Mining Secs:", "mine_hold"), ("Waiting Secs:", "mine_wait")):
                    ctk.CTkLabel(r, text=label, font=("Arial", 12, "bold")).pack(side="left", padx=(0, 2))
                    e = ctk.CTkEntry(r, width=52, font=("Arial", 12))
                    e.insert(0, f"{float(seg.get(field, 3.0 if field == 'mine_hold' else 1.75)):.2f}")
                    e.pack(side="left", padx=(0, 10))
                    e.bind("<FocusOut>", lambda ev, k=key, f=field, w=e: self._save_seg_value(k, f, w.get()))
                    save_while_typing(e, lambda k=key, f=field, w=e: self._save_seg_value(k, f, w.get()))
            ctk.CTkLabel(body, text="Walk (key · starts at · hold secs):", font=("Arial", 12, "bold")).pack(anchor="w")
            for h in self._holds(seg):
                r = ctk.CTkFrame(body, fg_color="#2b3035", corner_radius=6); r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=h["key"].upper(), width=46, font=("Arial", 13, "bold"), text_color="#9ec5fe").pack(side="left", padx=6)
                ctk.CTkLabel(r, text=f"at {h['start']:.2f}s", width=80, font=("Arial", 12), text_color="#ced4da").pack(side="left")
                e = ctk.CTkEntry(r, width=60, font=("Arial", 12)); e.insert(0, f"{h['dur']:.2f}"); e.pack(side="left", padx=6, pady=3)
                e.bind("<FocusOut>", lambda ev, k=key, h=h, w=e: self._save_hold(k, h, w.get()))
                save_while_typing(e, lambda k=key, h=h, w=e: self._save_hold(k, h, w.get()))

    def _route_seg(self, route, key):
        return route["return"] if key == "return" else route["segments"][key]

    def _save_seg_value(self, key, field, text):
        route = self.logic.load_route()
        try:
            self._route_seg(route, key)[field] = max(0.0, float(text))
            self.logic.save_route(route)
        except (ValueError, TypeError, IndexError):
            pass

    def _save_hold(self, key, hold, text):
        """Change how long a key is held: moves its release event."""
        route = self.logic.load_route()
        try:
            dur = max(0.0, float(text))
        except ValueError:
            return
        seg = self._route_seg(route, key)
        ev = seg["events"][hold["up"]]
        ev[0] = round(hold["start"] + dur, 3)
        seg["events"].sort(key=lambda e: e[0])
        seg["duration"] = round(max(seg["duration"], ev[0]), 3)
        self.logic.save_route(route)
        self.build_route_panel()

    def _ok_card(self, parent, step, title, desc):
        card = ctk.CTkFrame(parent, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        card.pack(fill="x", padx=16, pady=5)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 0))
        t = ctk.CTkLabel(head, text=f"{step}. {title}", font=("Arial", 13, "bold"), text_color="#f8f9fa")
        t.pack(side="left")
        status = ctk.CTkLabel(head, text="", font=("Arial", 11, "bold"))
        status.pack(side="right")
        help_box(card, desc, t)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(4, 8))
        return status, row

    def setup_ok_tab(self):
        tab = fast_scroll_frame(self.tabview.tab("Pop Up"))
        t = ctk.CTkLabel(tab, text="Pop Up Detection", font=("Arial", 18, "bold"), text_color="#0d6efd")
        t.pack(pady=(12, 8))
        help_box(tab, "Shared by every macro, so you only set it up once. The OK popup (steps 1-4) and your other "
                      "pop ups (step 5) are always clicked while a macro runs. Always Click Pop Ups also clicks "
                      "them when no macro is running.", t)
        if not hasattr(self, "_always_ok_on"):
            self._always_ok_on = False
        self._ok_toggles = getattr(self, "_ok_toggles", [])
        ok_toggle = big_toggle(tab, self.toggle_always_ok)
        ok_toggle.pack(pady=(0, 8), fill="x", padx=20)
        self._ok_toggles.append(ok_toggle)
        style_toggle(ok_toggle, self._always_ok_on, "Always Click Pop Ups")
        if not hasattr(self, "always_ok_btn"):
            self.always_ok_btn = ok_toggle
        btn_kw = dict(height=28, font=("Arial", 12), fg_color="#0d6efd", hover_color="#0b5ed7")
        sub_kw = dict(height=28, width=70, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")

        self.ok_btn_status, row = self._ok_card(tab, 1, "Capture OK Button",
            "Open an OK popup in Roblox, then drag a tight box around the OK button.")
        ctk.CTkButton(row, text="Capture", command=self.pick_ok_button, **btn_kw).pack(side="left")
        self.ok_preview = ctk.CTkLabel(row, text="")
        self.ok_preview.pack(side="left", padx=12)

        self.ok_area_status, row = self._ok_card(tab, 2, "Scan Area  (optional)",
            "Where to look for the button. Default: the whole screen. Set a smaller area to make it lighter.")
        ctk.CTkButton(row, text="Set Area", command=lambda: self.pick_region("ok_scan_area"), **btn_kw).pack(side="left")
        ctk.CTkButton(row, text="Clear", command=lambda: self._clear_ok_setting("ok_scan_area", [0, 0, 0, 0]), **sub_kw).pack(side="left", padx=6)
        self.ok_area_switch = ctk.CTkSwitch(row, text="Show on screen", font=("Arial", 12), command=self.toggle_ok_area_overlay)
        self.ok_area_switch.pack(side="left", padx=6)

        self.ok_click_status, row = self._ok_card(tab, 3, "Click Spot  (optional)",
            "A fixed point to click when the popup is found. Defaults to the button itself.")
        ctk.CTkButton(row, text="Set Spot", command=lambda: self.pick_point("ok_click_pos"), **btn_kw).pack(side="left")
        ctk.CTkButton(row, text="Clear", command=lambda: self._clear_ok_setting("ok_click_pos", [0, 0]), **sub_kw).pack(side="left", padx=6)

        _, row = self._ok_card(tab, 4, "Test & Tune",
            "Lower the match % if it misses the popup, raise it if it clicks when no popup is open.")
        ctk.CTkButton(row, text="▶ Test Now", command=lambda: self._run_test(self.logic.test_ok_popup), **btn_kw).pack(side="left")
        thr = float(self.settings.get("ok_match_threshold", 0.80))
        self.ok_thr_label = ctk.CTkLabel(row, text=f"Match: {int(thr * 100)}%", width=80, font=("Arial", 12))
        self.ok_thr_label.pack(side="right")
        slider = ctk.CTkSlider(row, from_=0.5, to=0.98, number_of_steps=48, command=self._update_ok_threshold)
        slider.set(thr)
        slider.pack(side="right", fill="x", expand=True, padx=8)
        self.refresh_ok_status()

        # 5. other pop ups: a picture of something only that pop up shows + where to click to close it
        card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        card.pack(fill="x", padx=16, pady=5)
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=10, pady=(8, 0))
        t5 = ctk.CTkLabel(head, text="5. Other Pop Ups", font=("Arial", 13, "bold"), text_color="#f8f9fa")
        t5.pack(side="left")
        help_box(card, "Any other pop up that gets in the way (e.g. Delayed Packages). For each one: open it in "
                       "Roblox, press Capture and drag a box around something ONLY that pop up shows (its title is "
                       "best), then Click spot = where to click to close it (e.g. its X). Test looks for it now and "
                       "clicks. It uses the same Match % and Scan Area as the OK button.", t5)
        self._popup_box = ctk.CTkFrame(card, fg_color="transparent"); self._popup_box.pack(fill="x", padx=6)
        ctk.CTkButton(card, text="+ Add pop up", width=120, command=self._add_popup, **btn_kw).pack(
            anchor="w", padx=10, pady=(4, 10))
        for pp in self.logic.popups():
            self._popup_row(pp)

    def _add_popup(self):
        name = self._ask("Add pop up", "Name of the pop up (e.g. Delayed Packages):")
        if name is None:
            return
        self._popup_row(self.logic.add_popup(name.strip() or "Pop up"))

    def _popup_row(self, pp):
        BTN_ = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        BLUE_ = dict(height=28, font=("Arial", 12), fg_color="#0d6efd", hover_color="#0b5ed7")
        box = ctk.CTkFrame(self._popup_box, fg_color="#1a1d20", corner_radius=6); box.pack(fill="x", padx=4, pady=3)
        r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x", padx=6, pady=(6, 2))
        on = ctk.CTkCheckBox(r1, text="", width=24, command=lambda: (pp.__setitem__("enabled", bool(on.get())),
                                                                     self.settings.save()))
        if pp["enabled"]:
            on.select()
        on.pack(side="left")
        name = ctk.CTkEntry(r1, width=180, font=("Arial", 12)); name.insert(0, pp["name"]); name.pack(side="left", padx=4)
        store = lambda *_: (pp.__setitem__("name", name.get().strip() or "Pop up"), self.settings.save())
        name.bind("<FocusOut>", store); save_while_typing(name, store)
        pic = ctk.CTkLabel(r1, text="", font=("Arial", 12)); pic.pack(side="left", padx=8)
        ctk.CTkButton(r1, text="Delete", width=70, fg_color="#842029", hover_color="#6a1a21", height=28,
                      font=("Arial", 12), command=lambda: (self.logic.remove_popup(pp), box.destroy())).pack(side="right")
        r2 = ctk.CTkFrame(box, fg_color="transparent"); r2.pack(fill="x", padx=6, pady=(2, 6))
        spot = ctk.CTkLabel(r2, text="", font=("Arial", 12))

        def show():
            has = self.logic.has_popup_picture(pp)
            img = None
            if has:
                try:
                    from PIL import Image
                    im = Image.open(self.logic.popup_path(pp)).convert("RGB")
                    im.thumbnail((160, 30))
                    img = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
                except Exception:
                    img = None
            pic.configure(image=img, text="" if img else ("picture saved" if has else "no picture yet"),
                          text_color="#75b798" if has else "#ea868f")
            pic._img = img
            spot.configure(text=f"click at ({pp['click'][0]}, {pp['click'][1]})" if any(pp["click"])
                           else "no click spot yet", text_color="#75b798" if any(pp["click"]) else "#ea868f")

        def capture():
            self._hide_for_pick()

            def done(x1, y1, x2, y2):
                def save():
                    ok = self.logic.capture_popup(pp, [x1, y1, x2, y2])
                    self.root.deiconify()
                    self.log(f"Pop up '{pp['name']}': picture saved." if ok else "Capture failed - drag a bigger box.")
                    show()
                self.root.after(300, save)
            Overlay(done)

        def pick_spot():
            self._hide_for_pick()

            def done(x, y):
                self.root.deiconify()
                pp["click"] = [x, y]
                self.settings.save()
                self.log(f"Pop up '{pp['name']}': click spot set to ({x}, {y}).")
                show()
            PointSelector(done)
        ctk.CTkButton(r2, text="Capture", width=80, command=capture, **BLUE_).pack(side="left")
        ctk.CTkButton(r2, text="Click spot", width=90, command=pick_spot, **BLUE_).pack(side="left", padx=6)
        ctk.CTkButton(r2, text="Test", width=60, command=lambda: self._run_test(lambda: self.logic.test_popup(pp)),
                      **BTN_).pack(side="left")
        spot.pack(side="left", padx=8)
        show()

    def _update_ok_threshold(self, val):
        self.settings.set("ok_match_threshold", round(float(val), 2))
        self.ok_thr_label.configure(text=f"Match: {int(float(val) * 100)}%")

    def _clear_ok_setting(self, key, empty):
        self.settings.settings["regions"][key] = empty
        self.settings.save()
        if key == "ok_scan_area" and self.ok_area_switch.get() == 1:
            self.toggle_ok_area_overlay()
        self.refresh_ok_status()

    def refresh_ok_status(self):
        if not hasattr(self, "ok_btn_status"):
            return
        regions = self.settings.get("regions", {})
        is_set = lambda k: any(v != 0 for v in regions.get(k, [0]))
        good, muted = "#75b798", "#6c757d"
        tpl_ok = is_set("ok_button") and os.path.exists(self.logic._ok_template_path())
        self.ok_btn_status.configure(text="Captured" if tpl_ok else "Not set",
                                     text_color=good if tpl_ok else "#ea868f")
        self.ok_area_status.configure(text="Custom" if is_set("ok_scan_area") else "Default",
                                      text_color=good if is_set("ok_scan_area") else muted)
        pos = regions.get("ok_click_pos", [0, 0])
        self.ok_click_status.configure(text=f"({pos[0]}, {pos[1]})" if is_set("ok_click_pos") else "Default",
                                       text_color=good if is_set("ok_click_pos") else muted)
        try:
            from PIL import Image
            if tpl_ok:
                img = Image.open(self.logic._ok_template_path())
                img.thumbnail((140, 40))
                self._ok_preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.ok_preview.configure(image=self._ok_preview_img)
        except Exception:
            pass

    def check_calibration(self):
        if not hasattr(self, "calib_frame"):
            return                                   # windows without a Main page (Event Notifier)
        regions = self.settings.get("regions", {})
        if "Fishing" in self.root.title():
            essential = ["minigame_bar", "fishing_click_pos"]
        elif "Mining" in self.root.title():
            essential = []
        else:
            essential = []
            
        missing = [r for r in essential if r not in regions or all(v == 0 for v in regions[r])]
        if missing: self.calib_frame.pack(pady=10, fill="x", padx=20)
        else: self.calib_frame.pack_forget()

    def go_back(self):
        self.logic.stop()
        keyboard.unhook_all()
        if self.on_back: self.on_back()

    def setup_events_tab(self):
        from gui_events import EventsPage
        self.events_page = EventsPage(self.tabview.tab("Events"), self.root, self.settings)

    def toggle_always_ok(self):
        self._always_ok_on = not self._always_ok_on
        for b in getattr(self, "_ok_toggles", [self.always_ok_btn]):      # Main page + OK page stay in sync
            style_toggle(b, self._always_ok_on, "Always Click Pop Ups")
        if self._always_ok_on:
            self.logic.start_global_ok_scanner()
        else:
            self.logic.stop_global_ok_scanner()

    def setup_settings_tab(self):
        tab = self.tabview.tab("Settings")
        if "Mining" in self.root.title():
            self.setup_mining_settings(tab)
            return

        self.setup_library_settings(fast_scroll_frame(tab))

    UMBRAL_PAGES = ("Routes", "Moves", "Juggernaut", "Spawn", "Server reset")

    def umbral_page(self, name):
        """Build one Umbral Abyss Stone page (each has its own tab)."""
        tab = fast_scroll_frame(self.tabview.tab(name))
        {"Routes": self._umbral_routes_page, "Moves": self._umbral_moves_page, "Juggernaut": self._umbral_jug_page,
         "Spawn": self._umbral_spawn_page, "Server reset": self._umbral_server_page}[name](tab)

    def _umbral_routes_page(self, tab):
        from logic_umbral_abyss import LOCATIONS
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        card_kw = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        # --- routes: one F9 -> F9 walk from the crystal spawn to each place the Juggernaut can be
        rc = self._route_card(tab, None, None, "Test Path", self.logic.test_path,
                              f"Stand at the crystal spawn (right after respawning), press {self.logic.rec_key()}, "
                              f"walk to where the Juggernaut can be - stop close to it - and press "
                              f"{self.logic.rec_key()} again. Make one route per location, then pick them below.")
        share = ctk.CTkFrame(rc, fg_color="transparent"); share.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkButton(share, text="Import route", width=100, command=self._import_route, **btn).pack(side="right")
        ctk.CTkButton(share, text="Export route", width=100, command=self._export_route, **btn).pack(side="right", padx=4)

        # --- the 3 locations
        lc = ctk.CTkFrame(tab, **card_kw); lc.pack(fill="x", padx=15, pady=4)
        t = ctk.CTkLabel(lc, text="Locations", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(8, 4))
        help_box(lc, "Each run: crystal spawn -> walk location 1's route -> Juggernaut there? kill it -> respawn -> "
                     "location 2 -> location 3 -> again. '(none)' skips a location.\n"
                     "Loadout = your 3 routes as one bundle: switch between sets in one click. New makes a loadout "
                     f"with 3 fresh empty routes. Stand at the crystal spawn and press Record next to a location: it "
                     f"switches to Roblox and records - walk there, then press {self.logic.rec_key()} to finish. Delete removes the bundle only; "
                     "its routes stay.", t)
        row = ctk.CTkFrame(lc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(row, text="Loadout", width=90, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
        self.umbral_loadout_menu = ctk.CTkOptionMenu(row, values=list(self.logic.loadouts()), width=200, height=26,
                                                     command=self._pick_loadout)
        self.umbral_loadout_menu.set(self.logic.active_loadout())
        self.umbral_loadout_menu.pack(side="left", padx=4)
        row = ctk.CTkFrame(lc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(row, text="", width=90).pack(side="left")
        ctk.CTkButton(row, text="New loadout", width=100, command=self._new_loadout,
                      **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"}).pack(side="left", padx=(6, 2))
        ctk.CTkButton(row, text="Rename", width=80, command=self._rename_loadout, **btn).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Delete", width=80, command=self._delete_loadout,
                      **{**btn, "fg_color": "#842029", "hover_color": "#6a1a21"}).pack(side="left", padx=2)
        self.umbral_loc_menus = []
        current = self.logic.location_routes()
        for i in range(LOCATIONS):
            row = ctk.CTkFrame(lc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=f"Location {i + 1}", width=90, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
            om = ctk.CTkOptionMenu(row, values=["(none)"] + self.logic.list_routes(), width=200, height=26,
                                   command=lambda v, i=i: self.logic.set_location_route(i, v))
            om.set(current[i] or "(none)")
            om.pack(side="left", padx=4)
            self.umbral_loc_menus.append(om)
            self._mark(f"umbral_loc_{i}", om)
            rb = ctk.CTkButton(row, text="Record", width=64, command=lambda i=i: self._record_location(i), **btn)
            rb.pack(side="left", padx=4)
            self._mark(f"umbral_record_{i}", rb)
        ctk.CTkFrame(lc, fg_color="transparent", height=4).pack()

        self.refresh_routes()                            # fill the Route list (and the recorded / not recorded line)

    def _umbral_server_page(self, tab):
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        card_kw = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        # --- server reset: after all locations -> main menu -> new server -> warm-up
        sc = ctk.CTkFrame(tab, **card_kw); sc.pack(fill="x", padx=15, pady=4)
        head = ctk.CTkFrame(sc, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(8, 4))
        t = ctk.CTkLabel(head, text="Main menu clicks", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(side="left")
        help_box(sc, "Every click here is: move the mouse, wait 'Mouse: wait', then click - so it never clicks before "
                     "the mouse has arrived. "
                     "When every location is done it clicks Menu click 1 then Menu click 2 (waiting before each click) "
                     "to go to the main menu. With 'Reset server' on it then waits for the main menu, clicks the server "
                     "box, types your code, clicks Enter Server and waits until you've spawned. Once the menu is found it waits "
                     "a few more seconds, because its buttons slide in. Warm-up: for that many "
                     "minutes it just respawns, waits until spawned, stands still 'every' seconds, again - then the "
                     "normal routes until all locations are done again.", t)
        self.umbral_end_lbls = []
        for i in range(2):
            row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=f"Menu click {i + 1}", width=110, anchor="w", font=("Arial", 12)).pack(side="left")
            ctk.CTkButton(row, text="Pick spot", width=80, command=lambda i=i: self._pick_end_click(i),
                          **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"}).pack(side="left", padx=4)
            ctk.CTkButton(row, text="Clear", width=56, command=lambda i=i: self._set_end_click(i, [0, 0]),
                          **btn).pack(side="left")
            lbl = ctk.CTkLabel(row, text="", font=("Arial", 12)); lbl.pack(side="left", padx=6)
            self.umbral_end_lbls.append(lbl)
        self._show_end_click()
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(2, 6))
        ctk.CTkLabel(row, text="Wait", font=("Arial", 12)).pack(side="left", padx=(0, 4))
        self._num_combo(row, "umbral_end_click_wait", ["0.5", "1", "1.5", "2", "3", "5"],
                        float(self.settings.get("umbral_end_click_wait", 1.0))).pack(side="left")
        ctk.CTkLabel(row, text="s before each click (M1)", font=("Arial", 12)).pack(side="left", padx=4)
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(row, text="Mouse: wait", font=("Arial", 12)).pack(side="left", padx=(0, 4))
        self._num_combo(row, "click_delay", ["0.3", "0.5", "0.75", "1", "1.5", "2"],
                        float(self.settings.get("click_delay", 1.0))).pack(side="left")
        ctk.CTkLabel(row, text="s after moving, before clicking (all macros)", font=("Arial", 12)).pack(side="left", padx=4)

        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        rs = ctk.CTkSwitch(row, text="Reset server (main menu -> new server)", font=("Arial", 12, "bold"),
                           command=lambda: self.settings.set("umbral_reset_server", bool(rs.get())))
        if self.settings.get("umbral_reset_server", False):
            rs.select()
        rs.pack(side="left")
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Wait for the main menu", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "umbral_menu_wait", ["10", "15", "20", "30", "45", "60"],
                        float(self.settings.get("umbral_menu_wait", 20)), minimum=1).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="s (at most), then", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "umbral_menu_settle", ["1", "2", "3", "4", "5"],
                        float(self.settings.get("umbral_menu_settle", 3.0))).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="s for the buttons", font=("Arial", 12)).pack(side="left")
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Main menu check", width=110, anchor="w", font=("Arial", 12)).pack(side="left")
        mseg = ctk.CTkSegmentedButton(row, values=["Manual", "Automatic"], font=("Arial", 12, "bold"), width=170,
                                      command=lambda v: self.settings.set("umbral_menu_mode",
                                                                          "auto" if v == "Automatic" else "manual"))
        mseg.set("Automatic" if self.settings.get("umbral_menu_mode", "manual") == "auto" else "Manual")
        mseg.pack(side="left", padx=4)
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        self._mark("umbral_menu", ctk.CTkButton(row, text="Capture menu", width=110, command=self._capture_umbral_menu,
                                                **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"}))
        self._target("umbral_menu").pack(side="left")
        ctk.CTkButton(row, text="Test", width=56, command=lambda: self._run_test(self.logic.test_menu),
                      **btn).pack(side="left", padx=4)
        self.umbral_menu_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12))
        self.umbral_menu_lbl.pack(side="left", padx=6)
        self._show_umbral_menu()
        self.umbral_server_lbls = {}
        for key, text in (("umbral_server_box", "Server box"), ("umbral_server_enter", "Enter Server")):
            row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=text, width=110, anchor="w", font=("Arial", 12)).pack(side="left")
            pb = ctk.CTkButton(row, text="Pick spot", width=80, command=lambda k=key: self._pick_umbral_point(k),
                               **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"})
            pb.pack(side="left", padx=4)
            self._mark(key, pb)
            lbl = ctk.CTkLabel(row, text="", font=("Arial", 12)); lbl.pack(side="left", padx=6)
            self.umbral_server_lbls[key] = lbl
        self._show_umbral_points()
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Server code", width=110, anchor="w", font=("Arial", 12)).pack(side="left")
        code = ctk.CTkEntry(row, width=160, font=("Arial", 12))
        code.insert(0, str(self.settings.get("umbral_server_code", "")))
        code.pack(side="left", padx=4)
        store_code = lambda *_: self.settings.set("umbral_server_code", code.get().strip())
        code.bind("<FocusOut>", store_code)
        save_while_typing(code, store_code)
        row = ctk.CTkFrame(sc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 10))
        ctk.CTkLabel(row, text="Warm-up", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "umbral_warm_minutes", ["0", "1", "2", "3", "5", "10"],
                        float(self.settings.get("umbral_warm_minutes", 5))).pack(side="left", padx=4)
        ctk.CTkLabel(row, text="min: respawn every", font=("Arial", 12)).pack(side="left", padx=4)
        self._num_combo(row, "umbral_warm_every", ["10", "20", "30", "45", "60"],
                        float(self.settings.get("umbral_warm_every", 30)), minimum=1).pack(side="left")
        ctk.CTkLabel(row, text="s", font=("Arial", 12)).pack(side="left", padx=4)

    def _umbral_moves_page(self, tab):
        from gui_umbral_moves import UmbralMovesPage
        self.umbral_moves_page = UmbralMovesPage(self, tab)

    def _umbral_jug_page(self, tab):
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        card_kw = dict(fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        # --- finding it
        jc = ctk.CTkFrame(tab, **card_kw); jc.pack(fill="x", padx=15, pady=4)
        t = ctk.CTkLabel(jc, text="Juggernaut", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(8, 4))
        help_box(jc, "At the end of each route it looks for the Juggernaut by colour: a very dark body with red marks "
                     "(a purple haze = corrupted). Works best when the route stops close to it. Not seen = not there: "
                     "it respawns and goes to the next location. Check now only looks - it presses nothing.\n"
                     "Look in: Set area = only look inside your box (e.g. where it stands at the end of the route).\n"
                     "Colours: Auto (nothing picked) handles bright fog AND dark caves. Or Pick Colour 1 (e.g. its dark "
                     "body) AND Colour 2 (e.g. a bright red mark): it only counts when both are found together, so a red "
                     "roof or a dark tree alone doesn't.\n"
                     "Must be close: a colour-1 pixel only counts with colour 2 within that many pixels (its red marks "
                     "sit right on its dark body), so a red thing and a dark thing that are just both on screen "
                     "don't count. Fog and morning light make the marks pinker: Colour 1's Tol about 40 covers "
                     "night, morning and fog.\n"
                     "Checks: not seen on the first look = wait that many seconds and look again, up to that many "
                     "looks in all, before it decides it isn't here and goes on (it may still be spawning or "
                     "walking into view).", t)
        row = ctk.CTkFrame(jc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 10))
        ctk.CTkButton(row, text="Check now", width=100, command=lambda: self._run_test(self.logic.test_hunt_check),
                      **btn).pack(side="left")
        row = ctk.CTkFrame(jc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text="Look in", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkButton(row, text="Set area", width=80, command=lambda: self.pick_region("umbral_jug_area"),
                      **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"}).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Clear", width=56, command=self._clear_jug_area, **btn).pack(side="left")
        self.umbral_jug_area_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12))
        self.umbral_jug_area_lbl.pack(side="left", padx=6)
        self._show_jug_area()
        self._umbral_color_rows(jc, "jug", "Colour 1", "umbral_jug_min",
                                ["5", "10", "15", "30", "60", "120"], 15, "min pixels")
        self._umbral_color_rows(jc, "jug2", "Colour 2", "umbral_jug2_min",
                                ["3", "5", "10", "15", "30"], 5, "min pixels (on colour 1)")
        from logic_umbral_abyss import JUG_NEAR
        row = ctk.CTkFrame(jc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text="Must be close", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(row, text="colour 1 and colour 2 within", font=("Arial", 12)).pack(side="left", padx=(8, 4))
        self._num_combo(row, "umbral_jug_near", ["3", "5", "8", "10", "15", "20"],
                        float(self.settings.get("umbral_jug_near", JUG_NEAR)), minimum=1).pack(side="left")
        ctk.CTkLabel(row, text="px of each other", font=("Arial", 12)).pack(side="left", padx=4)
        row = ctk.CTkFrame(jc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 10))
        ctk.CTkLabel(row, text="Checks", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkLabel(row, text="look", font=("Arial", 12)).pack(side="left", padx=(8, 4))
        self._num_combo(row, "umbral_jug_checks", ["1", "2", "3", "4", "5"],
                        float(self.settings.get("umbral_jug_checks", 2)), minimum=1).pack(side="left")
        ctk.CTkLabel(row, text="times,", font=("Arial", 12)).pack(side="left", padx=4)
        self._num_combo(row, "umbral_jug_check_gap", ["2", "3", "5", "8", "10"],
                        float(self.settings.get("umbral_jug_check_gap", 5)), minimum=0.5).pack(side="left")
        ctk.CTkLabel(row, text="s apart, before 'not here'", font=("Arial", 12)).pack(side="left", padx=4)
        ctk.CTkFrame(jc, fg_color="transparent", height=6).pack()

    def _umbral_spawn_page(self, tab):
        from logic_umbral_abyss import CAM_90_DEFAULT
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        card.pack(fill="x", padx=15, pady=4)
        t = ctk.CTkLabel(card, text="Spawn", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(anchor="w", padx=8, pady=(8, 4))
        help_box(card, "The macro always plays from the 2nd spawn, the one with the purple crystals. If it's at the "
                       "other one it respawns (Esc, R, Enter) until it lands there. Check spawn only looks; "
                       "Go to crystal spawn respawns until it's there.\n"
                       "Crystal area: drag a box over where the crystals show at that spawn (both checks only look "
                       "there). No box = the whole view except the bottom HUD and the chat.\n"
                       "Health bar: capture it once while spawned (drag a tight box, like the OK button) - before every "
                       "check the macro waits until it's back (fully spawned, also after dying), then scrolls down to "
                       "zoom out and looks. Test shows the match; lower Match if it misses the bar, raise it if it "
                       "counts you as spawned too early.", t)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text="Wait after each key (s)", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "umbral_key_wait", ["0.5", "0.75", "1", "1.5", "2"],
                        float(self.settings.get("umbral_key_wait", 1.0)), minimum=0.2).pack(side="left", padx=6)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text="Then press", font=("Arial", 12)).pack(side="left")
        sk = ctk.CTkEntry(row, width=50, font=("Arial", 12))
        sk.insert(0, str(self.settings.get("umbral_spawn_key", "g")))
        sk.pack(side="left", padx=6)
        store_sk = lambda *_: self.settings.set("umbral_spawn_key", sk.get().strip().lower())
        sk.bind("<FocusOut>", store_sk)
        save_while_typing(sk, store_sk)
        ctk.CTkLabel(row, text="once it's at the crystal spawn (empty = nothing)", font=("Arial", 11),
                     text_color="#adb5bd").pack(side="left")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text="Health bar", font=("Arial", 12, "bold")).pack(side="left")
        hb = ctk.CTkButton(row, text="Capture", width=80, command=self._capture_umbral_health,
                           **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"})
        hb.pack(side="left", padx=6)
        self._mark("umbral_health", hb)
        self.umbral_health_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12))
        self.umbral_health_lbl.pack(side="left", padx=4)
        self.umbral_health_preview = ctk.CTkLabel(row, text="")
        self.umbral_health_preview.pack(side="left", padx=6)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        ctk.CTkButton(row, text="Test", width=56, command=lambda: self._run_test(self.logic.test_health_bar),
                      **btn).pack(side="left")
        from logic_umbral_abyss import HEALTH_MATCH
        thr = float(self.settings.get("umbral_health_match", HEALTH_MATCH))
        self.umbral_thr_lbl = ctk.CTkLabel(row, text=f"Match: {int(thr * 100)}%", width=80, font=("Arial", 12))
        self.umbral_thr_lbl.pack(side="right")
        sl = ctk.CTkSlider(row, from_=0.5, to=0.98, number_of_steps=48,
                           command=lambda v: (self.settings.set("umbral_health_match", round(float(v), 2)),
                                              self.umbral_thr_lbl.configure(text=f"Match: {int(float(v) * 100)}%")))
        sl.set(thr)
        sl.pack(side="right", fill="x", expand=True, padx=8)
        self._show_umbral_health()
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text="Camera 90° turn time (s)", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "umbral_cam_90", ["0.6", "0.65", "0.7", "0.75", "0.8", "0.85", "0.9"],
                        float(self.settings.get("umbral_cam_90", CAM_90_DEFAULT)), minimum=0.05).pack(side="left", padx=6)
        ctk.CTkLabel(row, text="(F5 in Roblox turns 360° - it should end where it started)", font=("Arial", 11),
                     text_color="#adb5bd").pack(side="left")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text="Scroll down (notches)", font=("Arial", 12)).pack(side="left")
        self._num_combo(row, "umbral_scroll", ["0", "5", "10", "15", "20", "30"],
                        float(self.settings.get("umbral_scroll", 15))).pack(side="left", padx=6)
        self._umbral_color_rows(card, "crystal", "Crystal colour", "umbral_crystal_min",
                                ["0.3", "0.5", "1", "2", "3"], 0.5, "min % of the view", auto=False)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 4))
        ctk.CTkLabel(row, text="Crystal area", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkButton(row, text="Set area", width=80, command=lambda: self.pick_region("umbral_scan"),
                      **{**btn, "fg_color": "#0d6efd", "hover_color": "#0b5ed7"}).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Clear", width=56, command=self._clear_umbral_area, **btn).pack(side="left")
        self.umbral_area_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12))
        self.umbral_area_lbl.pack(side="left", padx=6)
        self._show_umbral_area()
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 10))
        ctk.CTkButton(row, text="Check spawn", width=110, command=lambda: self._run_test(self.logic.test_spawn_check),
                      **btn).pack(side="left")
        ctk.CTkButton(row, text="Go to crystal spawn", width=150, fg_color="#0d6efd", hover_color="#0b5ed7",
                      height=28, font=("Arial", 12),
                      command=lambda: self._run_test(self.logic.test_go_crystal_spawn)).pack(side="left", padx=6)

    def _refresh_loadouts(self):
        if hasattr(self, "umbral_loadout_menu"):
            self.umbral_loadout_menu.configure(values=list(self.logic.loadouts()))
            self.umbral_loadout_menu.set(self.logic.active_loadout())
        self.refresh_routes()

    def _pick_loadout(self, name):
        self.logic.set_active_loadout(name)
        self.log(f"Loadout '{name}': " + ", ".join(r or "(none)" for r in self.logic.location_routes()))
        self._refresh_loadouts()

    def _new_loadout(self):
        name = self._ask("New loadout", "Name of the new loadout (3 new empty routes are made for it):")
        if name is None:
            return
        made = self.logic.new_loadout(name.strip() or None)
        if not made:
            self.log("That loadout name is empty or already taken.")
            return
        self.log(f"Loadout '{made}' made with routes " + ", ".join(self.logic.location_routes())
                 + ". Stand at the crystal spawn and press Record next to Location 1.")
        self._refresh_loadouts()

    def _rename_loadout(self):
        old = self.logic.active_loadout()
        new = self._ask("Rename loadout", f"New name for '{old}':", old)
        if new and self.logic.rename_loadout(old, new):
            self._refresh_loadouts()

    def _delete_loadout(self):
        from tkinter import messagebox
        name = self.logic.active_loadout()
        if len(self.logic.loadouts()) <= 1:
            self.log("That's the only loadout - make another one first.")
            return
        if messagebox.askyesno("Delete loadout", f"Delete the loadout '{name}'?\nIts routes are kept.",
                               parent=self.root):
            self.logic.delete_loadout(name)
            self._refresh_loadouts()

    def _record_location(self, i):
        """Select this location's route so the record key records into it (makes one if it has none)."""
        route = self.logic.location_routes()[i]
        if not route or route not in self.logic.list_routes() or self.logic.is_locked(route):
            base = f"{self.logic.active_loadout()} {i + 1}"
            route = self.logic.create_route(base) or self.logic.create_route(self.logic.free_route_name(base))
            self.logic.set_location_route(i, route)
        if self.logic.is_recording():
            self.log(f"Already recording - press {self.logic.rec_key()} in Roblox to finish that one first.")
            return
        self.logic.set_active_route(route)
        self.refresh_routes()

        def start():                                     # switch to Roblox, then record straight away
            if not self.logic.wait_focus_for_test():
                return
            self.logic.toggle_recording()
            self.log(f"Location {i + 1}: recording '{route}' - walk there from the crystal spawn, then press "
                     f"{self.logic.rec_key()} to finish.")
        threading.Thread(target=start, daemon=True).start()

    def _show_end_click(self):
        for lbl, p in zip(self.umbral_end_lbls, self.logic.end_spots()):
            lbl.configure(text=f"({p[0]}, {p[1]})" if any(p) else "not set (skipped)",
                          text_color="#75b798" if any(p) else "#adb5bd")

    def _show_umbral_points(self):
        for key, lbl in self.umbral_server_lbls.items():
            p = self.settings.get(key) or [0, 0]
            lbl.configure(text=f"({p[0]}, {p[1]})" if any(p) else "not set", text_color="#75b798" if any(p) else "#ea868f")

    def _pick_umbral_point(self, key):
        self._hide_for_pick()

        def done(x, y):
            self.root.deiconify()
            self.settings.set(key, [int(x), int(y)])
            self._show_umbral_points()
        PointSelector(done)

    def _set_end_click(self, i, pos):
        spots = self.logic.end_spots()
        spots[i] = [int(pos[0]), int(pos[1])]
        self.settings.settings.pop("umbral_end_click", None)          # replaced by the 2-spot list
        self.settings.set("umbral_end_clicks", spots)
        self._show_end_click()

    def _pick_end_click(self, i):
        self._hide_for_pick()

        def done(x, y):
            self.root.deiconify()
            self._set_end_click(i, (x, y))
        PointSelector(done)

    def _show_jug_area(self):
        r = self.settings.get("regions", {}).get("umbral_jug_area") or [0, 0, 0, 0]
        own = r[2] > r[0] and r[3] > r[1]
        self.umbral_jug_area_lbl.configure(text=f"area set ({r[2] - r[0]}x{r[3] - r[1]})" if own else
                                           "no area (play area, not you / HUD)",
                                           text_color="#75b798" if own else "#adb5bd")

    def _clear_jug_area(self):
        self.settings.settings.setdefault("regions", {}).pop("umbral_jug_area", None)
        self.settings.save()
        self._show_jug_area()

    def _umbral_color_rows(self, card, key, label, min_key, min_values, min_default, min_text, auto=True):
        """Pick a colour + tolerance (like Fishing) for the Umbral crystal / Juggernaut check. 'Auto' = the
        built-in check (no colour picked)."""
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text=label, font=("Arial", 12, "bold")).pack(side="left")
        swatch = ctk.CTkFrame(row, width=20, height=20, corner_radius=4)
        swatch.pack(side="left", padx=6)
        lbl = ctk.CTkLabel(row, text="", font=("Arial", 12))
        btn = dict(height=26, font=("Arial", 12))

        def show():
            c = self.settings.get(f"umbral_{key}_color")
            swatch.configure(fg_color="#%02x%02x%02x" % tuple(c[:3]) if c else "#343a40")
            lbl.configure(text=str(list(c[:3])) if c else ("automatic" if auto else "not picked yet"),
                          text_color="#e9ecef" if c else "#adb5bd")

        def picked(color):
            self.root.deiconify()
            self.settings.set(f"umbral_{key}_color", [int(v) for v in color[:3]])
            show()

        def pick():
            self._hide_for_pick()
            ColorPicker(picked)

        def to_auto():
            self.settings.settings.pop(f"umbral_{key}_color", None)
            self.settings.save()
            show()
        pk = ctk.CTkButton(row, text="Pick", width=56, fg_color="#0d6efd", hover_color="#0b5ed7", command=pick, **btn)
        pk.pack(side="left", padx=2)
        self._mark(f"umbral_pick_{key}", pk)
        if auto:
            ctk.CTkButton(row, text="Auto", width=56, fg_color="#495057", hover_color="#343a40", command=to_auto,
                          **btn).pack(side="left", padx=2)
        lbl.pack(side="left", padx=6)
        show()
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        from logic_umbral_abyss import PICK_TOL
        tol = int(float(self.settings.get(f"umbral_{key}_tol", PICK_TOL[key])))
        tol_lbl = ctk.CTkLabel(row, text=f"Tol: {tol}", width=56, font=("Arial", 12))
        sl = ctk.CTkSlider(row, from_=1, to=80, number_of_steps=79, height=16,
                           command=lambda v: (self.settings.set(f"umbral_{key}_tol", int(v)),
                                              tol_lbl.configure(text=f"Tol: {int(v)}")))
        sl.set(tol)
        tol_lbl.pack(side="left")
        sl.pack(side="left", fill="x", expand=True, padx=6)
        self._num_combo(row, min_key, min_values, float(self.settings.get(min_key, min_default)),
                        minimum=0.05).pack(side="left", padx=(6, 2))
        ctk.CTkLabel(row, text=min_text, font=("Arial", 11), text_color="#adb5bd").pack(side="left")

    def setup_areas_tab(self):
        tab = fast_scroll_frame(self.tabview.tab("Areas"))   # scroll, don't squish

        self.gold_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        self.gold_card.pack(fill="x", padx=15, pady=(10, 4))
        self.build_gold_card()

        self.minigame_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        self.minigame_card.pack(fill="x", padx=15, pady=4)
        self.build_minigame_card()

        hc = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        hc.pack(fill="x", padx=15, pady=4)
        row = ctk.CTkFrame(hc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        sw = ctk.CTkSwitch(row, text="Hide chat during the minigame", font=("Arial", 13, "bold"),
                           command=lambda: self.settings.set("hide_chat_in_minigame", bool(sw.get())))
        if self.settings.get("hide_chat_in_minigame"):
            sw.select()
        sw.pack(side="left")
        help_box(hc, "The chat's white Here / Global / Friends tabs look like silver clovers. Pick the chat "
                     "button at the top of Roblox: it's clicked to close chat when a minigame starts and "
                     "again to open it after.", sw)
        row = ctk.CTkFrame(hc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 8))
        ctk.CTkButton(row, text="Pick chat button", width=150, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=lambda: self.pick_point("chat_button")).pack(side="left")
        pos = self.settings.get("regions", {}).get("chat_button", [0, 0])
        self.chat_btn_lbl = ctk.CTkLabel(row, text=f"({pos[0]}, {pos[1]})" if any(pos) else "not set",
                                         font=("Arial", 12), text_color="#75b798" if any(pos) else "#ea868f")
        self.chat_btn_lbl.pack(side="left", padx=8)

        cr = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        cr.pack(fill="x", padx=15, pady=4)
        row = ctk.CTkFrame(cr, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(row, text="Clover Region", width=150, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=lambda: self.pick_region("score")).pack(side="left")
        self.clover_region_lbl = ctk.CTkLabel(cr, text="", font=("Arial", 12), justify="left", wraplength=420)
        self.clover_region_lbl.pack(anchor="w", padx=8, pady=(0, 6))
        self._show_clover_region()
        self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays, font=("Arial", 12))
        self.overlay_switch.pack(pady=10)

    # ---------- Gold clover: automatic from the hotbar, or manual boxes ----------
    def build_gold_card(self):
        gc = self.gold_card
        for w in gc.winfo_children():
            w.destroy()
        mode = self.logic.gold_mode()
        head = ctk.CTkFrame(gc, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 0))
        t = ctk.CTkLabel(head, text="Gold Clover detection", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(side="left")
        help_box(gc, "Drag a SMALL box over the spot where each move's 3rd clover appears." if mode == "manual" else
                     "Auto finds your hotbar by itself (click into Roblox within 3 s). Or drag ONE box over it with "
                     "Set hotbar: from the TOP of the clovers to the bottom of the icons, first icon to last.", t)
        seg = ctk.CTkSegmentedButton(gc, values=["Automatic", "Manual"], font=("Arial", 12, "bold"),
                                     command=lambda v: (self.settings.set("gold_mode", v.lower()), self.build_gold_card()))
        seg.set("Automatic" if mode == "auto" else "Manual")
        seg.pack(fill="x", padx=8, pady=4)
        self.gold_status = {}
        if mode == "manual":
            regions = self.settings.get("regions", {})
            flags = self.logic.train_flags()
            for i in [k + 1 for k, on in enumerate(flags) if on]:
                row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
                ctk.CTkButton(row, text=f"Set Move {i}'s spot", width=150, height=28, fg_color="#0d6efd",
                              hover_color="#0b5ed7", command=lambda idx=i: self.pick_region(f"gold_clover_{idx}")).pack(side="left")
                ok = any(regions.get(f"gold_clover_{i}", [0, 0, 0, 0]))
                lbl = ctk.CTkLabel(row, text="set" if ok else "not set", font=("Arial", 12),
                                   text_color="#75b798" if ok else "#ea868f")
                lbl.pack(side="left", padx=8)
                self.gold_status[i] = lbl
            self._gold_color_rows(gc)
            ctk.CTkLabel(gc, text="", height=4).pack()
            return

        hb = self.settings.settings.setdefault("gold_hotbar", {"region": [0, 0, 0, 0], "slots": 6})
        row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(row, text="Auto", width=62, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=self.auto_gold_hotbar).pack(side="left", padx=(0, 4))
        ctk.CTkButton(row, text="Set hotbar", width=96, height=28, fg_color="#495057", hover_color="#343a40",
                      command=self.pick_gold_hotbar).pack(side="left")
        ok = self.logic.gold_hotbar()[0] is not None
        ctk.CTkLabel(row, text="set" if ok else "not set", font=("Arial", 12),
                     text_color="#75b798" if ok else "#ea868f").pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Slots", font=("Arial", 12)).pack(side="left", padx=(4, 2))
        om = ctk.CTkOptionMenu(row, values=[str(i) for i in range(1, 11)], width=52, height=26,
                               command=lambda v: (hb.__setitem__("slots", int(v)), self.settings.save(), self.build_gold_card()))
        om.set(str(hb.get("slots", 6)))
        om.pack(side="left")
        ctk.CTkButton(row, text="Show", width=56, height=28, fg_color="#495057", hover_color="#343a40",
                      command=self.show_gold_spots).pack(side="right")
        ctk.CTkButton(row, text="Test", width=56, height=28, fg_color="#495057", hover_color="#343a40",
                      command=self.test_gold).pack(side="right", padx=4)
        ctk.CTkLabel(gc, text="Which hotbar slot each move is: Settings → Moves to train → slot.",
                     font=("Arial", 12), text_color="#ced4da").pack(anchor="w", padx=8)
        self.gold_test_lbl = ctk.CTkLabel(gc, text="", font=("Arial", 12), justify="left", wraplength=420, anchor="w")
        self.gold_test_lbl.pack(fill="x", padx=8)
        self._gold_color_rows(gc)
        ctk.CTkLabel(gc, text="", height=4).pack()

    def _gold_color_rows(self, gc):
        """The gold colour (built-in or your own pick) and how strict the match is."""
        own = self.settings.get("gold_color")
        row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text="Gold colour", font=("Arial", 12, "bold")).pack(side="left")
        shown = own or list(self.logic.GOLD_CLOVER_COLOR)
        ctk.CTkFrame(row, width=22, height=22, corner_radius=4, border_width=1, border_color="#adb5bd",
                     fg_color="#%02x%02x%02x" % tuple(int(v) for v in shown[:3])).pack(side="left", padx=6)
        ctk.CTkLabel(row, text=(f"your pick {tuple(own[:3])}" if own else "built-in"), font=("Arial", 12),
                     text_color="#ced4da").pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Pick colour", width=90, height=26, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=self.pick_gold_color).pack(side="left", padx=2)
        if own:
            ctk.CTkButton(row, text="Built-in", width=70, height=26, fg_color="#495057", hover_color="#343a40",
                          command=lambda: (self.settings.set("gold_color", None), self.build_gold_card())).pack(side="left", padx=2)

    def pick_gold_color(self):
        """Click a gold clover on screen to use its exact colour."""
        self._hide_for_pick()

        def done(color):
            self.root.deiconify()
            self.settings.set("gold_color", [int(c) for c in color[:3]])
            self.log(f"Gold colour set to {tuple(color[:3])} - press Test to check a maxed move reads gold.")
            self.build_gold_card()
        ColorPicker(done)

    def auto_gold_hotbar(self):
        """Find the hotbar in the Roblox window you click into, then show the 3rd-clover boxes."""
        self.log("Auto-find: click into the Roblox window now - it looks in 3 s.")

        def run():
            time.sleep(3)
            if self.logic.auto_find_gold_hotbar():
                self.root.after(0, lambda: (self.build_gold_card(), self.show_gold_spots()))
        threading.Thread(target=run, daemon=True).start()

    def pick_gold_hotbar(self):
        self._hide_for_pick()

        def done(x1, y1, x2, y2):
            self.root.deiconify()
            hb = self.settings.settings.setdefault("gold_hotbar", {"slots": 6})
            hb["region"] = [x1, y1, x2, y2]
            hb.pop("spots", None)                        # a dragged box uses the classic spots again
            self.settings.save()
            self.build_gold_card()
            self.log("Hotbar saved. Press Show to check the yellow boxes sit on each 3rd-clover spot.")
        Overlay(done)

    def show_gold_spots(self):
        """Yellow box on the 3rd-clover spot of every slot, for 3 seconds."""
        r, n = self.logic.gold_hotbar()
        if not r:
            self.log("Set the hotbar first."); return
        # solid bright yellow (not see-through): easy to spot on the clovers
        boxes = [PersistentOverlay(*self.logic.third_clover_rect(k), color="#ffff00", alpha=1.0) for k in range(1, n + 1)]
        self.root.after(3000, lambda: [b.destroy() for b in boxes])

    def test_gold(self):
        if not self.logic.gold_hotbar()[0]:
            self.log("Set the hotbar first."); return
        from logic_library import MAX_MOVES
        flags, parts = self.logic.train_flags(), []
        for i in range(MAX_MOVES):
            if not flags[i]:
                continue
            share = self.logic.third_clover_share(self.logic.move_slot(i))
            gold = share is not None and share >= self.logic.GOLD_SHARE
            parts.append(f"{self.logic.move_label(i)} (slot {self.logic.move_slot(i)}): "
                         f"{'GOLD ' if gold else 'not yet'} ({(share or 0):.2f})")
        self.gold_test_lbl.configure(text="\n".join(parts) or "Tick moves to train first (Settings).")

    # ---------- Minigame detector ----------
    def build_minigame_card(self):
        card = self.minigame_card
        for w in card.winfo_children():
            w.destroy()
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 2))
        t = ctk.CTkLabel(head, text="Minigame detector", font=("Arial", 14, "bold"), text_color="#0d6efd")
        t.pack(side="left")
        help_box(card, "During a minigame, press Capture: the screen freezes - drag a box around something that ONLY "
                       "shows in the minigame and never changes while it runs (a title or frame, not a timer or "
                       "score). It needs a 99% match. Walking starts once it's gone.", t)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 4))
        ok = self.logic.has_minigame_snapshot()
        mg = ctk.CTkButton(row, text="Re-capture" if ok else "Capture", width=120, height=28, fg_color="#0d6efd",
                           hover_color="#0b5ed7", command=self.capture_minigame)
        mg.pack(side="left")
        self._mark("lib_minigame", mg)
        ctk.CTkLabel(row, text="captured" if ok else "not captured", font=("Arial", 12),
                     text_color="#75b798" if ok else "#ea868f").pack(side="left", padx=8)
        ctk.CTkButton(row, text="Test", width=56, height=28, fg_color="#495057", hover_color="#343a40",
                      command=self.test_minigame).pack(side="right")
        self.minigame_test_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12, "bold"))
        self.minigame_test_lbl.pack(side="right", padx=8)
        ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

    def capture_minigame(self):
        """Grab the screen NOW (while the minigame is up), then let the user box the marker on that frozen image."""
        import numpy as np, cv2
        from PIL import ImageGrab
        self._hide_for_pick()
        shot = cv2.cvtColor(np.array(ImageGrab.grab().convert("RGB")), cv2.COLOR_RGB2BGR)

        def done(x1, y1, x2, y2):
            ok = self.logic.save_minigame_snapshot(shot[y1:y2, x1:x2].copy(), [x1, y1, x2, y2])
            self.root.deiconify()
            self.log("Minigame marker captured." if ok else "Capture failed — drag a bigger box.")
            self.build_minigame_card()
        Overlay(done)

    def test_minigame(self):
        s = self.logic.minigame_score()
        if s is None:
            self.minigame_test_lbl.configure(text="capture first", text_color="#ea868f")
            return
        on = s >= self.logic.MINIGAME_MATCH
        self.minigame_test_lbl.configure(text=f"{'IN minigame' if on else 'not in minigame'} ({s:.2f})",
                                         text_color="#75b798" if on else "#adb5bd")

    def setup_clover_tab(self):
        tab = self.tabview.tab("Clover Clicker")
        t = ctk.CTkLabel(tab, text="Clover Target Colors & Tolerances", font=("Arial", 16, "bold"), text_color="#0d6efd")
        t.pack(pady=10)
        help_box(tab, "Tol (tolerance) is how far a colour may drift from the picked one.\n"
                      "Lower (1-10): very strict, best for stable lighting. Higher (20-40): allows in-game lighting shifts.\n"
                      "Clicking wrong spots? Lower it. Not clicking the clovers? Raise it.", t)

        self.color_previews, self.color_labels = {}, {}
        self.clover_tol_sliders, self.clover_tol_labels = {}, {}

        colors = self.settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        clover_tols = self.settings.get("clover_tolerances", {})

        for c in ["bronze", "silver", "gold"]:
            card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            card.pack(pady=4, fill="x", padx=15)

            f_color = ctk.CTkFrame(card, fg_color="transparent")
            f_color.pack(pady=(6, 2), fill="x", padx=10)

            ctk.CTkLabel(f_color, text=c.capitalize(), width=60, font=("Arial", 12, "bold"), text_color="#ffffff").pack(side="left", padx=5)

            color = colors.get(c, self.DEFAULT_CLOVER_COLORS[c])
            preview = ctk.CTkFrame(f_color, width=20, height=20, fg_color='#%02x%02x%02x' % tuple(color), corner_radius=4)
            preview.pack(side="left", padx=5)
            self.color_previews[c] = preview

            lbl = ctk.CTkLabel(f_color, text=str(color), font=("Arial", 12), text_color="#e9ecef")
            lbl.pack(side="left", padx=5)
            self.color_labels[c] = lbl

            ctk.CTkButton(f_color, text="Pick", width=50, fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda cl=c: self.pick_color(cl)).pack(side="right", padx=5)

            f_tol = ctk.CTkFrame(card, fg_color="transparent")
            f_tol.pack(pady=(0, 6), fill="x", padx=10)

            ctk.CTkLabel(f_tol, text="Tol:", width=30, font=("Arial", 12), text_color="#e9ecef").pack(side="left", padx=(60, 5))

            tol_val = clover_tols.get(c, self.DEFAULT_CLOVER_TOLERANCES[c])   # same default the clicker uses
            slider = ctk.CTkSlider(f_tol, from_=1, to=100, number_of_steps=99, height=16,
                                  command=lambda val, cl=c: self.update_clover_tolerance(cl, val))
            slider.set(tol_val)
            slider.pack(side="left", fill="x", expand=True, padx=5)
            self.clover_tol_sliders[c] = slider

            val_lbl = ctk.CTkLabel(f_tol, text=str(int(tol_val)), width=35, font=("Arial", 13, "bold"), text_color="#ffffff")
            val_lbl.pack(side="right", padx=5)
            self.clover_tol_labels[c] = val_lbl

        ctk.CTkButton(tab, text="Reset to Defaults", fg_color="#dc3545", hover_color="#bb2d3b", font=("Arial", 12, "bold"), command=self.reset_clover_colors).pack(pady=10)

    def setup_fishing_settings_tab(self):
        tab = self.tabview.tab("Fishing Settings")
        ctk.CTkLabel(tab, text="Minigame Configuration", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(pady=8)

        card1 = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        card1.pack(pady=4, fill="x", padx=20)
        ctk.CTkButton(card1, text="Set Fishing Click Position", fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_point("fishing_click_pos")).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ctk.CTkButton(card1, text="Set Minigame Bar Area", fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_region("minigame_bar")).pack(side="right", fill="x", expand=True, padx=6, pady=6)

        f1 = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        f1.pack(pady=4, fill="x", padx=20)
        ctk.CTkLabel(f1, text="Bar Color:", font=("Arial", 12, "bold")).pack(side="left", padx=8)
        c1 = self.settings.get("bar_color", (0, 255, 0))
        self.bar_preview = ctk.CTkFrame(f1, width=18, height=18, fg_color='#%02x%02x%02x' % tuple(c1), corner_radius=4)
        self.bar_preview.pack(side="left", padx=5)
        self.bar_color_lbl = ctk.CTkLabel(f1, text=str(c1), font=("Arial", 12), text_color="#e9ecef")
        self.bar_color_lbl.pack(side="left")
        ctk.CTkButton(f1, text="Test (F1)", width=55, fg_color="#495057", hover_color="#343a40", command=lambda: self._run_test(self.logic.test_bar_detection)).pack(side="right", padx=6, pady=6)
        ctk.CTkButton(f1, text="Pick", width=50, fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_color("bar_color")).pack(side="right", padx=2, pady=6)

        f2 = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        f2.pack(pady=4, fill="x", padx=20)
        ctk.CTkLabel(f2, text="Fish Color:", font=("Arial", 12, "bold")).pack(side="left", padx=8)
        c2 = self.settings.get("fish_color", (255, 255, 255))
        self.fish_preview = ctk.CTkFrame(f2, width=18, height=18, fg_color='#%02x%02x%02x' % tuple(c2), corner_radius=4)
        self.fish_preview.pack(side="left", padx=5)
        self.fish_color_lbl = ctk.CTkLabel(f2, text=str(c2), font=("Arial", 12), text_color="#e9ecef")
        self.fish_color_lbl.pack(side="left")
        ctk.CTkButton(f2, text="Test (F2)", width=55, fg_color="#495057", hover_color="#343a40", command=lambda: self._run_test(self.logic.test_fish_detection)).pack(side="right", padx=6, pady=6)
        ctk.CTkButton(f2, text="Pick", width=50, fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_color("fish_color")).pack(side="right", padx=2, pady=6)

        ctk.CTkLabel(tab, text="Detection Tolerance (Variance):", font=("Arial", 12, "bold")).pack(pady=(8, 0))
        self.fishing_tolerance_slider = ctk.CTkSlider(tab, from_=1, to=100, number_of_steps=99, command=self.update_tolerance)
        self.fishing_tolerance_slider.set(self.settings.get("color_tolerance", 25)); self.fishing_tolerance_slider.pack(pady=4)
        self.fishing_tolerance_val_label = ctk.CTkLabel(tab, text=f"Value: {int(self.fishing_tolerance_slider.get())}", font=("Arial", 12, "bold"))
        self.fishing_tolerance_val_label.pack()

        self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays, font=("Arial", 12))
        self.overlay_switch.pack(pady=8)

        ctk.CTkButton(tab, text="Reset Fishing Defaults", fg_color="#dc3545", hover_color="#bb2d3b", font=("Arial", 12, "bold"), command=self.reset_fishing_defaults).pack(pady=5)
        ctk.CTkButton(tab, text="Test Full Tracking", fg_color="#0dcaf0", hover_color="#31d2f2", text_color="#000000", font=("Arial", 12, "bold"), command=lambda: self._run_test(self.logic.test_detection)).pack(pady=10)

    def reset_fishing_defaults(self):
        self.settings.set("bar_color", [95, 153, 98])
        self.settings.set("fish_color", [188, 187, 144])
        self.settings.set("color_tolerance", 25)

        self.bar_preview.configure(fg_color='#5f9962')
        self.bar_color_lbl.configure(text="[95, 153, 98]")
        self.fish_preview.configure(fg_color='#bcbb90')
        self.fish_color_lbl.configure(text="[188, 187, 144]")
        if hasattr(self, 'fishing_tolerance_slider'):
            self.fishing_tolerance_slider.set(25)
        if hasattr(self, 'fishing_tolerance_val_label'):
            self.fishing_tolerance_val_label.configure(text="Value: 25")
        self.log("Fishing Defaults Restored")

    # Umbral Abyss Stone: camera turn hotkeys (action, default key, label, degrees; negative = left)
    UMBRAL_TURNS = (("umbral_l90", "f1", "Turn left 90°", -90), ("umbral_l180", "f2", "Turn left 180°", -180),
                    ("umbral_r90", "f3", "Turn right 90°", 90), ("umbral_r180", "f4", "Turn right 180°", 180),
                    ("umbral_360", "f5", "Full 360°", 360))

    def setup_hotkeys_tab(self):
        tab = self.tabview.tab("Hotkeys")
        ctk.CTkLabel(tab, text="Custom Hotkeys", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(pady=10)
        self.hotkey_entries = {}
        hotkeys = self.settings.get("hotkeys")
        actions = ["start"]

        if "Umbral" in self.root.title():
            for a, key, _, _ in self.UMBRAL_TURNS:
                hotkeys.setdefault(a, key)
                actions.append(a)
        elif "Fishing" in self.root.title():
            if hasattr(self.logic, 'test_bar_detection'): actions.append('test_btn')
            if hasattr(self.logic, 'test_fish_detection'): actions.append('test_color')
        else:
            if hasattr(self.logic, 'test_detection'): actions.append('test_btn')
            if hasattr(self.logic, 'test_color_detection'): actions.append('test_color')

        if hasattr(self.logic, 'test_movement'): actions.append('test_movement')
        if hasattr(self.logic, 'test_path') and not hasattr(self.logic, 'test_movement'): actions.append('test_path')
        if hasattr(self.logic, 'test_find_moves'): actions += ['test_find', 'test_full', 'test_open']

        for a in actions:
            f = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            f.pack(pady=3, fill="x", padx=20)
            display_names = {"start": "Start / Stop", "test_btn": "Test Ok Popup", "test_color": "Test Color",
                             "test_movement": "Test Movement"}
            if "Mining" in self.root.title():
                display_names.update({"test_btn": "Test Prompt", "test_movement": "Test Path"})
            elif "Library" in self.root.title():
                display_names.update({"test_btn": "Test Dialogue", "test_path": "Test Path", "test_find": "Find moves (list open)",
                                      "test_full": "Full test (route + moves)",
                                      "test_open": "Test opening (space + E)"})
            display_names.update({a: label for a, _, label, _ in self.UMBRAL_TURNS})
            label_text = display_names.get(a, a.replace("_", " ").capitalize())
            ctk.CTkLabel(f, text=label_text, width=120, font=("Arial", 12, "bold"), anchor="w").pack(side="left", padx=10, pady=6)
            e = ctk.CTkEntry(f, width=80, font=("Arial", 12))
            e.insert(0, hotkeys.get(a, ""))
            e.pack(side="right", padx=10, pady=6)
            e.bind("<FocusOut>", lambda ev, ac=a: self.update_hotkey(ac))
            self.hotkey_entries[a] = e
        if hasattr(self.logic, "toggle_recording"):
            f = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            f.pack(pady=3, fill="x", padx=20)
            ctk.CTkLabel(f, text="Record route", width=120, font=("Arial", 12, "bold"), anchor="w").pack(side="left", padx=10, pady=6)
            e = ctk.CTkEntry(f, width=80, font=("Arial", 12))
            e.insert(0, hotkeys.get("record", "f9"))
            e.pack(side="right", padx=10, pady=6)
            e.bind("<FocusOut>", lambda ev: self.update_hotkey("record"))
            self.hotkey_entries["record"] = e
            ctk.CTkLabel(f, text="start / stop  (e.g. f9, ctrl+p)", font=("Arial", 11),
                         text_color="#adb5bd").pack(side="right", padx=4)
        ctk.CTkButton(tab, text="Apply Hotkeys", font=("Arial", 12, "bold"), fg_color="#0d6efd", hover_color="#0b5ed7", command=self.register_hotkeys).pack(pady=20)

    def register_hotkeys(self):
        keyboard.unhook_all()
        hk = self.settings.get("hotkeys")

        def try_add(key_name, callback):
            try:
                key_val = hk.get(key_name)
                if key_val:
                    keyboard.add_hotkey(key_val, callback)
            except Exception as e:
                self.log(f"Hotkey Error ({key_name}): {e}")

        def press_hotkey(key_name, callback, default=""):
            """A hotkey that fires even while other keys are held (a plain hotkey only fires when it's the only
            key down - so F9 while still holding W never stopped a recording, and F1-F5 while walking were
            recorded as turns but didn't turn the camera). 'ctrl+p' style: the last key, with its modifiers
            checked. One call per press (held-key repeats are ignored)."""
            from utils import on_hotkey
            try:
                on_hotkey(hk.get(key_name) or default, callback)
            except Exception as e:
                self.log(f"Hotkey Error ({key_name}): {e}")

        # F6 starts AND stops. A single key fires even while the macro holds W/A/S/D or an arrow key
        # (a plain hotkey only fires when F6 is the only key down, so it was ignored mid-route).
        start_key = str(hk.get('start') or "").strip()
        if start_key and "+" not in start_key:
            last = [0.0]

            def on_start(_e):
                if time.time() - last[0] > 0.5:          # held key repeats: one toggle per press
                    last[0] = time.time()
                    self.toggle_macro()
            try:
                keyboard.on_press_key(start_key, on_start)
            except Exception as e:
                self.log(f"Hotkey Error (start): {e}")
        else:
            try_add('start', self.toggle_macro)

        if "Umbral" in self.root.title():
            for a, key, _, deg in self.UMBRAL_TURNS:
                hk.setdefault(a, key)
                press_hotkey(a, lambda d=deg: self._run_test(lambda: self.logic.test_turn(d)))
        elif "Fishing" in self.root.title():
            if hasattr(self.logic, 'test_bar_detection'):
                try_add('test_btn', lambda: self._run_test(self.logic.test_bar_detection))
            if hasattr(self.logic, 'test_fish_detection'):
                try_add('test_color', lambda: self._run_test(self.logic.test_fish_detection))
        else:
            if hasattr(self.logic, 'test_detection'):
                try_add('test_btn', lambda: self._run_test(self.logic.test_detection))
            if hasattr(self.logic, 'test_color_detection'):
                try_add('test_color', lambda: self._run_test(self.logic.test_color_detection))
            if hasattr(self.logic, 'test_movement'):
                try_add('test_movement', lambda: self._run_test(self.logic.test_movement))
            elif hasattr(self.logic, 'test_path'):          # Library: its own key so it doesn't share F2 with Test Color
                try_add('test_path', lambda: self._run_test(self.logic.test_path))
        if hasattr(self.logic, 'test_find_moves'):
            try_add('test_find', self.test_find_moves)                        # F4: move list already open
            try_add('test_full', lambda: self.test_find_moves(walk=True))     # F5: route + dialogue + moves
            try_add('test_open', lambda: self._run_test(self.logic.test_open_dialogue))   # F7: space + E opening

        if hasattr(self.logic, "toggle_recording"):
            press_hotkey("record", self.logic.toggle_recording, default="f9")

        self.log("Hotkeys registered")

    def toggle_macro(self):
        """F6 / the Start-Stop button: start when stopped, stop (and reload settings) when running."""
        if self.logic.running:
            self.refresh_macro()
        elif self._is_library and self.logic.dialog_mode() == "auto" and not self._ocr_ok():
            self.log("Not started: text reading doesn't work (Auto mode needs it) - see the popup.")
        else:
            self.root.after(0, self._start_with_check)   # F6 comes from the key hook's thread: build the dialog here
            return
        self.root.after(0, self._sync_start_btn)

    def _start_with_check(self):
        """Start, unless the setup check finds something not ignored: then show it first."""
        if self.logic.running or getattr(self, "_setup_dialog", None) is not None:
            return
        try:
            problems = self.logic.setup_problems()
        except Exception as e:
            print(f"Setup check error: {e}")
            problems = []
        ignored = set(self.settings.get("setup_check_ignored") or [])
        show = [p for p in problems if p["block"] or p["id"] not in ignored]
        if not show:
            self.logic.start()
            self._sync_start_btn()
            return
        for p in show:
            self.log(("Can't start: " if p["block"] else "Setup: ") + p["text"])
        self._setup_dialog_open(show)

    # ----- pointing at a setting: open its tab, scroll to it, make it blink -----
    def _mark(self, name, widget):
        self.__dict__.setdefault("_targets", {})[name] = widget
        return widget

    def _target(self, name):
        w = self.__dict__.get("_targets", {}).get(name)
        try:
            return w if w is not None and w.winfo_exists() else None
        except Exception:
            return None

    def point_to(self, page, name):
        """Show the setting `name` on page `page` (built if it wasn't yet) and make it blink."""
        if page in getattr(self.tabview, "pages", {}):
            self.tabview.set(page)
        self.root.after(200, lambda: self._blink(self._target(name) or getattr(self, name, None)))

    def _blink(self, w):
        if w is None:
            return
        try:
            self.root.update_idletasks()
            p = w.master                                 # scroll its page so it's in view
            while p is not None and not isinstance(p, ctk.CTkScrollableFrame):
                p = getattr(p, "master", None)
            if p is not None:
                y = w.winfo_rooty() - p.winfo_rooty()
                p._parent_canvas.yview_moveto(max(0.0, (y - 80) / max(1, p.winfo_height())))
        except Exception:
            pass
        try:
            orig = (w.cget("border_width"), w.cget("border_color"))
            flip = lambda on: w.configure(border_width=3 if on else orig[0],
                                          border_color="#ffc107" if on else orig[1])
        except Exception:
            try:
                row, orig_bg = w.master, w.master.cget("fg_color")
                flip = lambda on: row.configure(fg_color="#664d03" if on else orig_bg)
            except Exception:
                return
        for k in range(8):                               # 4 blinks over 2 s, ends as it was
            self.root.after(k * 250, lambda on=(k % 2 == 0): self._safe(flip, on))

    @staticmethod
    def _safe(fn, *a):
        try:
            fn(*a)
        except Exception:
            pass

    def _setup_dialog_open(self, show):
        win = ctk.CTkToplevel(self.root)
        self._setup_dialog = win
        win.title("Before starting")
        win.minsize(540, 120)
        win.transient(self.root)
        win.after(150, win.lift)
        blocked = any(p["block"] for p in show)

        def close():
            self._setup_dialog = None
            win.destroy()
        ctk.CTkLabel(win, text="Can't start yet:" if blocked else "Your setup is missing something:",
                     font=("Arial", 14, "bold"), text_color="#ea868f" if blocked else "#ffc107").pack(
            anchor="w", padx=14, pady=(12, 6))
        ticks = {}
        for p in show:
            box = ctk.CTkFrame(win, fg_color="#212529", corner_radius=6); box.pack(fill="x", padx=12, pady=3)
            top = ctk.CTkFrame(box, fg_color="transparent"); top.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkLabel(top, text=("X  " if p["block"] else "!  ") + p.get("short", p["text"]),
                         font=("Arial", 13, "bold"), anchor="w").pack(side="left")
            if p.get("go"):
                ctk.CTkButton(top, text="Go there  →", width=100, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                              command=lambda g=p["go"]: (close(), self.point_to(*g))).pack(side="right")
            if not p["block"]:
                var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(box, text="Don't warn me about this again", variable=var,
                                font=("Arial", 11)).pack(anchor="w", padx=10, pady=(0, 6))
                ticks[p["id"]] = var
            else:
                ctk.CTkFrame(box, fg_color="transparent", height=4).pack()
        row = ctk.CTkFrame(win, fg_color="transparent"); row.pack(fill="x", padx=12, pady=(8, 12))

        def start():
            ign = set(self.settings.get("setup_check_ignored") or [])
            ign |= {k for k, v in ticks.items() if v.get()}
            self.settings.set("setup_check_ignored", sorted(ign))
            close()
            self.logic.start()
            self._sync_start_btn()
        ctk.CTkButton(row, text="Cancel", width=90, fg_color="#495057", hover_color="#343a40",
                      command=close).pack(side="right")
        if not blocked:
            ctk.CTkButton(row, text="Start anyway", width=120, fg_color="#0d6efd", hover_color="#0b5ed7",
                          command=start).pack(side="right", padx=6)
        win.protocol("WM_DELETE_WINDOW", close)

    def _sync_start_btn(self):
        """Keep the button in step with the macro, also when it stops by itself (e.g. all moves trained)."""
        try:
            if not self.start_btn.winfo_exists():
                return
        except Exception:
            return
        running = bool(self.logic.running)
        if not running and getattr(self, "_action_badge", None) is not None:
            from overlay import show_action
            show_action(self, "", False)                 # macro stopped: hide the action bar
        if running != self._shown_running:
            key = self.settings.get("hotkeys", {}).get("start", "f6").upper()
            if running:
                self.start_btn.configure(text=f"■  Stop Macro ({key})", fg_color="#dc3545", hover_color="#bb2d3b")
            else:
                self.start_btn.configure(text=f"▶  Start Macro ({key})", fg_color="#198754", hover_color="#157347")
            self._shown_running = running
        self.root.after(400, self._sync_start_btn)

    def refresh_macro(self):
        # stopping waits for the macro's threads to finish: do it off the window's thread so it never freezes
        def stop():
            self.logic.stop()
            self.root.after(0, lambda: (self.register_hotkeys(), self.log("Macro stopped")))
        threading.Thread(target=stop, daemon=True).start()   # no settings.load(): every page shares the live settings, a reload would detach them

    def _run_test(self, fn):
        import threading
        def wrapper():
            self.logic.test_running = True
            try:
                fn()
            finally:
                # keep the test's last line on the action bar for a few seconds, then hide it
                def done():
                    self.logic.test_running = False
                    if not self.logic.running:
                        from overlay import show_action
                        show_action(self, "", False)
                self.root.after(5000, done)
        threading.Thread(target=wrapper, daemon=True).start()

    def update_hotkey(self, a):
        key = self.hotkey_entries[a].get().lower()
        hk = self.settings.get("hotkeys"); hk[a] = key; self.settings.set("hotkeys", hk); self.register_hotkeys()

    def update_move_name(self, idx):
        names = self.logic.move_names() if hasattr(self.logic, "move_names") else self.settings.get("move_names")
        new_name = self.move_entries[idx].get()
                                                              
        if new_name != names[idx]:
            old = names[idx]
            names[idx] = new_name
            self.settings.set("move_names", names)
            # a different move in this slot: its 'gold used' starts again from 0 (Total keeps counting).
            # Only the letters count, so fixing capitals / spaces doesn't reset it.
            norm = lambda t: "".join(c for c in (t or "").lower() if c.isalnum())
            if norm(old) != norm(new_name) and hasattr(self.logic, "reset_move_gold"):
                self.logic.reset_move_gold(idx)
        self.update_gold_display()

    def update_tolerance(self, val):
        self.settings.set("color_tolerance", int(val))
        if hasattr(self, 'clover_tolerance_val_label'):
            self.clover_tolerance_val_label.configure(text=f"Value: {int(val)}")
        if hasattr(self, 'fishing_tolerance_val_label'):
            self.fishing_tolerance_val_label.configure(text=f"Value: {int(val)}")
        if hasattr(self, 'tundra_tolerance_val_label'):
            self.tundra_tolerance_val_label.configure(text=f"Value: {int(val)}")
        if hasattr(self, 'clover_tolerance_slider'):
            self.clover_tolerance_slider.set(int(val))
        if hasattr(self, 'fishing_tolerance_slider'):
            self.fishing_tolerance_slider.set(int(val))
        if hasattr(self, 'tundra_tolerance_slider'):
            self.tundra_tolerance_slider.set(int(val))

    def update_clover_tolerance(self, color_type, val):
        tols = self.settings.get("clover_tolerances", {})
        tols[color_type] = int(val)
        self.settings.set("clover_tolerances", tols)
        if color_type in self.clover_tol_labels:
            self.clover_tol_labels[color_type].configure(text=str(int(val)))
        self.log(f"{color_type.capitalize()} Tolerance: {int(val)}")

    def log(self, msg, _printed=False, hold=0):
        """hold = keep this message on the action bar at least that many seconds (later ones wait their turn
        on the bar; the console still gets every line right away)."""
        if not _printed:
            print(msg)
        if not hasattr(self, 'status_label'):
            return
        # the macro logs from its own thread; the window may only be touched from the window's thread
        # (touching it from another thread is what made the window freeze)
        if threading.current_thread() is threading.main_thread():
            try:
                self.status_label.configure(text=f"Status: {msg}")
            except Exception:
                pass
            now = time.time()
            if not hold and now < getattr(self, "_bar_hold_until", 0):
                self._bar_pending = msg                  # shown once the held message has had its time
                return
            if hold:
                self._bar_hold_until, self._bar_pending = now + hold, None
                self.root.after(int(hold * 1000) + 50, self._bar_release)
            self._show_on_bar(msg)
        else:
            try:
                self.root.after(0, lambda m=msg: self.log(m, _printed=True, hold=hold))   # already printed above
            except Exception:
                pass

    def _show_on_bar(self, msg):
        try:
            from overlay import show_action
            show_action(self, msg, bool(getattr(self.logic, "running", False)
                                        or getattr(self.logic, "test_running", False)))
        except Exception:
            pass

    def _bar_release(self):
        if time.time() >= getattr(self, "_bar_hold_until", 0) - 0.01:
            msg, self._bar_pending = getattr(self, "_bar_pending", None), None
            if msg:
                self._show_on_bar(msg)

    def _hide_for_pick(self):
        """Hide the macro window and give Windows time to repaint, so the
        picker's screenshot doesn't include this window."""
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)

    def pick_region(self, key):
        self._hide_for_pick()
        Overlay(lambda x1, y1, x2, y2: self.save_region(key, x1, y1, x2, y2))

    def _show_clover_region(self):
        r = self.settings.get("regions", {}).get("score", [0, 0, 0, 0])
        mine = r[2] > r[0] and r[3] > r[1]
        if hasattr(self, "clover_region_lbl"):
            self.clover_region_lbl.configure(
                text=f"YOUR box is used {tuple(r)} - Full Auto Setup switches back to automatic" if mine else
                "automatic: the whole play area between the black bars (Show Scan Areas draws it)",
                text_color="#ffc107" if mine else "#75b798")

    def _show_umbral_health(self):
        ok = self.logic.has_health_bar()
        self.umbral_health_lbl.configure(text="captured" if ok else "not captured",
                                         text_color="#75b798" if ok else "#ea868f")
        try:
            if ok:
                from PIL import Image
                img = Image.open(self.logic.health_path())
                img.thumbnail((140, 30))
                self._umbral_health_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self.umbral_health_preview.configure(image=self._umbral_health_img)
        except Exception:
            pass

    def _show_umbral_menu(self):
        ok = os.path.exists(self.logic.menu_path())
        self.umbral_menu_lbl.configure(text="captured (for Manual)" if ok else "not captured (for Manual)",
                                       text_color="#75b798" if ok else "#adb5bd")

    def _capture_umbral_menu(self):
        self._hide_for_pick()

        def finish(x1, y1, x2, y2):
            ok = self.logic.capture_menu([x1, y1, x2, y2])
            self.root.deiconify()
            self.log("Main menu captured." if ok else "Capture failed - drag a bigger box.")
            self._show_umbral_menu()
        Overlay(lambda x1, y1, x2, y2: self.root.after(150, lambda: finish(x1, y1, x2, y2)))

    def _capture_umbral_health(self):
        self._hide_for_pick()

        def finish(x1, y1, x2, y2):
            ok = self.logic.capture_health_bar([x1, y1, x2, y2])
            self.root.deiconify()
            self.log("Health bar captured." if ok else "Capture failed - drag a bigger box.")
            self._show_umbral_health()
        Overlay(lambda x1, y1, x2, y2: self.root.after(150, lambda: finish(x1, y1, x2, y2)))

    def _show_umbral_area(self):
        r = self.settings.get("regions", {}).get("umbral_scan") or [0, 0, 0, 0]
        own = r[2] > r[0] and r[3] > r[1]
        self.umbral_area_lbl.configure(text=f"area set ({r[2] - r[0]}x{r[3] - r[1]})" if own else
                                       "no area (whole view, no HUD / chat)",
                                       text_color="#75b798" if own else "#adb5bd")

    def _clear_umbral_area(self):
        self.settings.settings.setdefault("regions", {}).pop("umbral_scan", None)
        self.settings.save()
        self._show_umbral_area()

    def _show_interact_area(self):
        r = self.settings.get("regions", {}).get("mining_interact") or [0, 0, 0, 0]
        own = r[2] > r[0] and r[3] > r[1]
        self.interact_area_lbl.configure(text=f"area set ({r[2] - r[0]}x{r[3] - r[1]})" if own else "no area (lower middle)",
                                         text_color="#75b798" if own else "#adb5bd")

    def _clear_interact_area(self):
        self.settings.settings.setdefault("regions", {}).pop("mining_interact", None)
        self.settings.save()
        self._show_interact_area()

    def _test_interact(self):
        def run():
            seen = self.logic.interact_visible()
            self.log("Interact prompt: seen" if seen else "Interact prompt: NOT seen (stand where it shows, or set the area)")
        threading.Thread(target=run, daemon=True).start()

    def save_region(self, key, x1, y1, x2, y2):
        self.root.deiconify(); self.settings.settings["regions"][key] = [x1, y1, x2, y2]; self.settings.save(); self.check_calibration()
        if key == "score":
            self._show_clover_region()
        if key == "mining_interact" and hasattr(self, "interact_area_lbl"):
            self._show_interact_area()
        if key == "umbral_scan" and hasattr(self, "umbral_area_lbl"):
            self._show_umbral_area()
        if key == "umbral_jug_area" and hasattr(self, "umbral_jug_area_lbl"):
            self._show_jug_area()
        if key == "umbral_kill_region" and hasattr(self, "umbral_moves_page"):
            self.umbral_moves_page.show_kill_box()
        if key.startswith("gold_clover_") and getattr(self, "gold_status", {}).get(int(key[-1])):
            self.gold_status[int(key[-1])].configure(text="set", text_color="#75b798")
        if key == "ok_scan_area":
            self.refresh_ok_status()
            if self.ok_area_switch.get() == 1:
                self.toggle_ok_area_overlay()

    def pick_ok_button(self):
        """Drag a box tightly around the OK button while the popup is visible.
        The box becomes both the scan area and the template image."""
        self._hide_for_pick()
        Overlay(lambda x1, y1, x2, y2: self.root.after(300, lambda: self._save_ok_button(x1, y1, x2, y2)))

    def _save_ok_button(self, x1, y1, x2, y2):
        self.settings.settings["regions"]["ok_button"] = [x1, y1, x2, y2]
        self.settings.save()
        ok = self.logic.capture_ok_template([x1, y1, x2, y2])
        self.root.deiconify()
        self.log("OK button captured." if ok else "OK button capture failed — try a larger box.")
        self.refresh_ok_status()

    def pick_point(self, key):
        self._hide_for_pick()
        PointSelector(lambda x, y: self.save_point(key, x, y))

    def save_point(self, key, x, y):
        self.root.deiconify()
        self.settings.settings["regions"][key] = [x, y]
        self.settings.save()
        self.check_calibration()
        if key == "chat_button" and hasattr(self, "chat_btn_lbl"):
            self.chat_btn_lbl.configure(text=f"({x}, {y})", text_color="#75b798")
            self.log("Chat button saved. Make sure chat is OPEN when you start the macro.")
        if key == "ok_click_pos":
            self.log(f"OK click spot set to ({x}, {y}).")
            self.refresh_ok_status()

    def pick_color(self, key):
        self._hide_for_pick()
        ColorPicker(lambda color: self.save_color(key, color))

    def save_color(self, key, color):
        self.root.deiconify()
        hex_color = '#%02x%02x%02x' % tuple(color)
        if key == "bar_color":
            self.settings.set("bar_color", list(color))
            self.bar_preview.configure(fg_color=hex_color)
            self.bar_color_lbl.configure(text=str(list(color)))
        elif key == "fish_color":
            self.settings.set("fish_color", list(color))
            self.fish_preview.configure(fg_color=hex_color)
            self.fish_color_lbl.configure(text=str(list(color)))
        else:
            colors = self.settings.get("clover_colors", {})
            colors[key] = list(color); self.settings.set("clover_colors", colors)
            self.color_previews[key].configure(fg_color=hex_color)
            self.color_labels[key].configure(text=str(list(color)))

    def reset_clover_colors(self):
        default_colors = {k: list(v) for k, v in self.DEFAULT_CLOVER_COLORS.items()}
        default_tols = dict(self.DEFAULT_CLOVER_TOLERANCES)
        self.settings.set("clover_colors", default_colors)
        self.settings.set("clover_tolerances", default_tols)
        self.settings.set("color_tolerance", 25)

        for c in ["bronze", "silver", "gold"]:
            color = list(self.DEFAULT_CLOVER_COLORS[c])
            hex_color = '#%02x%02x%02x' % tuple(color)
            if c in self.color_previews:
                self.color_previews[c].configure(fg_color=hex_color)
            if c in self.color_labels:
                self.color_labels[c].configure(text=str(color))
            if c in self.clover_tol_sliders:
                self.clover_tol_sliders[c].set(default_tols[c])
            if c in self.clover_tol_labels:
                self.clover_tol_labels[c].configure(text=str(default_tols[c]))

        if hasattr(self, 'clover_tolerance_slider'):
            self.clover_tolerance_slider.set(25)
        if hasattr(self, 'clover_tolerance_val_label'):
            self.clover_tolerance_val_label.configure(text="Value: 25")
        if hasattr(self, 'fishing_tolerance_slider'):
            self.fishing_tolerance_slider.set(25)
        if hasattr(self, 'fishing_tolerance_val_label'):
            self.fishing_tolerance_val_label.configure(text="Value: 25")

        self.log("Clover Defaults Restored")

    def exit_app(self):
        self.logic.stop(); self.root.destroy(); os._exit(0)

    def setup_statistics_tab(self):
        tab = self.tabview.tab("Statistics")
        ctk.CTkLabel(tab, text="Training Statistics", font=("Arial", 18, "bold"), text_color="#0d6efd").pack(pady=(15, 10))

        card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        card.pack(fill="x", padx=20, pady=10)
        self.gold_label = self._stat_row(card, "Total Gold Used", ("Arial", 15, "bold"), "#ffc107",
                                         lambda: self.reset_stat(None))

        stats_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        stats_card.pack(fill="x", padx=20, pady=5)
        self.move_stats_labels = [self._stat_row(stats_card, "", ("Arial", 13), "#ffffff",
                                                 lambda i=i: self.reset_stat(i))
                                  for i in range(len(self._move_stats()[0]))]
        self.update_gold_display()

        ctk.CTkButton(tab, text="Reset All", fg_color="#dc3545", hover_color="#bb2d3b", font=("Arial", 12, "bold"),
                      command=self.reset_gold).pack(pady=20)

    def _stat_row(self, parent, name, font, color, on_reset):
        """One statistic: name and value on the left, its own Reset on the right. Returns the value label."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkButton(row, text="Reset", width=60, height=24, font=("Arial", 11), fg_color="#495057",
                      hover_color="#bb2d3b", command=on_reset).pack(side="right")
        lbl = ctk.CTkLabel(row, text=name, font=font, text_color=color, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        return lbl

    def _move_stats(self):
        nine = getattr(self.logic, "_nine", None)
        if nine:
            return nine("move_names", ""), nine("move_stats", 0)
        return self.settings.get("move_names", ["", "", ""]), self.settings.get("move_stats", [0, 0, 0])

    def update_gold_display(self):
        if not hasattr(self, 'gold_label'):
            return
        self.gold_label.configure(text=f"Total Gold Used: {self.settings.get('total_gold', 0)}")
        names, stats = self._move_stats()
        for i, lbl in enumerate(getattr(self, "move_stats_labels", [])[:len(names)]):
            lbl.configure(text=f"{names[i] or f'Move {i + 1}'}: {stats[i]}")

    def reset_stat(self, i):
        """Reset one number: the total gold (i = None) or one move's."""
        if i is None:
            self.settings.set("total_gold", 0)
            self.log("Total gold reset")
        else:
            names, stats = self._move_stats()
            stats[i] = 0
            self.settings.set("move_stats", stats)
            self.log(f"{names[i] or f'Move {i + 1}'} statistic reset")
        self.update_gold_display()

    def reset_gold(self):
        self.settings.set("total_gold", 0)
        self.settings.set("move_stats", [0] * len(self.settings.get("move_stats") or [0, 0, 0]))
        self.log("Statistics Reset")
        self.update_gold_display()

    def toggle_overlays(self):
        if self.overlay_switch.get() == 1: self.show_overlays()
        else: self.hide_overlays()

    def show_overlays(self):
        self.hide_overlays()
        regions = self.settings.get("regions")
        
        if "Fishing" in self.root.title():
            relevant_keys = ["minigame_bar"]
        elif "Mining" in self.root.title():
            relevant_keys = []
        else:                  
            relevant_keys = ["score", "gold_clover_1", "gold_clover_2", "gold_clover_3", "minigame_marker"]

        colors = ["red", "green", "blue", "yellow", "cyan", "magenta"]
        for i, key in enumerate(relevant_keys):
            rect = regions.get(key)
            if key == "score" and not (rect and any(v != 0 for v in rect)) and hasattr(self.logic, "auto_clover_region"):
                # automatic Clover Region: the last one found in a minigame, or between the bars on screen now
                rect = self.logic.play_area()
            if rect and any(v != 0 for v in rect):
                self.overlays[key] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color=colors[i % len(colors)])

    def toggle_ok_area_overlay(self):
        old = self.overlays.pop("_ok_area", None)
        if old: old.destroy()
        if self.ok_area_switch.get() != 1:
            return
        rect = self.logic.get_ok_search_region()
        if rect and not any(v != 0 for v in self.settings.get("regions", {}).get("ok_scan_area", [0, 0, 0, 0])):
            self.log("No Scan Area set: the whole screen is scanned (nothing to draw).")
            self.ok_area_switch.deselect()
        elif rect:
            self.overlays["_ok_area"] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color="orange")
        else:
            self.log("No OK scan area yet — set one or capture the OK button first.")
            self.ok_area_switch.deselect()

    def hide_overlays(self):
        for k in [k for k in self.overlays if k != "_ok_area"]:
            self.overlays.pop(k).destroy()

class OkPopupPage(SpatialGUI):
    """Just the shared OK Popup page, for windows that aren't a SpatialGUI (the Skill Macro).
    It reuses every OK method above, with its own small OK-only logic, so the setup stays shared."""

    def __init__(self, root, frame, settings, log):
        from gui_events import EventsOnlyLogic
        self.root = root
        self.settings = settings
        self._log_fn = log
        self.overlays = {}
        self.tabs_to_show = []                       # no Main page -> the Always Click OK toggle sits on this page
        self.tabview = type("OnePage", (), {"tab": staticmethod(lambda name: frame)})()
        self.logic = EventsOnlyLogic(self)
        self.setup_ok_tab()

    def log(self, msg):
        self._log_fn(msg)

    def close(self):
        """Stop the background OK clicker when leaving the Skill Macro."""
        try:
            self.logic.stop_global_ok_scanner()
        except Exception:
            pass
