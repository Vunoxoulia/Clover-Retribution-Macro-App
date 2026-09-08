import customtkinter as ctk
import tkinter as tk
from settings import SpatialSettings
from overlay import Overlay, PointSelector, ColorPicker, PersistentOverlay
from updater import SpatialUpdater
from logic_library import LibraryLogic
from logic_tundra import TundraLogic, DEFAULT_NODE_STEPS
from logic_cave import CaveLogic
from logic_fishing import FishingLogic
from logic_devil_union import DevilUnionLogic
import keyboard
import os
import sys
import webbrowser

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

        self.create_card("Library Macro", "Full automation for the\nSpatial Library.", "Launch", 
                         lambda: self.on_select("Library Macro", LibraryLogic, 
                                                tabs=["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"],
                                                tutorial_url="https://youtu.be/Nb1vjq6DC4I"), 0)

        self.create_card("Tundra Mining", "Automated mining in\nthe Tundra region.", "Launch", 
                         lambda: self.on_select("Tundra Mining", TundraLogic, 
                                                tabs=["Main", "Settings", "Hotkeys"],
                                                tutorial_url="https://youtu.be/dOCZW46MCp8"), 1)

        self.create_card("Cave Mining", "Automated mining in\nthe Cave region.", "Coming Soon", None, 2)

        self.create_card("Fishing Macro", "Automated fishing for\nvarious rewards.", "Launch", 
                         lambda: self.on_select("Fishing Macro", FishingLogic, 
                                                tabs=["Main", "Fishing Settings", "Hotkeys"],
                                                tutorial_url="https://youtu.be/nIvzTzCzbFE"), 3)

        self.create_card("Devil Union", "Automated training for\nDevil Union abilities.", "Coming Soon", None, 4)

        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=10, padx=20)
        
        update_btn = ctk.CTkButton(footer, text="Check for Updates", width=150, fg_color="#0d6efd", hover_color="#0b5ed7", command=self.check_updates)
        update_btn.pack(side="left", padx=(0, 10))

        patch_notes_btn = ctk.CTkButton(footer, text="Patch Notes", width=120, command=self.show_patch_notes, fg_color="#495057", hover_color="#343a40")
        patch_notes_btn.pack(side="left")

        links_frame = ctk.CTkFrame(footer, fg_color="transparent")
        links_frame.pack(side="right", pady=10)

        yt_link = ctk.CTkLabel(links_frame, text="Youtube", font=("Arial", 12, "underline"), text_color="#dc3545", cursor="hand2")
        yt_link.pack(side="left", padx=5)
        yt_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.youtube.com/@Vunoxoulia"))

        dc_link = ctk.CTkLabel(links_frame, text="discord", font=("Arial", 12, "underline"), text_color="#0dcaf0", cursor="hand2")
        dc_link.pack(side="left", padx=5)
        dc_link.bind("<Button-1>", lambda e: webbrowser.open("https://discord.com/invite/VRMB4djfzp"))

        donate_link = ctk.CTkLabel(links_frame, text="Donate", font=("Arial", 12, "underline"), text_color="#ffc107", cursor="hand2")
        donate_link.pack(side="left", padx=5)
        donate_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.roblox.com/communities/34022778/The-Manga-Corner#!/store"))

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
        card = ctk.CTkFrame(self.cards_frame, width=230, height=290, corner_radius=12, fg_color="#212529", border_color="#343a40", border_width=1)
        card.grid(row=0, column=column, padx=12, pady=10, sticky="nsew")
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=title, font=("Arial", 18, "bold"), text_color="#ffffff").pack(pady=(20, 8))
        ctk.CTkLabel(card, text=description, font=("Arial", 13), text_color="#e9ecef", justify="center").pack(pady=8, padx=10)
        btn = ctk.CTkButton(card, text=button_text, command=command, font=("Arial", 13, "bold"), fg_color="#0d6efd", hover_color="#0b5ed7")
        if command is None:
            btn.configure(state="disabled", fg_color="#343a40", text_color="#6c757d")
        btn.pack(side="bottom", pady=20)
        self.cards_frame.grid_columnconfigure(column, weight=1)

