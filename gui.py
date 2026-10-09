import customtkinter as ctk
import tkinter as tk
from settings import SpatialSettings
from overlay import Overlay, PointSelector, ColorPicker, PersistentOverlay
from updater import SpatialUpdater
from logic_library import LibraryLogic
from logic_mining import MiningLogic
from logic_fishing import FishingLogic
from logic_devil_union import DevilUnionLogic
import keyboard
from ui_style import big_toggle, style_toggle
import os
import sys
import webbrowser
import time

class MacroSelector:
    def __init__(self, root, on_select, current_version):
        self.root = root
        self.on_select = on_select
        self.current_version = current_version
        self.root.title("VunVun's Macro Hub")
        self.root.geometry("1300x550")
        
        self.updater = SpatialUpdater(current_version, "Vunoxoulia", "Clover-Retribution-Macro-App")
        self.setup_ui()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        
        title = ctk.CTkLabel(self.root, text="Select a Macro", font=("Arial", 32, "bold"), text_color="#0d6efd")
        title.pack(pady=(35, 5))
        
        version_lbl = ctk.CTkLabel(self.root, text=f"v{self.current_version}", font=("Arial", 12, "bold"), text_color="#e9ecef")
        version_lbl.pack()

        self.cards_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.cards_frame.pack(expand=True, fill="both", padx=20, pady=20)

        self.create_card("Library Macro", "Auto spell clover mastery.", "Launch", 
                         lambda: self.on_select("Library Macro", LibraryLogic, 
                                                tabs=["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"],
                                                tutorial_url="https://youtu.be/4xNxNFktF5o"), 0)

        self.create_card("Mining Macro", "Mining away.", "Launch",
                         lambda: self.on_select("Mining Macro", MiningLogic,
                                                tabs=["Main", "Settings", "Hotkeys"],
                                                tutorial_url="https://youtu.be/mD85aJdDbfE"), 1)

        self.create_card("Fishing Macro", "Auto Fishy.", "Launch",
                         lambda: self.on_select("Fishing Macro", FishingLogic,
                                                tabs=["Main", "Fishing Settings", "Hotkeys"],
                                                tutorial_url="https://youtu.be/a_4odPOc3e4"), 2)

        self.create_card("Skill Macro", "AFK skill rotation, skill\ncombos and auto item use.", "Launch",
                         self.launch_smart, 3)

        self.create_card("Event Notifier", "Posts server events from\nchat to Discord.", "Launch",
                         self.launch_events, 4)

        self.create_card("Devil Union", "Automated training for\nDevil Union progression.", "Coming Soon", None, 5)

        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=10, padx=20)
        
        update_btn = ctk.CTkButton(footer, text="Check for Updates", width=150, fg_color="#0d6efd", hover_color="#0b5ed7", command=self.check_updates)
        update_btn.pack(side="left", padx=(0, 10))

        patch_notes_btn = ctk.CTkButton(footer, text="Patch Notes", width=120, command=self.show_patch_notes, fg_color="#495057", hover_color="#343a40")
        patch_notes_btn.pack(side="left")

        links_frame = ctk.CTkFrame(footer, fg_color="transparent")
        links_frame.pack(side="right")

        link_btn = dict(height=32, width=118, corner_radius=16, font=("Arial", 13, "bold"))
        ctk.CTkButton(links_frame, text="▶  YouTube", fg_color="#c4302b", hover_color="#9e2622", **link_btn,
                      command=lambda: webbrowser.open("https://www.youtube.com/@Vunoxoulia")).pack(side="left", padx=4)
        ctk.CTkButton(links_frame, text="💬  Discord", fg_color="#5865F2", hover_color="#4752c4", **link_btn,
                      command=lambda: webbrowser.open("https://discord.com/invite/VRMB4djfzp")).pack(side="left", padx=4)

        # Donate: pick Robux (Roblox group store) or real money (Ko-fi)
        donate_menu = tk.Menu(self.root, tearoff=0, bg="#212529", fg="#e9ecef", activebackground="#0d6efd",
                              activeforeground="#ffffff", font=("Arial", 12))
        donate_menu.add_command(label="  Robux  (Roblox store)", command=lambda: webbrowser.open(
            "https://www.roblox.com/communities/34022778/The-Manga-Corner#!/store"))
        donate_menu.add_command(label="  Real money  (Ko-fi)", command=lambda: webbrowser.open(
            "https://ko-fi.com/vunoxoulia"))
        donate_btn = ctk.CTkButton(links_frame, text="♥  Donate  ▾", fg_color="#ffc107", hover_color="#e0a800",
                                   text_color="#212529", **link_btn)
        donate_btn.configure(command=lambda: donate_menu.tk_popup(donate_btn.winfo_rootx(),
                                                                  donate_btn.winfo_rooty() + donate_btn.winfo_height()))
        donate_btn.pack(side="left", padx=4)

        self.setup_layout_picker()

    def setup_layout_picker(self):
        """Keyboard layout: the macros press keys by their QWERTY position (that's how Roblox reads them)."""
        from utils import LAYOUTS, set_layout, detect_layout
        settings = SpatialSettings()
        row = ctk.CTkFrame(self.root, fg_color="#2b2f33", corner_radius=10)
        row.pack(side="bottom", pady=(0, 18))
        ctk.CTkLabel(row, text="⌨  Keyboard layout", font=("Arial", 14, "bold")).pack(side="left", padx=(16, 10), pady=10)
        hint = ctk.CTkLabel(row, text="", font=("Arial", 12), text_color="#adb5bd")

        def show_hint(choice):
            if choice == "Auto":
                hint.configure(text=f"detected: {detect_layout()}")
            elif choice == "QWERTY":
                hint.configure(text="keys sent as typed")
            else:
                hint.configure(text="keys sent by position (WASD = ZQSD on AZERTY)")

        def pick(choice):
            settings.set("keyboard_layout", choice)
            set_layout(choice)
            show_hint(choice)

        current = settings.get("keyboard_layout", "Auto")
        seg = ctk.CTkSegmentedButton(row, values=LAYOUTS, command=pick, font=("Arial", 13, "bold"), height=32)
        seg.set(current if current in LAYOUTS else "Auto")
        seg.pack(side="left", padx=4, pady=10)
        hint.pack(side="left", padx=(10, 16))
        set_layout(seg.get())
        show_hint(seg.get())

    def launch_events(self):
        from gui_events import EventsOnlyLogic
        self.on_select("Event Notifier", EventsOnlyLogic, tabs=["Events"])

    def launch_smart(self):
        from gui_smart import SmartMacroGUI  # lazy: gui_smart imports from this module
        self.on_select("Skill Macro", None, gui_class=SmartMacroGUI)

    def show_patch_notes(self):
        import requests
        from tkinter import messagebox
        notes_url = f"https://raw.githubusercontent.com/Vunoxoulia/Clover-Retribution-Macro-App/main/PATCH_NOTES.txt"
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

    def create_card(self, title, description, button_text, command, column):
        card = ctk.CTkFrame(self.cards_frame, width=195, height=290, corner_radius=12, fg_color="#212529", border_color="#343a40", border_width=1)
        card.grid(row=0, column=column, padx=12, pady=10, sticky="nsew")
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=title, font=("Arial", 18, "bold"), text_color="#ffffff").pack(pady=(20, 8))
        ctk.CTkLabel(card, text=description, font=("Arial", 13), text_color="#e9ecef", justify="center").pack(pady=8, padx=10)
        btn = ctk.CTkButton(card, text=button_text, command=command, font=("Arial", 13, "bold"), fg_color="#0d6efd", hover_color="#0b5ed7")
        if command is None:
            btn.configure(state="disabled", fg_color="#343a40", text_color="#ced4da")
        btn.pack(side="bottom", pady=20)
        self.cards_frame.grid_columnconfigure(column, weight=1)