class SpatialGUI:
    def __init__(self, root, title="Spatial Macro", logic_class=LibraryLogic, on_back=None, tabs=None, tutorial_url="#"):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        self.root.geometry("560x680" if "Tundra" in title else "480x680")
        self.tutorial_url = tutorial_url
        self.settings = SpatialSettings()
        self.logic = logic_class(self)
        self.overlays = {} 
        self.tabs_to_show = tabs if tabs else ["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"]
        self.DEFAULT_CLOVER_COLORS = {"gold": (251, 198, 108), "silver": (187, 197, 197), "bronze": (219, 151, 139)}
        self.DEFAULT_CLOVER_TOLERANCES = {"gold": 33, "silver": 30, "bronze": 40}
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.setup_ui()
        self.register_hotkeys()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)
        for tab_name in self.tabs_to_show: self.tabview.add(tab_name)
        if "Main" in self.tabs_to_show: self.setup_main_tab()
        if "Settings" in self.tabs_to_show: self.setup_settings_tab()
        if "Areas" in self.tabs_to_show: self.setup_areas_tab()
        if "Clover Clicker" in self.tabs_to_show: self.setup_clover_tab()
        if "Fishing Settings" in self.tabs_to_show: self.setup_fishing_settings_tab()
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
        self.start_btn = ctk.CTkButton(tab, text=f"Start Macro ({hk['start'].upper()})", font=("Arial", 14, "bold"), fg_color="#198754", hover_color="#157347", command=self.logic.start)
        self.start_btn.pack(pady=6, fill="x", padx=40)
        self.refresh_btn = ctk.CTkButton(tab, text=f"Reload Macro ({hk['refresh'].upper()})", font=("Arial", 12), fg_color="#6c757d", hover_color="#5c636a", command=self.refresh_macro)
        self.refresh_btn.pack(pady=4, fill="x", padx=40)

        if self.on_back:
            ctk.CTkButton(tab, text="Back to Menu", fg_color="transparent", border_color="#6c757d", border_width=2, text_color="#e9ecef", command=self.go_back).pack(pady=(15, 8))
        tutorial_link = ctk.CTkLabel(tab, text="Video Tutorial", font=("Arial", 14, "underline"), text_color="#0dcaf0", cursor="hand2")
        tutorial_link.pack(side="bottom", pady=10)
        tutorial_link.bind("<Button-1>", lambda e: webbrowser.open(self.tutorial_url))

    def show_quick_start(self):
        from tkinter import messagebox
        if "Tundra" in self.root.title():
            msg = "1. Watch tutorial to find spot.\n2. Go there in-game.\n3. Press F6 to start!"
        elif "Fishing" in self.root.title():
            msg = "1. Go to 'Fishing Settings'.\n2. Set 'Minigame Bar Area'.\n3. Pick 'Bar Color' (Green) and 'Fish Color' (White).\n4. Press F6 to start!"
        else:
            msg = "1. Set 'Move Selection Area'.\n2. Set 'Clover Region' & 'Quest Region'.\n3. Pick colors in 'Clover Clicker'.\n4. Set Move Names.\n5. Press START!"
        messagebox.showinfo("Setup Guide", msg)

    def check_calibration(self):
        regions = self.settings.get("regions", {})
        if "Fishing" in self.root.title():
            essential = ["minigame_bar", "fishing_click_pos"]
        elif "Tundra" in self.root.title():
            essential = ["tundra_detection_region"]
        else:
            essential = ["score", "move_menu", "quest_region"]
            
        missing = [r for r in essential if r not in regions or all(v == 0 for v in regions[r])]
        if missing: self.calib_frame.pack(pady=10, fill="x", padx=20)
        else: self.calib_frame.pack_forget()

    def go_back(self):
        self.logic.stop()
        keyboard.unhook_all()
        if self.on_back: self.on_back()

    def setup_settings_tab(self):
        tab = self.tabview.tab("Settings")
        if "Tundra" in self.root.title():
            ctk.CTkLabel(tab, text="Tundra Mining Settings", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(pady=(5, 2))

            # Detection controls card
            det_frame = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            det_frame.pack(fill="x", padx=15, pady=4)

            ctk.CTkButton(det_frame, text="Set Detection Region", fg_color="#0d6efd", hover_color="#0b5ed7",
                           command=lambda: self.pick_region("tundra_detection_region")).pack(side="left", padx=5, pady=5)
            ctk.CTkButton(det_frame, text="Test White (F1)", fg_color="#495057", hover_color="#343a40", width=95,
                           command=lambda: self._run_test(self.logic.test_detection)).pack(side="left", padx=3, pady=5)
            ctk.CTkButton(det_frame, text="Test Path (F2)", fg_color="#495057", hover_color="#343a40", width=95,
                           command=lambda: self._run_test(self.logic.test_movement)).pack(side="left", padx=3, pady=5)

            # Variance & Sprinting Delay row
            var_frame = ctk.CTkFrame(tab, fg_color="transparent")
            var_frame.pack(fill="x", padx=15, pady=2)

            ctk.CTkLabel(var_frame, text="Tol:", font=("Arial", 12, "bold")).pack(side="left", padx=2)
            self.fishing_tolerance_slider = ctk.CTkSlider(var_frame, from_=1, to=100, number_of_steps=99, command=self.update_tolerance, width=90)
            self.fishing_tolerance_slider.set(self.settings.get("color_tolerance", 25))
            self.fishing_tolerance_slider.pack(side="left", padx=3)
            self.fishing_tolerance_val_label = ctk.CTkLabel(var_frame, text=f"{int(self.fishing_tolerance_slider.get())}", font=("Arial", 12, "bold"), width=22)
            self.fishing_tolerance_val_label.pack(side="left")

            ctk.CTkLabel(var_frame, text="Sprint Delay (s):", font=("Arial", 12, "bold"), text_color="#e9ecef").pack(side="left", padx=(8, 2))
            self.sprinting_delay_entry = ctk.CTkEntry(var_frame, width=46, font=("Arial", 12))
            self.sprinting_delay_entry.insert(0, f"{float(self.settings.get('sprinting_delay', 0.25)):.2f}")
            self.sprinting_delay_entry.pack(side="left")
            self.sprinting_delay_entry.bind("<FocusOut>", lambda e: self.save_sprinting_delay())
            self.sprinting_delay_entry.bind("<KeyRelease>", lambda e: self.save_sprinting_delay())
            

            self.overlay_switch = ctk.CTkSwitch(var_frame, text="Scan Areas", command=self.toggle_overlays, font=("Arial", 12))
            self.overlay_switch.pack(side="right", padx=2)

            # Section Header for Node Timers
            header_frame = ctk.CTkFrame(tab, fg_color="transparent")
            header_frame.pack(fill="x", padx=15, pady=(6, 0))
            ctk.CTkLabel(header_frame, text="⛏️ Mining Node Timers", font=("Arial", 14, "bold"), text_color="#ffffff").pack(side="left")

            ctk.CTkLabel(tab, text="All values below are in SECONDS. Click a node to expand it. \"Walk\" shows the exact keys "
                                    "held, in order, to reach that node (e.g. D 0.30 = hold D for 0.30s, then S 0.10 = hold S for 0.10s).",
                         font=("Arial", 11), text_color="#9aa4ae", justify="left", wraplength=430).pack(fill="x", padx=15, pady=(2, 6))

            # Scrollable Node Timers Frame
            self.nodes_scroll_frame = ctk.CTkScrollableFrame(tab, fg_color="#1a1d20", corner_radius=8, height=310)
            self.nodes_scroll_frame.pack(fill="both", expand=True, padx=15, pady=4)

            self.node_input_widgets = {}

            node_timers = self.settings.get("node_timers", {})

            self.node_expanded = getattr(self, 'node_expanded', {})

            for i in range(1, 12):
                node_key = str(i)
                cfg = node_timers.get(node_key, {})
                steps = cfg.get("steps") or [{"key": k, "seconds": s} for k, s in DEFAULT_NODE_STEPS[node_key]]

                card = ctk.CTkFrame(self.nodes_scroll_frame, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
                card.pack(fill="x", padx=4, pady=3)

                # Node header - click to expand/collapse this node's settings
                toggle_btn = ctk.CTkButton(card, text=f"Node {i}   ▸", fg_color="#0d6efd", hover_color="#0b5ed7",
                                           text_color="#ffffff", font=("Arial", 13, "bold"), anchor="w",
                                           corner_radius=6, height=32)
                toggle_btn.pack(fill="x", padx=6, pady=6)

                details = ctk.CTkFrame(card, fg_color="transparent")
                # Not packed yet - stays collapsed/hidden until the header is clicked.

                # Inputs Row 1: Mining / Waiting timers
                row = ctk.CTkFrame(details, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=(0, 5))

                ctk.CTkLabel(row, text="Mining Secs:", font=("Arial", 12, "bold"), text_color="#e9ecef").pack(side="left", padx=(0, 2))
                hold_entry = ctk.CTkEntry(row, width=48, font=("Arial", 12))
                hold_entry.insert(0, f"{float(cfg.get('mine_hold', 3.0)):.2f}")
                hold_entry.pack(side="left", padx=(0, 10))
                hold_entry.bind("<FocusOut>", lambda e, idx=i: self.save_node_timer(idx))
                hold_entry.bind("<KeyRelease>", lambda e, idx=i: self.save_node_timer(idx))

                ctk.CTkLabel(row, text="Waiting Secs:", font=("Arial", 12, "bold"), text_color="#e9ecef").pack(side="left", padx=(0, 2))
                wait_entry = ctk.CTkEntry(row, width=48, font=("Arial", 12))
                wait_entry.insert(0, f"{float(cfg.get('mine_wait', 1.75)):.2f}")
                wait_entry.pack(side="left", padx=(0, 6))
                wait_entry.bind("<FocusOut>", lambda e, idx=i: self.save_node_timer(idx))
                wait_entry.bind("<KeyRelease>", lambda e, idx=i: self.save_node_timer(idx))

                # Inputs Row 2: the exact WASD key sequence walked to reach this node.
                # Each entry is the raw hold duration (seconds) for that key press -
                # not a multiplier - so it shows only the keys actually used per node.
                steps_row = ctk.CTkFrame(details, fg_color="transparent")
                steps_row.pack(fill="x", padx=8, pady=(0, 8))

                ctk.CTkLabel(steps_row, text="Walk (sec):", font=("Arial", 12, "bold"), text_color="#e9ecef").pack(side="left", padx=(0, 4))

                step_widgets = []
                for step in steps:
                    key_char = str(step.get("key", "?")).upper()
                    ctk.CTkLabel(steps_row, text=key_char, font=("Arial", 12, "bold"), text_color="#8bb9fe").pack(side="left", padx=(0, 2))
                    step_entry = ctk.CTkEntry(steps_row, width=46, font=("Arial", 12))
                    step_entry.insert(0, f"{float(step.get('seconds', 0.0)):.2f}")
                    step_entry.pack(side="left", padx=(0, 8))
                    step_entry.bind("<FocusOut>", lambda e, idx=i: self.save_node_timer(idx))
                    step_entry.bind("<KeyRelease>", lambda e, idx=i: self.save_node_timer(idx))
                    step_widgets.append({"key": step.get("key"), "entry": step_entry})

                # Store widgets for all controls
                self.node_input_widgets[i] = {
                    "hold": hold_entry,
                    "wait": wait_entry,
                    "steps": step_widgets
                }

                toggle_btn.configure(command=lambda idx=i, btn=toggle_btn, frame=details: self.toggle_node_card(idx, btn, frame))
                if self.node_expanded.get(i):
                    details.pack(fill="x")
                    toggle_btn.configure(text=f"Node {i}   ▾")

            return

        ctk.CTkButton(tab, text="Move Selection Area (OCR)", command=lambda: self.pick_region("move_menu")).pack(pady=10)
        ctk.CTkButton(tab, text="Test Ok Popup (F1)", fg_color="#445566", width=160,
                      command=lambda: self._run_test(self.logic.test_detection)).pack(pady=(0, 10))
        ctk.CTkLabel(tab, text="Move Names (for OCR):").pack(pady=5)
        self.move_entries = []
        self.resolved_labels = []
        for i in range(3):
            frame = ctk.CTkFrame(tab, fg_color="transparent")
            frame.pack(pady=2, fill="x", padx=40)
            entry = ctk.CTkEntry(frame, placeholder_text=f"Move {i+1} Name")
            entry.insert(0, self.settings.get("move_names")[i])
            entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
            entry.bind("<FocusOut>", lambda e, idx=i: self.update_move_name(idx))
            entry.bind("<KeyRelease>", lambda e, idx=i: self.update_move_name(idx))
            self.move_entries.append(entry)
            ctk.CTkButton(frame, text="Test", width=50, command=lambda idx=i: self._run_test(lambda: self.logic.test_move_ocr(idx))).pack(side="right")

            lock_frame = ctk.CTkFrame(tab, fg_color="transparent")
            lock_frame.pack(fill="x", padx=40, pady=(0, 4))
            resolved = self.settings.get("resolved_move_names", ["", "", ""])[i]
            pos = self.settings.get("resolved_move_positions", [None, None, None])[i]
            if resolved and pos:
                lock_text = f"🔒 {resolved}  ({pos[0]}, {pos[1]})"
            elif resolved:
                lock_text = f"🔒 {resolved}"
            else:
                lock_text = "unlocked"
            lock_color = "#4CAF50" if resolved else "gray55"
            lbl = ctk.CTkLabel(lock_frame, text=lock_text, font=("Arial", 12),
                               text_color=lock_color, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            ctk.CTkButton(lock_frame, text="✕", width=28, height=20,
                          fg_color="gray30", hover_color="#A13333",
                          command=lambda idx=i: self.clear_resolved_name(idx)).pack(side="right")
            self.resolved_labels.append(lbl)

    def setup_areas_tab(self):
        tab = self.tabview.tab("Areas")
        if "Tundra" in self.root.title():
            ctk.CTkLabel(tab, text="Tundra Detection Area", font=("Arial", 16, "bold"), text_color="#0d6efd").pack(pady=(10, 5))
            card = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            card.pack(pady=5, fill="x", padx=20)
            ctk.CTkButton(card, text="Set Detection Region", fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_region("quest_region")).pack(side="left", fill="x", expand=True, padx=8, pady=8)
            ctk.CTkButton(card, text="Test", width=60, fg_color="#495057", hover_color="#343a40", command=lambda: self._run_test(self.logic.test_detection)).pack(side="right", padx=8, pady=8)
            self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays, font=("Arial", 12))
            self.overlay_switch.pack(pady=15)
            return

        ctk.CTkLabel(tab, text="Gold Clover Move Status Areas", font=("Arial", 14, "bold"), text_color="#0d6efd").pack(pady=(10, 5))
        for i in range(1, 4):
            ctk.CTkButton(tab, text=f"Gold Clover {i}", fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda idx=i: self.pick_region(f"gold_clover_{idx}")).pack(pady=3)

        ctk.CTkLabel(tab, text="\nMinigame UI Regions", font=("Arial", 14, "bold"), text_color="#0d6efd").pack(pady=5)
        ctk.CTkButton(tab, text="Clover Region", fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_region("score")).pack(pady=3)
        f = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
        f.pack(pady=4, fill="x", padx=20)
        ctk.CTkButton(f, text="Quest/Guide Region", fg_color="#0d6efd", hover_color="#0b5ed7", command=lambda: self.pick_region("quest_region")).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ctk.CTkButton(f, text="Test", width=55, fg_color="#495057", hover_color="#343a40", command=lambda: self._run_test(self.logic.test_quest_ocr)).pack(side="right", padx=6, pady=6)
        self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays, font=("Arial", 12))
        self.overlay_switch.pack(pady=15)

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
        actions = ["start", "refresh"]

        if "Fishing" in self.root.title():
            if hasattr(self.logic, 'test_bar_detection'): actions.append('test_btn')
            if hasattr(self.logic, 'test_fish_detection'): actions.append('test_color')
        else:
            if hasattr(self.logic, 'test_detection'): actions.append('test_btn')
            if hasattr(self.logic, 'test_color_detection'): actions.append('test_color')

        if hasattr(self.logic, 'test_movement'): actions.append('test_movement')

        for a in actions:
            f = ctk.CTkFrame(tab, fg_color="#212529", border_color="#343a40", border_width=1, corner_radius=8)
            f.pack(pady=3, fill="x", padx=20)
            display_names = {"test_btn": "Test Ok Popup", "test_color": "Test Color", "test_movement": "Test Movement"}
            label_text = display_names.get(a, a.replace("_", " ").capitalize())
            ctk.CTkLabel(f, text=label_text, width=120, font=("Arial", 12, "bold"), anchor="w").pack(side="left", padx=10, pady=6)
            e = ctk.CTkEntry(f, width=80, font=("Arial", 12))
            e.insert(0, hotkeys.get(a, ""))
            e.pack(side="right", padx=10, pady=6)
            e.bind("<FocusOut>", lambda ev, ac=a: self.update_hotkey(ac))
            self.hotkey_entries[a] = e
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

        try_add('start', self.logic.start)
        try_add('refresh', self.refresh_macro)

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

        self.log("Hotkeys registered")

    def refresh_macro(self):
        self.logic.stop(); self.settings.load(); self.register_hotkeys(); self.log("Macro Refreshed")

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
        names = self.settings.get("move_names")
        new_name = self.move_entries[idx].get()
                                                              
        if new_name != names[idx]:
            names[idx] = new_name
            self.settings.set("move_names", names)
            self.clear_resolved_name(idx)
        self.update_gold_display()

    def refresh_resolved_label(self, idx):
        """Update the lock label for slot idx after a resolved name is saved."""
        if not hasattr(self, "resolved_labels") or idx >= len(self.resolved_labels):
            return
        resolved = self.settings.get("resolved_move_names", ["", "", ""])[idx]
        pos = self.settings.get("resolved_move_positions", [None, None, None])[idx]
        if resolved and pos:
            self.resolved_labels[idx].configure(
                text=f"🔒 {resolved}  ({pos[0]}, {pos[1]})", text_color="#4CAF50"
            )
        elif resolved:
            self.resolved_labels[idx].configure(text=f"🔒 {resolved}", text_color="#4CAF50")
        else:
            self.resolved_labels[idx].configure(text="unlocked", text_color="gray55")

    def clear_resolved_name(self, idx):
        """Clear the saved resolved name and position for slot idx."""
        resolved = list(self.settings.get("resolved_move_names", ["", "", ""]))
        resolved[idx] = ""
        self.settings.set("resolved_move_names", resolved)
        positions = list(self.settings.get("resolved_move_positions", [None, None, None]))
        positions[idx] = None
        self.settings.set("resolved_move_positions", positions)
        self.refresh_resolved_label(idx)
        self.log(f"Move {idx+1} lock cleared.")

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

    def toggle_node_card(self, node_idx, btn, details_frame):
        expanded = self.node_expanded.get(node_idx, False)
        if expanded:
            details_frame.pack_forget()
            btn.configure(text=f"Node {node_idx}   ▸")
        else:
            details_frame.pack(fill="x")
            btn.configure(text=f"Node {node_idx}   ▾")
        self.node_expanded[node_idx] = not expanded

    def save_node_timer(self, node_idx):
        if not hasattr(self, 'node_input_widgets') or node_idx not in self.node_input_widgets:
            return
        widgets = self.node_input_widgets[node_idx]
        try:
            hold_val = max(0.1, float(widgets["hold"].get()))
        except ValueError:
            hold_val = 3.0

        try:
            wait_val = max(0.0, float(widgets["wait"].get()))
        except ValueError:
            wait_val = 1.75

        steps = []
        for step in widgets["steps"]:
            try:
                seconds_val = max(0.0, float(step["entry"].get()))
            except ValueError:
                seconds_val = 0.0
            steps.append({"key": step["key"], "seconds": seconds_val})

        node_timers = dict(self.settings.get("node_timers", {}))
        node_timers[str(node_idx)] = {
            "mine_hold": hold_val,
            "mine_wait": wait_val,
            "steps": steps
        }
        self.settings.set("node_timers", node_timers)

    def save_sprinting_delay(self):
        if not hasattr(self, 'sprinting_delay_entry'):
            return
        try:
            val = max(0.0, float(self.sprinting_delay_entry.get()))
        except ValueError:
            val = 0.25
        self.settings.set("sprinting_delay", val)

    def reset_tundra_defaults(self):
        default_timers = {
            str(i): {"mine_hold": 3.0, "mine_wait": 1.75,
                      "steps": [{"key": k, "seconds": s} for k, s in DEFAULT_NODE_STEPS[str(i)]]}
            for i in range(1, 12)
        }
        self.settings.set("node_timers", default_timers)
        self.settings.set("color_tolerance", 25)
        self.settings.set("sprinting_delay", 0.25)

        if hasattr(self, 'sprinting_delay_entry'):
            self.sprinting_delay_entry.delete(0, "end")
            self.sprinting_delay_entry.insert(0, "0.25")

        if hasattr(self, 'node_input_widgets'):
            for i in range(1, 12):
                if i in self.node_input_widgets:
                    widgets = self.node_input_widgets[i]
                    widgets["hold"].delete(0, "end")
                    widgets["hold"].insert(0, "3.00")
                    widgets["wait"].delete(0, "end")
                    widgets["wait"].insert(0, "1.75")
                    for step, (_, seconds) in zip(widgets["steps"], DEFAULT_NODE_STEPS[str(i)]):
                        step["entry"].delete(0, "end")
                        step["entry"].insert(0, f"{seconds:.2f}")

        if hasattr(self, 'fishing_tolerance_slider'):
            self.fishing_tolerance_slider.set(25)
        if hasattr(self, 'fishing_tolerance_val_label'):
            self.fishing_tolerance_val_label.configure(text="25")

        self.log("Tundra Defaults & Node Timers Restored")

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

    def pick_region(self, key):
        self.root.withdraw()
        Overlay(lambda x1, y1, x2, y2: self.save_region(key, x1, y1, x2, y2))

    def save_region(self, key, x1, y1, x2, y2):
        self.root.deiconify(); self.settings.settings["regions"][key] = [x1, y1, x2, y2]; self.settings.save(); self.check_calibration()

    def pick_point(self, key):
        self.root.withdraw()
        PointSelector(lambda x, y: self.save_point(key, x, y))

    def save_point(self, key, x, y):
        self.root.deiconify()
        self.settings.settings["regions"][key] = [x, y]
        self.settings.save()
        self.check_calibration()

    def pick_color(self, key):
        self.root.withdraw()
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
        default_tols = {"gold": 33, "silver": 30, "bronze": 40}
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
        move_names = self.settings.get("move_names", ["", "", ""])
        move_stats = self.settings.get("move_stats", [0, 0, 0])
        for i in range(3):
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
        self.settings.set("total_gold", 0); self.settings.set("move_stats", [0, 0, 0]); self.log("Statistics Reset")
        self.update_gold_display()

    def toggle_overlays(self):
        if self.overlay_switch.get() == 1: self.show_overlays()
        else: self.hide_overlays()

    def show_overlays(self):
        self.hide_overlays()
        regions = self.settings.get("regions")
        
        if "Fishing" in self.root.title():
            relevant_keys = ["minigame_bar"]
        elif "Tundra" in self.root.title():
            relevant_keys = ["tundra_detection_region"]
        else:                  
            relevant_keys = ["score", "move_menu", "quest_region", "gold_clover_1", "gold_clover_2", "gold_clover_3"]

        colors = ["red", "green", "blue", "yellow", "cyan", "magenta"]
        for i, key in enumerate(relevant_keys):
            rect = regions.get(key)
            if rect and any(v != 0 for v in rect):
                self.overlays[key] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color=colors[i % len(colors)])

    def hide_overlays(self):
        for o in self.overlays.values(): o.destroy()
        self.overlays = {}