NAV_ICONS = {
    "Main": "🏠", "Settings": "⚙", "Areas": "🔲", "Clover Clicker": "🍀",
    "Fishing Settings": "🎣", "OK Popup": "🔔", "Events": "📣", "Hotkeys": "⌨", "Statistics": "📊",
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

    def add(self, name):
        page = ctk.CTkFrame(self.content, fg_color="#1e2124", corner_radius=10)
        btn = ctk.CTkButton(self.nav_frame, text=f"{NAV_ICONS.get(name, '•')}  {name}", anchor="w",
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

    def get(self):
        return self.current

class SpatialGUI:
    def __init__(self, root, title="Spatial Macro", logic_class=LibraryLogic, on_back=None, tabs=None, tutorial_url="#"):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        self.root.geometry("720x720" if "Mining" in title else "650x700")
        self.tutorial_url = tutorial_url
        self.settings = SpatialSettings()
        self.logic = logic_class(self)
        self.overlays = {} 
        self.tabs_to_show = list(tabs) if tabs else ["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"]
        # Shared OK popup setup page: every macro gets it, placed before Hotkeys
        if "OK Popup" not in self.tabs_to_show:
            idx = self.tabs_to_show.index("Hotkeys") if "Hotkeys" in self.tabs_to_show else len(self.tabs_to_show)
            self.tabs_to_show.insert(idx, "OK Popup")
        # Shared Event Notifier page: every macro gets it too (runs alongside the macro)
        if "Events" not in self.tabs_to_show:
            self.tabs_to_show.insert(self.tabs_to_show.index("OK Popup") + 1, "Events")
        self.DEFAULT_CLOVER_COLORS = {"gold": (255, 180, 51), "silver": (164, 178, 178), "bronze": (198, 62, 37)}
        self.DEFAULT_CLOVER_TOLERANCES = {"gold": 20, "silver": 20, "bronze": 20}
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
        if "Main" in self.tabs_to_show: self.setup_main_tab()
        if "Settings" in self.tabs_to_show: self.setup_settings_tab()
        if "Areas" in self.tabs_to_show: self.setup_areas_tab()
        if "Clover Clicker" in self.tabs_to_show: self.setup_clover_tab()
        if "Fishing Settings" in self.tabs_to_show: self.setup_fishing_settings_tab()
        if "OK Popup" in self.tabs_to_show: self.setup_ok_tab()
        if "Events" in self.tabs_to_show: self.setup_events_tab()
        if "Hotkeys" in self.tabs_to_show: self.setup_hotkeys_tab()
        if "Statistics" in self.tabs_to_show: self.setup_statistics_tab()

    def setup_main_tab(self):
        tab = self.tabview.tab("Main")
        ctk.CTkLabel(tab, text=self.root.title().upper(), font=("Arial", 22, "bold"), text_color="#0d6efd").pack(pady=(12, 6))
        self.help_btn = ctk.CTkButton(tab, text="❓ How to Setup", width=130, height=26, font=("Arial", 12, "bold"), fg_color="#0dcaf0", hover_color="#31d2f2", text_color="#000000", command=self.show_quick_start)
        self.help_btn.pack(pady=4)

        self.calib_frame = ctk.CTkFrame(tab, fg_color="#842029", border_color="#f5c2c7", border_width=1, corner_radius=8)
        self.calib_label = ctk.CTkLabel(self.calib_frame, text="⚠️ UNCALIBRATED SETTINGS DETECTED\nPlease go to Settings tabs to set up.", font=("Arial", 12, "bold"), text_color="#ea868f")
        self.calib_label.pack(padx=12, pady=8)
        self.check_calibration()

        status_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        status_card.pack(fill="x", padx=20, pady=15)
        self.status_label = ctk.CTkLabel(status_card, text="Status: <Not Started>", font=("Arial", 13, "bold"), text_color="#f8f9fa")
        self.status_label.pack(pady=12, padx=10)

        hk = self.settings.get("hotkeys")
        main_btn = dict(height=40, corner_radius=8, font=("Arial", 13, "bold"))      # same size as the big toggles
        # One Start/Stop toggle on one key (F6), like the Skill Macro
        self.start_btn = ctk.CTkButton(tab, text="", command=self.toggle_macro, **main_btn)
        self.start_btn.pack(pady=(6, 4), fill="x", padx=40)
        self._shown_running = None
        self._sync_start_btn()

        # Always-Click-OK toggle — works even when the macro is stopped or paused
        self._always_ok_on = False
        self.always_ok_btn = big_toggle(tab, self.toggle_always_ok)
        self._ok_toggles = [self.always_ok_btn]
        style_toggle(self.always_ok_btn, False, "Always Click OK")
        self.always_ok_btn.pack(pady=4, fill="x", padx=40)
        ok_hint = ctk.CTkLabel(tab, text="Set up OK detection in the 🔔 OK Popup page", font=("Arial", 12),
                               text_color="#ced4da", cursor="hand2")
        ok_hint.pack(pady=(0, 8))
        ok_hint.bind("<Button-1>", lambda e: self.tabview.set("OK Popup"))

        tutorial_link = ctk.CTkLabel(tab, text="Video Tutorial", font=("Arial", 14, "underline"), text_color="#0dcaf0", cursor="hand2")
        tutorial_link.pack(side="bottom", pady=10)
        tutorial_link.bind("<Button-1>", lambda e: webbrowser.open(self.tutorial_url))

    # ================= Mining (recorded routes) =================
    def setup_mining_settings(self, tab):
        card = lambda: ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")

        self._route_card(tab, "Test Prompt (F1)", self.logic.test_detection,
                         "Test Path (F2)", self.logic.test_movement,
                         "Recording: stand at the start, press Ctrl+P, walk the loop, TAP E once at each ore, "
                         "pause ~0.5s at corners (checkpoints), press Ctrl+P again back at the start.")

        # Movement / alignment
        mc = card(); mc.pack(fill="x", padx=15, pady=4)
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(6, 2))
        self.smart_switch = ctk.CTkSwitch(row, text="🧠 Smart Movement (lag-aware)", font=("Arial", 12, "bold"),
                                          command=lambda: self.settings.set("smart_movement", bool(self.smart_switch.get())))
        if self.settings.get("smart_movement", True): self.smart_switch.select()
        self.smart_switch.pack(side="left")
        ctk.CTkButton(row, text="Test Sensor", width=90, command=lambda: self._run_test(self.logic.test_motion_sensor),
                      **btn).pack(side="right")
        ctk.CTkButton(row, text="Test Start Spot", width=110, command=lambda: self._run_test(self.logic.test_home),
                      **btn).pack(side="right", padx=4)
        row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(2, 6))

        def slider(parent, label, key, default, lo, hi, steps, fmt):
            ctk.CTkLabel(parent, text=label, font=("Arial", 12)).pack(side="left")
            val = ctk.CTkLabel(parent, text=fmt(self.settings.get(key, default)), width=44, font=("Arial", 12, "bold"))
            def on(v):
                v = round(float(v), 1) if isinstance(default, float) else int(v)
                self.settings.set(key, v); val.configure(text=fmt(v))
            sl = ctk.CTkSlider(parent, from_=lo, to=hi, number_of_steps=steps, width=95, command=on)
            sl.set(self.settings.get(key, default)); sl.pack(side="left", padx=3); val.pack(side="left", padx=(0, 10))

        slider(row, "Tolerance:", "home_tolerance", 30, 5, 80, 15, lambda v: f"{int(v)}px")
        slider(row, "Motion:", "motion_threshold", 2.5, 0.5, 10, 95, lambda v: f"{float(v):.1f}")

        # Recorded path per ore
        head = ctk.CTkFrame(tab, fg_color="transparent"); head.pack(fill="x", padx=15, pady=(6, 0))
        ctk.CTkLabel(head, text="⛏️ Recorded Path", font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkLabel(tab, text="Each ore shows the keys you held to walk there (edit the hold time if you need to) "
                               "and how long to mine.", font=("Arial", 12), text_color="#ced4da",
                     justify="left", wraplength=460).pack(fill="x", padx=15, pady=(0, 4))
        self.route_panel = ctk.CTkScrollableFrame(tab, fg_color="#1a1d20", corner_radius=8)
        self.route_panel.pack(fill="both", expand=True, padx=15, pady=(0, 8))
        self.route_expanded = {}
        self.refresh_routes()

    def _route_card(self, tab, test1_text, test1_fn, test2_text, test2_fn, tip):
        btn = dict(height=28, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")
        rc = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        rc.pack(fill="x", padx=15, pady=(8, 4))
        row = ctk.CTkFrame(rc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(6, 2))
        ctk.CTkLabel(row, text="🗺 Route:", font=("Arial", 13, "bold")).pack(side="left", padx=(0, 6))
        self.route_menu = ctk.CTkOptionMenu(row, values=["(none)"], width=170, command=self._select_route)
        self.route_menu.pack(side="left")
        ctk.CTkButton(row, text="New", width=50, command=self._new_route, **btn).pack(side="left", padx=(6, 2))
        ctk.CTkButton(row, text="Rename", width=64, command=self._rename_route, **btn).pack(side="left", padx=2)
        ctk.CTkButton(row, text="Delete", width=56, command=self._delete_route,
                      **{**btn, "hover_color": "#bb2d3b"}).pack(side="left", padx=2)
        row = ctk.CTkFrame(rc, fg_color="transparent"); row.pack(fill="x", padx=6, pady=(2, 6))
        self.rec_label = ctk.CTkLabel(row, text="", font=("Arial", 12, "bold"))
        self.rec_label.pack(side="left")
        ctk.CTkButton(row, text=test2_text, width=110, command=lambda: self._run_test(test2_fn), **btn).pack(side="right")
        ctk.CTkButton(row, text=test1_text, width=120, command=lambda: self._run_test(test1_fn), **btn).pack(side="right", padx=4)
        ctk.CTkLabel(rc, text=tip, font=("Arial", 12), text_color="#ced4da", justify="left",
                     wraplength=410).pack(fill="x", padx=8, pady=(0, 6))

    # ================= Library =================
    def setup_library_settings(self, tab):
        self._route_card(tab, "Test Dialogue (F1)", self.logic.test_detection,
                         "Test Path (F3)", self.logic.test_path,
                         "At the desk: Ctrl+P → walk to the wisp → tap E → Ctrl+P.  (❓ How to Setup on Main explains it.)")
        mc = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        mc.pack(fill="x", padx=15, pady=4)
        ctk.CTkLabel(mc, text="✨ Moves to train", font=("Arial", 13, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkLabel(mc, text="Type each move's name exactly as on the wisp's button: it's found by name (scrolling "
                              "the list if needed). Slot = where it sits on your hotbar (for the gold clover check).",
                     font=("Arial", 12), text_color="#ced4da",
                     justify="left", wraplength=410).pack(fill="x", padx=8, pady=(0, 4))
        from logic_library import MAX_MOVES
        flags = self.logic.train_flags()
        names = self.logic.move_names()
        slots = self.logic._nine("gold_move_slots", lambda k: k + 1)
        self.train_vars, self.move_entries = [], []
        for i in range(MAX_MOVES):
            row = ctk.CTkFrame(mc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            var = ctk.BooleanVar(value=flags[i])
            ctk.CTkCheckBox(row, text=f"Move {i + 1}", variable=var, width=90, font=("Arial", 12, "bold"),
                            command=self._save_train_flags).pack(side="left")
            sel = ctk.CTkOptionMenu(row, values=[str(k) for k in range(1, MAX_MOVES + 1)], width=58, height=26,
                                    command=lambda v, idx=i: (slots.__setitem__(idx, int(v)), self.settings.save()))
            sel.set(str(slots[i]))
            sel.pack(side="right")
            ctk.CTkLabel(row, text="slot", font=("Arial", 12)).pack(side="right", padx=(6, 3))
            e = ctk.CTkEntry(row, placeholder_text="name on the wisp's button", font=("Arial", 12))
            if names[i]: e.insert(0, names[i])
            e.pack(side="left", fill="x", expand=True, padx=(4, 0))
            e.bind("<FocusOut>", lambda ev, idx=i: self.update_move_name(idx))
            self.train_vars.append(var); self.move_entries.append(e)
        ctk.CTkLabel(mc, text="", height=4).pack()
        self.dialog_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        self.dialog_card.pack(fill="x", padx=15, pady=4)
        self.build_dialog_card()
        self.refresh_routes()

    # ---------- Wisp dialogue: Auto / Image / Manual ----------
    DIALOG_HINTS = {
        "auto": "Finds the buttons by their shape and clicks by position. Works in any language — try this first.",
        "image": "With the dialogue open, drag a box around each button once. The macro clicks wherever that picture shows up.",
        "manual": "Click the exact spot of each button. Use it if Auto/Image miss. Don't move or resize Roblox afterwards.",
    }

    def build_dialog_card(self):
        from logic_library import DIALOG_BUTTONS
        card = self.dialog_card
        for w in card.winfo_children():
            w.destroy()
        mode = self.logic.dialog_mode()
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(head, text="💬 Wisp dialogue", font=("Arial", 13, "bold")).pack(side="left")
        ctk.CTkButton(head, text="? Help", width=60, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#0dcaf0",
                      command=lambda: self.open_library_guide("Dialogue")).pack(side="right")
        ctk.CTkButton(head, text="↕ Test scroll", width=100, height=24, font=("Arial", 11, "bold"), fg_color="#495057",
                      hover_color="#343a40", command=lambda: self._run_test(self.logic.test_scroll)).pack(side="right", padx=6)
        seg = ctk.CTkSegmentedButton(card, values=["Auto", "Image", "Manual"], font=("Arial", 12, "bold"),
                                     command=lambda v: (self.settings.set("dialog_mode", v.lower()), self.build_dialog_card()))
        seg.set(mode.capitalize())
        seg.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(card, text=self.DIALOG_HINTS[mode], font=("Arial", 12), text_color="#ced4da",
                     justify="left", wraplength=410).pack(fill="x", padx=8, pady=(2, 4))
        if mode == "auto":
            ctk.CTkLabel(card, text="", height=2).pack()
            return
        flags = self.logic.train_flags()
        for key, label in DIALOG_BUTTONS.items():
            if key.startswith("move_") and not flags[int(key[-1]) - 1]:
                continue                                    # only the moves being trained
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            text = label if key == "clover_training" else self.logic.move_label(int(key[-1]) - 1)
            ctk.CTkLabel(row, text=text, width=150, anchor="w", font=("Arial", 12, "bold")).pack(side="left")
            if mode == "image":
                ok = self.logic.has_dialog_template(key)
                ctk.CTkButton(row, text="📸 Capture" if not ok else "📸 Re-capture", width=110, height=26,
                              fg_color="#0d6efd", hover_color="#0b5ed7",
                              command=lambda k=key: self.capture_dialog_button(k)).pack(side="left", padx=4)
                ctk.CTkLabel(row, text="✔ captured" if ok else "not captured", font=("Arial", 12),
                             text_color="#75b798" if ok else "#ea868f").pack(side="left", padx=6)
            else:
                pt = self.logic.manual_point(key)
                ctk.CTkButton(row, text="🎯 Pick spot", width=110, height=26, fg_color="#0d6efd", hover_color="#0b5ed7",
                              command=lambda k=key: self.pick_dialog_point(k)).pack(side="left", padx=4)
                ctk.CTkLabel(row, text=f"({pt[0]}, {pt[1]})" if pt else "not set", font=("Arial", 12),
                             text_color="#75b798" if pt else "#ea868f").pack(side="left", padx=6)
        if mode == "manual":
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 2))
            ctk.CTkLabel(row, text="Wait before each click (s)", font=("Arial", 12)).pack(side="left")
            om = ctk.CTkOptionMenu(row, values=["1", "1.5", "2", "3"], width=70, height=26,
                                   command=lambda v: self.settings.set("dialog_wait", float(v)))
            om.set(f"{self.settings.get('dialog_wait', 1.5):g}")
            om.pack(side="left", padx=6)
        ctk.CTkLabel(card, text="Talk to the wisp first so the buttons are on screen, then capture / pick. "
                                "Press Test Dialogue (F1) to check.", font=("Arial", 12), text_color="#ced4da",
                     justify="left", wraplength=410).pack(fill="x", padx=8, pady=(2, 6))

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

    def open_library_guide(self, section=None):
        from gui_guide import SetupGuide, LIBRARY_PAGES
        SetupGuide.show(self.root, section, pages=LIBRARY_PAGES, title="Library Macro — Setup Guide")

    def _save_train_flags(self):
        self.settings.set("train_moves", [bool(v.get()) for v in self.train_vars])
        if hasattr(self, "dialog_card"):
            self.build_dialog_card()

    def refresh_routes(self):
        if not hasattr(self, "route_menu"):
            return
        routes = self.logic.list_routes()
        active = self.logic.active_route()
        self.route_menu.configure(values=routes or ["(none)"])
        self.route_menu.set(active or "(none)")
        self.set_recording_ui(self.logic.is_recording())
        if hasattr(self, "route_panel"):
            self.build_route_panel()

    def set_recording_ui(self, recording):
        if not hasattr(self, "rec_label"):
            return
        if recording:
            self.rec_label.configure(text="● RECORDING… (Ctrl+P to finish)", text_color="#ea868f")
            return
        r = self.logic.load_route()
        if r:
            n_cp = sum(len(sg.get("checkpoints", [])) for sg in r["segments"]) + len(r["return"].get("checkpoints", []))
            what = (f"{r['ores']} ores, {n_cp} checkpoints" if "Mining" in self.root.title()
                    else f"recorded ({sum(s['duration'] for s in r['segments']) or r['return']['duration']:.1f}s walk)")
            self.rec_label.configure(text=f"✓ {what}", text_color="#75b798")
        else:
            self.rec_label.configure(text="Not recorded yet — press Ctrl+P", text_color="#ced4da")

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
            self.log(f"Route '{name}' created. Stand at its start spot and press Ctrl+P to record.")
        elif name:
            self.log("That name is empty or already used.")

    def _rename_route(self):
        old = self.logic.active_route()
        if not old: return
        new = self._ask("Rename route", f"New name for '{old}':", old)
        if new and self.logic.rename_route(old, new):
            self.refresh_routes()
        elif new:
            self.log("That name is empty or already used.")

    def _delete_route(self):
        from tkinter import messagebox
        name = self.logic.active_route()
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
            ctk.CTkLabel(self.route_panel, text="No recording for this route yet.\nStand at the start spot in-game and press Ctrl+P.",
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
            ctk.CTkLabel(body, text="Walk (key · starts at · hold secs):", font=("Arial", 12, "bold")).pack(anchor="w")
            for h in self._holds(seg):
                r = ctk.CTkFrame(body, fg_color="#2b3035", corner_radius=6); r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=h["key"].upper(), width=46, font=("Arial", 13, "bold"), text_color="#9ec5fe").pack(side="left", padx=6)
                ctk.CTkLabel(r, text=f"at {h['start']:.2f}s", width=80, font=("Arial", 12), text_color="#ced4da").pack(side="left")
                e = ctk.CTkEntry(r, width=60, font=("Arial", 12)); e.insert(0, f"{h['dur']:.2f}"); e.pack(side="left", padx=6, pady=3)
                e.bind("<FocusOut>", lambda ev, k=key, h=h, w=e: self._save_hold(k, h, w.get()))

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
        ctk.CTkLabel(head, text=f"{step}. {title}", font=("Arial", 13, "bold"), text_color="#f8f9fa").pack(side="left")
        status = ctk.CTkLabel(head, text="", font=("Arial", 11, "bold"))
        status.pack(side="right")
        ctk.CTkLabel(card, text=desc, font=("Arial", 12), text_color="#ced4da", justify="left",
                     anchor="w", wraplength=420).pack(fill="x", padx=10)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(4, 8))
        return status, row

    def setup_ok_tab(self):
        tab = self.tabview.tab("OK Popup")
        ctk.CTkLabel(tab, text="OK Popup Detection", font=("Arial", 18, "bold"), text_color="#0d6efd").pack(pady=(12, 0))
        ctk.CTkButton(tab, text="? Help", width=60, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#0dcaf0",
                      command=self.open_ok_guide).place(relx=1.0, x=-14, y=14, anchor="ne")
        ctk.CTkLabel(tab, text="Shared by every macro, so you only set it up once.", font=("Arial", 12),
                     text_color="#ced4da").pack(pady=(0, 6))
        if not hasattr(self, "_always_ok_on"):
            self._always_ok_on = False
        self._ok_toggles = getattr(self, "_ok_toggles", [])
        ok_toggle = big_toggle(tab, self.toggle_always_ok)
        ok_toggle.pack(pady=(0, 8), fill="x", padx=20)
        self._ok_toggles.append(ok_toggle)
        style_toggle(ok_toggle, self._always_ok_on, "Always Click OK")
        if not hasattr(self, "always_ok_btn"):
            self.always_ok_btn = ok_toggle
        btn_kw = dict(height=28, font=("Arial", 12), fg_color="#0d6efd", hover_color="#0b5ed7")
        sub_kw = dict(height=28, width=70, font=("Arial", 12), fg_color="#495057", hover_color="#343a40")

        self.ok_btn_status, row = self._ok_card(tab, 1, "Capture OK Button",
            "Open an OK popup in Roblox, then drag a tight box around the OK button.")
        ctk.CTkButton(row, text="📷 Capture", command=self.pick_ok_button, **btn_kw).pack(side="left")
        self.ok_preview = ctk.CTkLabel(row, text="")
        self.ok_preview.pack(side="left", padx=12)

        self.ok_area_status, row = self._ok_card(tab, 2, "Scan Area  (optional)",
            "Where to look for the button. Defaults to the captured box plus a small margin.")
        ctk.CTkButton(row, text="🔲 Set Area", command=lambda: self.pick_region("ok_scan_area"), **btn_kw).pack(side="left")
        ctk.CTkButton(row, text="Clear", command=lambda: self._clear_ok_setting("ok_scan_area", [0, 0, 0, 0]), **sub_kw).pack(side="left", padx=6)
        self.ok_area_switch = ctk.CTkSwitch(row, text="Show on screen", font=("Arial", 12), command=self.toggle_ok_area_overlay)
        self.ok_area_switch.pack(side="left", padx=6)

        self.ok_click_status, row = self._ok_card(tab, 3, "Click Spot  (optional)",
            "A fixed point to click when the popup is found. Defaults to the button itself.")
        ctk.CTkButton(row, text="🖱 Set Spot", command=lambda: self.pick_point("ok_click_pos"), **btn_kw).pack(side="left")
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
        self.ok_btn_status.configure(text="✓ Captured" if tpl_ok else "✗ Not set",
                                     text_color=good if tpl_ok else "#ea868f")
        self.ok_area_status.configure(text="✓ Custom" if is_set("ok_scan_area") else "Default",
                                      text_color=good if is_set("ok_scan_area") else muted)
        pos = regions.get("ok_click_pos", [0, 0])
        self.ok_click_status.configure(text=f"✓ ({pos[0]}, {pos[1]})" if is_set("ok_click_pos") else "Default",
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

    def show_quick_start(self):
        from tkinter import messagebox
        if "Library" in self.root.title():
            self.open_library_guide()
            return
        from gui_guide import SetupGuide, MINING_PAGES, FISHING_PAGES
        if "Mining" in self.root.title():
            SetupGuide.show(self.root, None, pages=MINING_PAGES, title="Mining Macro — Setup Guide")
            return
        if "Fishing" in self.root.title():
            SetupGuide.show(self.root, None, pages=FISHING_PAGES, title="Fishing Macro — Setup Guide")
            return
        else:
            msg = ("1. Settings: tick the moves to train.\n2. Areas: set the 3 Gold Clover areas.\n"
                   "3. Clover Clicker: pick the clover colours.\n4. (Recommended) Record the walk to the wisp with Ctrl+P.\n"
                   "5. Press START!")
        messagebox.showinfo("Setup Guide", msg)

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

    def open_ok_guide(self):
        from gui_guide import SetupGuide, OK_PAGES
        SetupGuide.show(self.root, None, pages=OK_PAGES, title="OK Popup — Setup Guide")

    def toggle_always_ok(self):
        self._always_ok_on = not self._always_ok_on
        for b in getattr(self, "_ok_toggles", [self.always_ok_btn]):      # Main page + OK page stay in sync
            style_toggle(b, self._always_ok_on, "Always Click OK")
        if self._always_ok_on:
            self.logic.start_global_ok_scanner()
        else:
            self.logic.stop_global_ok_scanner()

    def setup_settings_tab(self):
        tab = self.tabview.tab("Settings")
        if "Mining" in self.root.title():
            self.setup_mining_settings(tab)
            return

        sf = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        sf.pack(fill="both", expand=True)
        sb_canvas = getattr(getattr(sf, "_scrollbar", None), "_canvas", None)
        if sb_canvas is not None:
            sb_canvas.update_idletasks = lambda: None     # same speed-up as the Skill Macro pages
        self.setup_library_settings(sf)

    def setup_areas_tab(self):
        tab = self.tabview.tab("Areas")

        self.gold_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        self.gold_card.pack(fill="x", padx=15, pady=(10, 4))
        self.build_gold_card()

        self.minigame_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        self.minigame_card.pack(fill="x", padx=15, pady=4)
        self.build_minigame_card()

        hc = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        hc.pack(fill="x", padx=15, pady=4)
        row = ctk.CTkFrame(hc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        sw = ctk.CTkSwitch(row, text="💬 Hide chat during the minigame", font=("Arial", 13, "bold"),
                           command=lambda: self.settings.set("hide_chat_in_minigame", bool(sw.get())))
        if self.settings.get("hide_chat_in_minigame"):
            sw.select()
        sw.pack(side="left")
        ctk.CTkLabel(hc, text="The chat's white Here / Global / Friends tabs look like silver clovers. Pick the chat "
                              "button at the top of Roblox: it's clicked to close chat when a minigame starts and "
                              "again to open it after.", font=("Arial", 12), text_color="#ced4da", justify="left",
                     wraplength=420).pack(fill="x", padx=8)
        row = ctk.CTkFrame(hc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(4, 8))
        ctk.CTkButton(row, text="🎯 Pick chat button", width=150, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=lambda: self.pick_point("chat_button")).pack(side="left")
        pos = self.settings.get("regions", {}).get("chat_button", [0, 0])
        self.chat_btn_lbl = ctk.CTkLabel(row, text=f"✔ ({pos[0]}, {pos[1]})" if any(pos) else "not set",
                                         font=("Arial", 12), text_color="#75b798" if any(pos) else "#ea868f")
        self.chat_btn_lbl.pack(side="left", padx=8)

        cr = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        cr.pack(fill="x", padx=15, pady=4)
        row = ctk.CTkFrame(cr, fg_color="transparent"); row.pack(fill="x", padx=8, pady=6)
        ctk.CTkButton(row, text="Clover Region", width=150, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=lambda: self.pick_region("score")).pack(side="left")
        ctk.CTkLabel(row, text="optional — where clovers can appear",
                     font=("Arial", 12), text_color="#ced4da").pack(side="left", padx=8)
        self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays, font=("Arial", 12))
        self.overlay_switch.pack(pady=10)

    # ---------- Gold clover: automatic from the hotbar, or manual boxes ----------
    def build_gold_card(self):
        gc = self.gold_card
        for w in gc.winfo_children():
            w.destroy()
        mode = self.logic.gold_mode()
        head = ctk.CTkFrame(gc, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(head, text="🍀 Gold Clover detection", font=("Arial", 14, "bold"), text_color="#0d6efd").pack(side="left")
        ctk.CTkButton(head, text="? Help", width=60, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#0dcaf0",
                      command=lambda: self.open_library_guide("Gold Clover")).pack(side="right")
        seg = ctk.CTkSegmentedButton(gc, values=["Automatic", "Manual"], font=("Arial", 12, "bold"),
                                     command=lambda v: (self.settings.set("gold_mode", v.lower()), self.build_gold_card()))
        seg.set("Automatic" if mode == "auto" else "Manual")
        seg.pack(fill="x", padx=8, pady=4)
        self.gold_status = {}
        if mode == "manual":
            ctk.CTkLabel(gc, text="Drag a SMALL box over the spot where each move's 3rd clover appears.",
                         font=("Arial", 12), text_color="#ced4da", justify="left", wraplength=420).pack(fill="x", padx=8)
            regions = self.settings.get("regions", {})
            flags = self.logic.train_flags()
            for i in [k + 1 for k, on in enumerate(flags) if on]:
                row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
                ctk.CTkButton(row, text=f"Set Move {i}'s spot", width=150, height=28, fg_color="#0d6efd",
                              hover_color="#0b5ed7", command=lambda idx=i: self.pick_region(f"gold_clover_{idx}")).pack(side="left")
                ok = any(regions.get(f"gold_clover_{i}", [0, 0, 0, 0]))
                lbl = ctk.CTkLabel(row, text="✔ set" if ok else "not set", font=("Arial", 12),
                                   text_color="#75b798" if ok else "#ea868f")
                lbl.pack(side="left", padx=8)
                self.gold_status[i] = lbl
            ctk.CTkLabel(gc, text="", height=4).pack()
            return

        ctk.CTkLabel(gc, text="Drag ONE box over your whole hotbar, from the TOP of the clovers to the bottom of the "
                              "icons, first icon to last. The 3rd-clover spot of every slot is found automatically.",
                     font=("Arial", 12), text_color="#ced4da", justify="left", wraplength=420).pack(fill="x", padx=8)
        hb = self.settings.settings.setdefault("gold_hotbar", {"region": [0, 0, 0, 0], "slots": 6})
        row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(row, text="🔲 Set hotbar", width=120, height=28, fg_color="#0d6efd", hover_color="#0b5ed7",
                      command=self.pick_gold_hotbar).pack(side="left")
        ok = self.logic.gold_hotbar()[0] is not None
        ctk.CTkLabel(row, text="✔ set" if ok else "not set", font=("Arial", 12),
                     text_color="#75b798" if ok else "#ea868f").pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Slots", font=("Arial", 12)).pack(side="left", padx=(8, 2))
        om = ctk.CTkOptionMenu(row, values=[str(i) for i in range(1, 11)], width=60, height=26,
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
        ctk.CTkLabel(gc, text="", height=4).pack()

    def pick_gold_hotbar(self):
        self._hide_for_pick()

        def done(x1, y1, x2, y2):
            self.root.deiconify()
            self.settings.settings.setdefault("gold_hotbar", {"slots": 6})["region"] = [x1, y1, x2, y2]
            self.settings.save()
            self.build_gold_card()
            self.log("Hotbar saved. Press Show to check the yellow boxes sit on each 3rd-clover spot.")
        Overlay(done)

    def show_gold_spots(self):
        """Yellow box on the 3rd-clover spot of every slot, for 3 seconds."""
        r, n = self.logic.gold_hotbar()
        if not r:
            self.log("Set the hotbar first."); return
        boxes = [PersistentOverlay(*self.logic.third_clover_rect(k), color="yellow") for k in range(1, n + 1)]
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
                         f"{'GOLD ✔' if gold else 'not yet'} ({(share or 0):.2f})")
        self.gold_test_lbl.configure(text="\n".join(parts) or "Tick moves to train first (Settings).")

    # ---------- Minigame detector ----------
    def build_minigame_card(self):
        card = self.minigame_card
        for w in card.winfo_children():
            w.destroy()
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(head, text="🎮 Minigame detector", font=("Arial", 14, "bold"), text_color="#0d6efd").pack(side="left")
        ctk.CTkButton(head, text="? Help", width=60, height=24, font=("Arial", 11, "bold"), fg_color="#343a40",
                      hover_color="#495057", text_color="#0dcaf0",
                      command=lambda: self.open_library_guide("Minigame")).pack(side="right")
        ctk.CTkLabel(card, text="During a minigame, press Capture: the screen freezes — drag a box around something that "
                                "ONLY shows in the minigame (its timer, score or title). Walking starts once it's gone.",
                     font=("Arial", 12), text_color="#ced4da", justify="left", wraplength=420).pack(fill="x", padx=8, pady=(2, 4))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(0, 4))
        ok = self.logic.has_minigame_snapshot()
        ctk.CTkButton(row, text="📸 Re-capture" if ok else "📸 Capture", width=120, height=28, fg_color="#0d6efd",
                      hover_color="#0b5ed7", command=self.capture_minigame).pack(side="left")
        ctk.CTkLabel(row, text="✔ captured" if ok else "not captured", font=("Arial", 12),
                     text_color="#75b798" if ok else "#ea868f").pack(side="left", padx=8)
        ctk.CTkButton(row, text="Test", width=56, height=28, fg_color="#495057", hover_color="#343a40",
                      command=self.test_minigame).pack(side="right")
        self.minigame_test_lbl = ctk.CTkLabel(row, text="", font=("Arial", 12, "bold"))
        self.minigame_test_lbl.pack(side="right", padx=8)
        row2 = ctk.CTkFrame(card, fg_color="transparent"); row2.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkLabel(row2, text="Match needed", font=("Arial", 12)).pack(side="left")
        om = ctk.CTkOptionMenu(row2, values=["0.6", "0.7", "0.8", "0.9"], width=70, height=26,
                               command=lambda v: self.settings.set("minigame_threshold", float(v)))
        om.set(f"{self.settings.get('minigame_threshold', 0.8):g}")
        om.pack(side="left", padx=6)
        ctk.CTkLabel(row2, text="lower = finds it easier",
                     font=("Arial", 12), text_color="#ced4da").pack(side="left")

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
        on = s >= float(self.settings.get("minigame_threshold", 0.8))
        self.minigame_test_lbl.configure(text=f"{'IN minigame' if on else 'not in minigame'} ({s:.2f})",
                                         text_color="#75b798" if on else "#adb5bd")

    def setup_clover_tab(self):
        tab = self.tabview.tab("Clover Clicker")
        ctk.CTkLabel(tab, text="Clover Target Colors & Tolerances", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(pady=10)

        self.color_previews, self.color_labels = {}, {}
        self.clover_tol_sliders, self.clover_tol_labels = {}, {}

        colors = self.settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        global_tol = self.settings.get("color_tolerance", 25)
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

            tol_val = clover_tols.get(c, global_tol)
            slider = ctk.CTkSlider(f_tol, from_=1, to=100, number_of_steps=99, height=16,
                                  command=lambda val, cl=c: self.update_clover_tolerance(cl, val))
            slider.set(tol_val)
            slider.pack(side="left", fill="x", expand=True, padx=5)
            self.clover_tol_sliders[c] = slider

            val_lbl = ctk.CTkLabel(f_tol, text=str(int(tol_val)), width=35, font=("Arial", 13, "bold"), text_color="#ffffff")
            val_lbl.pack(side="right", padx=5)
            self.clover_tol_labels[c] = val_lbl

        ctk.CTkButton(tab, text="Reset to Defaults", fg_color="#dc3545", hover_color="#bb2d3b", font=("Arial", 12, "bold"), command=self.reset_clover_colors).pack(pady=10)

        explanation_frame = ctk.CTkFrame(tab, fg_color="#032830", border_color="#087990", border_width=1, corner_radius=8)
        explanation_frame.pack(pady=8, fill="x", padx=15)

        explanation_text = (
            "WHAT IS 'TOL'? (TOLERANCE)\n\n"
            "This controls how much the color can vary from your 'Picked' color.\n"
            "• Lower (1-10): Very strict. Best for stable lighting.\n"
            "• Higher (20-40): More lenient for in-game lighting shifts."
        )
        ctk.CTkLabel(explanation_frame, text=explanation_text, font=("Arial", 12), text_color="#6edff6", justify="left", wraplength=360).pack(padx=12, pady=10, fill="x")

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

    def setup_hotkeys_tab(self):
        tab = self.tabview.tab("Hotkeys")
        ctk.CTkLabel(tab, text="Custom Hotkeys", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(pady=10)
        self.hotkey_entries = {}
        hotkeys = self.settings.get("hotkeys")
        actions = ["start"]

        if "Fishing" in self.root.title():
            if hasattr(self.logic, 'test_bar_detection'): actions.append('test_btn')
            if hasattr(self.logic, 'test_fish_detection'): actions.append('test_color')
        else:
            if hasattr(self.logic, 'test_detection'): actions.append('test_btn')
            if hasattr(self.logic, 'test_color_detection'): actions.append('test_color')

        if hasattr(self.logic, 'test_movement'): actions.append('test_movement')
        if hasattr(self.logic, 'test_path') and not hasattr(self.logic, 'test_movement'): actions.append('test_path')

        for a in actions:
            f = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            f.pack(pady=3, fill="x", padx=20)
            display_names = {"start": "Start / Stop", "test_btn": "Test Ok Popup", "test_color": "Test Color",
                             "test_movement": "Test Movement"}
            if "Mining" in self.root.title():
                display_names.update({"test_btn": "Test Prompt", "test_movement": "Test Path"})
            elif "Library" in self.root.title():
                display_names.update({"test_btn": "Test Dialogue", "test_path": "Test Path"})
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
            ctk.CTkLabel(f, text="Ctrl+P (start / stop)", font=("Arial", 12), text_color="#ced4da").pack(side="right", padx=10)
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

        try_add('start', self.toggle_macro)          # F6 starts AND stops

        if "Fishing" in self.root.title():
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

        if hasattr(self.logic, "toggle_recording"):
            try:
                keyboard.add_hotkey("ctrl+p", self.logic.toggle_recording)
            except Exception as e:
                self.log(f"Hotkey Error (record): {e}")

        self.log("Hotkeys registered")

    def toggle_macro(self):
        """F6 / the Start-Stop button: start when stopped, stop (and reload settings) when running."""
        if self.logic.running:
            self.refresh_macro()
        else:
            self.logic.start()
        self.root.after(0, self._sync_start_btn)

    def _sync_start_btn(self):
        """Keep the button in step with the macro, also when it stops by itself (e.g. all moves trained)."""
        try:
            if not self.start_btn.winfo_exists():
                return
        except Exception:
            return
        running = bool(self.logic.running)
        if running != self._shown_running:
            key = self.settings.get("hotkeys", {}).get("start", "f6").upper()
            if running:
                self.start_btn.configure(text=f"■  Stop Macro ({key})", fg_color="#dc3545", hover_color="#bb2d3b")
            else:
                self.start_btn.configure(text=f"▶  Start Macro ({key})", fg_color="#198754", hover_color="#157347")
            self._shown_running = running
        self.root.after(400, self._sync_start_btn)

    def refresh_macro(self):
        self.logic.stop(); self.settings.load(); self.register_hotkeys(); self.log("Macro stopped")

    def _run_test(self, fn):
        import threading
        def wrapper():
            self.logic.test_running = True
            try:
                fn()
            finally:
                self.logic.test_running = False
        threading.Thread(target=wrapper, daemon=True).start()

    def update_hotkey(self, a):
        key = self.hotkey_entries[a].get().lower()
        hk = self.settings.get("hotkeys"); hk[a] = key; self.settings.set("hotkeys", hk); self.register_hotkeys()

    def update_move_name(self, idx):
        names = self.logic.move_names() if hasattr(self.logic, "move_names") else self.settings.get("move_names")
        new_name = self.move_entries[idx].get()
                                                              
        if new_name != names[idx]:
            names[idx] = new_name
            self.settings.set("move_names", names)
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

    def log(self, msg):
        if hasattr(self, 'status_label'): self.status_label.configure(text=f"Status: {msg}")
        print(msg)

    def _hide_for_pick(self):
        """Hide the macro window and give Windows time to repaint, so the
        picker's screenshot doesn't include this window."""
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)

    def pick_region(self, key):
        self._hide_for_pick()
        Overlay(lambda x1, y1, x2, y2: self.save_region(key, x1, y1, x2, y2))

    def save_region(self, key, x1, y1, x2, y2):
        self.root.deiconify(); self.settings.settings["regions"][key] = [x1, y1, x2, y2]; self.settings.save(); self.check_calibration()
        if key.startswith("gold_clover_") and getattr(self, "gold_status", {}).get(int(key[-1])):
            self.gold_status[int(key[-1])].configure(text="✔ set", text_color="#75b798")
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
            self.chat_btn_lbl.configure(text=f"✔ ({x}, {y})", text_color="#75b798")
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
        default_tols = {"gold": 20, "silver": 20, "bronze": 20}
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

        self.gold_label = ctk.CTkLabel(card, text=f"Total Gold Used: {self.settings.get('total_gold', 0)}", font=("Arial", 15, "bold"), text_color="#ffc107")
        self.gold_label.pack(pady=12, padx=10)

        stats_card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        stats_card.pack(fill="x", padx=20, pady=5)

        self.move_stats_labels = []
        nine = getattr(self.logic, "_nine", None)
        move_names = nine("move_names", "") if nine else self.settings.get("move_names", ["", "", ""])
        move_stats = nine("move_stats", 0) if nine else self.settings.get("move_stats", [0, 0, 0])
        for i in range(len(move_names)):
            lbl_name = move_names[i] if move_names[i] else f"Move {i+1}"
            lbl = ctk.CTkLabel(stats_card, text=f"{lbl_name}: {move_stats[i]}", font=("Arial", 13), text_color="#ffffff")
            lbl.pack(pady=6, padx=10)
            self.move_stats_labels.append(lbl)

        ctk.CTkButton(tab, text="Reset Statistics", fg_color="#dc3545", hover_color="#bb2d3b", font=("Arial", 12, "bold"), command=self.reset_gold).pack(pady=25)

    def update_gold_display(self):
        if not hasattr(self, 'gold_label'):
            return
        total_gold = self.settings.get("total_gold", 0)
        self.gold_label.configure(text=f"Total Gold Used: {total_gold}")
        
        move_names = self.settings.get("move_names", ["", "", ""])
        move_stats = self.settings.get("move_stats", [0, 0, 0])
        if hasattr(self, 'move_stats_labels'):
            for i in range(min(len(move_names), len(self.move_stats_labels))):
                lbl_name = move_names[i] if move_names[i] else f"Move {i+1}"
                self.move_stats_labels[i].configure(text=f"{lbl_name}: {move_stats[i]}")

    def reset_gold(self):
        self.settings.set("total_gold", 0); self.settings.set("move_stats", [0] * len(self.settings.get("move_stats") or [0, 0, 0])); self.log("Statistics Reset")
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
            relevant_keys = ["score", "gold_clover_1", "gold_clover_2", "gold_clover_3"]

        colors = ["red", "green", "blue", "yellow", "cyan", "magenta"]
        for i, key in enumerate(relevant_keys):
            rect = regions.get(key)
            if rect and any(v != 0 for v in rect):
                self.overlays[key] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color=colors[i % len(colors)])

    def toggle_ok_area_overlay(self):
        old = self.overlays.pop("_ok_area", None)
        if old: old.destroy()
        if self.ok_area_switch.get() != 1:
            return
        rect = self.logic.get_ok_search_region()
        if rect:
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
