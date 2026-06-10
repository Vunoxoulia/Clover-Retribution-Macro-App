import customtkinter as ctk
import tkinter as tk
from settings import SpatialSettings
from overlay import Overlay, PointSelector, ColorPicker, PersistentOverlay
from updater import SpatialUpdater
from logic_library import LibraryLogic
from logic_tundra import TundraLogic
from logic_cave import CaveLogic
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
        self.root.geometry("1100x550")
        
        
        self.updater = SpatialUpdater(current_version, "Vunoxoulia", "Clover-Retribution-Macro-App")
        
        self.setup_ui()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        
        
        title = ctk.CTkLabel(self.root, text="Select a Macro", font=("Arial", 32, "bold"))
        title.pack(pady=(40, 10))
        
        
        version_lbl = ctk.CTkLabel(self.root, text=f"v{self.current_version}", font=("Arial", 12))
        version_lbl.pack()

        
        self.cards_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.cards_frame.pack(expand=True, fill="both", padx=20, pady=20)

        
        self.create_card("Library Macro", "Full automation for the\nSpatial Library.", "Launch", 
                         lambda: self.on_select("Library Macro", LibraryLogic, 
                                                tabs=["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"],
                                                tutorial_url="https://youtu.be/iWiS-saldnA"), 0)

        
        self.create_card("Tundra Mining", "Automated mining in\nthe Tundra region.", "Launch", 
                         lambda: self.on_select("Tundra Mining", TundraLogic, 
                                                tabs=["Main", "Hotkeys"],
                                                tutorial_url="https://youtu.be/RMn0v5-SDq4"), 1)

        
        self.create_card("Cave Mining", "Automated mining in\nthe Cave region.", "Coming Soon", None, 2)

        
        self.create_card("Devil Union", "Automated training for\nDevil Union abilities.", "Coming Soon", None, 3)

        
        footer = ctk.CTkFrame(self.root, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=10, padx=20)
        
        update_btn = ctk.CTkButton(footer, text="Check for Updates", width=150, command=self.check_updates)
        update_btn.pack(side="left", padx=(0, 10))

        patch_notes_btn = ctk.CTkButton(footer, text="Patch Notes", width=120, command=self.show_patch_notes, fg_color="#333333", hover_color="#444444")
        patch_notes_btn.pack(side="left")

        links_frame = ctk.CTkFrame(footer, fg_color="transparent")
        links_frame.pack(side="right", pady=10)

        yt_link = ctk.CTkLabel(links_frame, text="Youtube", font=("Arial", 12, "underline"), text_color="red")
        yt_link.pack(side="left", padx=5)
        yt_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.youtube.com/@Vunoxoulia"))

        ctk.CTkLabel(links_frame, text="", font=("Arial", 12)).pack(side="left")

        dc_link = ctk.CTkLabel(links_frame, text="discord", font=("Arial", 12, "underline"), text_color="#5865F2")
        dc_link.pack(side="left", padx=5)
        dc_link.bind("<Button-1>", lambda e: webbrowser.open("https://discord.com/invite/VRMB4djfzp"))

        ctk.CTkLabel(links_frame, text="", font=("Arial", 12)).pack(side="left")

        donate_link = ctk.CTkLabel(links_frame, text="Donate", font=("Arial", 12, "underline"), text_color="gold")
        donate_link.pack(side="left", padx=5)
        donate_link.bind("<Button-1>", lambda e: webbrowser.open("https://www.roblox.com/communities/34022778/The-Manga-Corner#!/store"))

    def show_patch_notes(self):
        import requests
        from tkinter import messagebox
        
        # Raw GitHub URL for PATCH_NOTES.txt
        notes_url = f"https://raw.githubusercontent.com/Vunoxoulia/Clover-Retribution-Macro-App/main/PATCH_NOTES.txt"
        
        try:
            response = requests.get(notes_url, timeout=5)
            if response.status_code == 200:
                notes_text = response.text
                
                # Create a popup window for notes
                notes_window = ctk.CTkToplevel(self.root)
                notes_window.title("Latest Patch Notes")
                notes_window.geometry("600x400")
                notes_window.attributes("-topmost", True)
                
                textbox = ctk.CTkTextbox(notes_window, font=("Consolas", 14))
                textbox.pack(expand=True, fill="both", padx=20, pady=20)
                textbox.insert("0.0", notes_text)
                textbox.configure(state="disabled")
            else:
                messagebox.showerror("Error", "Could not fetch patch notes from GitHub.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to GitHub: {e}")

    def check_updates(self):
        url, version = self.updater.check_for_updates()
        if url:
            self.updater.install_update(url)

    def create_card(self, title, description, button_text, command, column):
        card = ctk.CTkFrame(self.cards_frame, width=250, height=300, corner_radius=15)
        card.grid(row=0, column=column, padx=20, pady=10, sticky="nsew")
        card.grid_propagate(False)

        
        lbl_title = ctk.CTkLabel(card, text=title, font=("Arial", 20, "bold"))
        lbl_title.pack(pady=(20, 10))

        lbl_desc = ctk.CTkLabel(card, text=description, font=("Arial", 14), justify="center")
        lbl_desc.pack(pady=10, padx=10)

        btn = ctk.CTkButton(card, text=button_text, command=command)
        if command is None:
            btn.configure(state="disabled", fg_color="gray")
        btn.pack(side="bottom", pady=20)

        
        self.cards_frame.grid_columnconfigure(column, weight=1)

class SpatialGUI:
    def __init__(self, root, title="Spatial Macro", logic_class=LibraryLogic, on_back=None, tabs=None, tutorial_url="#"):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        self.root.geometry("450x600")
        self.tutorial_url = tutorial_url
        
        self.settings = SpatialSettings()
        self.logic = logic_class(self)
        self.overlays = {} 
        
        self.tabs_to_show = tabs if tabs else ["Main", "Settings", "Areas", "Clover Clicker", "Hotkeys", "Statistics"]
        
        
        self.DEFAULT_CLOVER_COLORS = {
            "gold": (251, 198, 108),
            "silver": (187, 197, 197),
            "bronze": (251, 197, 170)
        }
        
        
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        
        self.setup_ui()
        self.register_hotkeys()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.tabview = ctk.CTkTabview(self.root)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        for tab_name in self.tabs_to_show:
            self.tabview.add(tab_name)

        if "Main" in self.tabs_to_show: self.setup_main_tab()
        if "Settings" in self.tabs_to_show: self.setup_settings_tab()
        if "Areas" in self.tabs_to_show: self.setup_areas_tab()
        if "Clover Clicker" in self.tabs_to_show: self.setup_clover_tab()
        if "Hotkeys" in self.tabs_to_show: self.setup_hotkeys_tab()
        if "Statistics" in self.tabs_to_show: self.setup_statistics_tab()

    def setup_main_tab(self):
        tab = self.tabview.tab("Main")
        
        title_text = self.root.title().upper()
        title = ctk.CTkLabel(tab, text=title_text, font=("Arial", 24, "bold"))
        title.pack(pady=10)
        
        subtitle = ctk.CTkLabel(tab, text="made by Vunxoulia :3\n\nConverted to Python with love", font=("Arial", 12))
        subtitle.pack(pady=10)

        self.status_label = ctk.CTkLabel(tab, text="Status: <Not Started>", font=("Arial", 14))
        self.status_label.pack(pady=20)

        hotkeys = self.settings.get("hotkeys")
        self.start_btn = ctk.CTkButton(tab, text=f"Start Macro ({hotkeys['start'].upper()})", command=self.logic.start)
        self.start_btn.pack(pady=5)

        self.refresh_btn = ctk.CTkButton(tab, text=f"Reload Macro ({hotkeys['refresh'].upper()})", command=self.refresh_macro)
        self.refresh_btn.pack(pady=5)

        if self.on_back:
            self.back_btn = ctk.CTkButton(tab, text="Back to Menu", fg_color="transparent", border_width=2, command=self.go_back)
            self.back_btn.pack(pady=(20, 10))

        tutorial_link = ctk.CTkLabel(tab, text="Video Tutorial", font=("Arial", 16, "underline"), text_color="#5865F2", cursor="hand2")
        tutorial_link.pack(side="bottom", pady=10)
        tutorial_link.bind("<Button-1>", lambda e: webbrowser.open(self.tutorial_url))

    def go_back(self):
        self.logic.stop()
        keyboard.unhook_all()
        if self.on_back:
            self.on_back()

    def setup_settings_tab(self):
        tab = self.tabview.tab("Settings")
        
        ctk.CTkButton(tab, text="Move Selection Area (OCR)", command=lambda: self.pick_region("move_menu")).pack(pady=10)

        ctk.CTkLabel(tab, text="Move Names (for OCR):").pack(pady=5)
        self.move_entries = []
        for i in range(3):
            frame = ctk.CTkFrame(tab, fg_color="transparent")
            frame.pack(pady=2, fill="x", padx=40)
            
            entry = ctk.CTkEntry(frame, placeholder_text=f"Move {i+1} Name")
            entry.insert(0, self.settings.get("move_names")[i])
            entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
            entry.bind("<FocusOut>", lambda e, idx=i: self.update_move_name(idx))
            self.move_entries.append(entry)
            
            test_btn = ctk.CTkButton(frame, text="Test", width=50, 
                                     command=lambda idx=i: self.logic.test_move_ocr(idx))
            test_btn.pack(side="right")

    def setup_areas_tab(self):
        tab = self.tabview.tab("Areas")
        
        ctk.CTkLabel(tab, text="Gold Clover Move Status Areas", font=("Arial", 14, "bold")).pack(pady=5)
        
        ctk.CTkButton(tab, text="Gold Clover 1", command=lambda: self.pick_region("gold_clover_1")).pack(pady=2)
        ctk.CTkButton(tab, text="Gold Clover 2", command=lambda: self.pick_region("gold_clover_2")).pack(pady=2)
        ctk.CTkButton(tab, text="Gold Clover 3", command=lambda: self.pick_region("gold_clover_3")).pack(pady=2)
        
        ctk.CTkLabel(tab, text="\nMinigame UI Regions", font=("Arial", 14, "bold")).pack(pady=5)
        
        clover_frame = ctk.CTkFrame(tab, fg_color="transparent")
        clover_frame.pack(pady=2, fill="x", padx=40)
        ctk.CTkButton(clover_frame, text="Clover Region", command=lambda: self.pick_region("score")).pack(side="left", fill="x", expand=True)

        quest_frame = ctk.CTkFrame(tab, fg_color="transparent")
        quest_frame.pack(pady=2, fill="x", padx=40)
        ctk.CTkButton(quest_frame, text="Quest/Guide Region", command=lambda: self.pick_region("quest_region")).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(quest_frame, text="Test", width=50, command=self.logic.test_quest_ocr).pack(side="right")

        self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays)
        self.overlay_switch.pack(pady=10)

    def setup_clover_tab(self):
        tab = self.tabview.tab("Clover Clicker")
        
        ctk.CTkLabel(tab, text="Clover Target Colors", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.color_previews = {}
        self.color_labels = {}
        
        saved_colors = self.settings.get("clover_colors")
        if not saved_colors:
            saved_colors = self.DEFAULT_CLOVER_COLORS
        
        for clover in ["bronze", "silver", "gold"]:
            frame = ctk.CTkFrame(tab)
            frame.pack(pady=5, fill="x", padx=20)
            
            label = ctk.CTkLabel(frame, text=clover.capitalize(), width=60)
            label.pack(side="left", padx=5)
            
            color = saved_colors.get(clover, self.DEFAULT_CLOVER_COLORS[clover])
            color_hex = '#%02x%02x%02x' % tuple(color)
            
            preview = ctk.CTkFrame(frame, width=20, height=20, fg_color=color_hex)
            preview.pack(side="left", padx=5)
            self.color_previews[clover] = preview
            
            rgb_label = ctk.CTkLabel(frame, text=str(color), font=("Arial", 10))
            rgb_label.pack(side="left", padx=5)
            self.color_labels[clover] = rgb_label
            
            btn = ctk.CTkButton(frame, text="Pick", width=50, 
                               command=lambda c=clover: self.pick_color(c))
            btn.pack(side="right", padx=5)

        
        self.reset_colors_btn = ctk.CTkButton(tab, text="Reset to Default Colors", 
                                              fg_color="#A13333", hover_color="#732424",
                                              command=self.reset_clover_colors)
        self.reset_colors_btn.pack(pady=15)

        ctk.CTkLabel(tab, text="\nDetection Tolerance (Confidence)", font=("Arial", 14, "bold")).pack(pady=(10, 0))
        ctk.CTkLabel(tab, text="Lower = More strict (higher confidence)\nHigher = More loose", font=("Arial", 10)).pack(pady=5)
        
        tol_frame = ctk.CTkFrame(tab, fg_color="transparent")
        tol_frame.pack(pady=5, fill="x", padx=40)

        self.tolerance_slider = ctk.CTkSlider(tol_frame, from_=1, to=100, number_of_steps=99,
                                             command=self.update_tolerance)
        self.tolerance_slider.set(self.settings.get("color_tolerance"))
        self.tolerance_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.reset_tol_btn = ctk.CTkButton(tol_frame, text="Reset", width=50, 
                                          command=self.reset_tolerance)
        self.reset_tol_btn.pack(side="right")
        
        self.tolerance_val_label = ctk.CTkLabel(tab, text=f"Value: {int(self.tolerance_slider.get())}")
        self.tolerance_val_label.pack()

    def reset_tolerance(self):
        default_val = 25
        self.settings.set("color_tolerance", default_val)
        self.tolerance_slider.set(default_val)
        self.tolerance_val_label.configure(text=f"Value: {default_val}")
        self.log(f"Tolerance reset to {default_val}")

    def setup_hotkeys_tab(self):
        tab = self.tabview.tab("Hotkeys")
        ctk.CTkLabel(tab, text="Custom Hotkeys", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.hotkey_entries = {}
        hotkeys = self.settings.get("hotkeys")
        
        
        if "Tundra" in self.root.title():
            active_hotkeys = ["start", "refresh", "test_btn", "test_movement"]
        else:
            active_hotkeys = ["start", "refresh", "test_btn", "test_color"]
        
        for action in active_hotkeys:
            key = hotkeys.get(action, "")
            frame = ctk.CTkFrame(tab)
            frame.pack(pady=2, fill="x", padx=20)
            
            label_text = action.replace("_", " ").capitalize()
            if action == "refresh": label_text = "Reload Macro"
            if action == "test_btn" and "Tundra" in self.root.title(): label_text = "Test Interact OCR"
            if action == "test_movement": label_text = "Test Movement"
            
            ctk.CTkLabel(frame, text=label_text, width=100).pack(side="left", padx=5)
            
            entry = ctk.CTkEntry(frame, width=80)
            entry.insert(0, key)
            entry.pack(side="right", padx=5)
            entry.bind("<FocusOut>", lambda e, a=action: self.update_hotkey(a))
            self.hotkey_entries[action] = entry

        ctk.CTkButton(tab, text="Apply Hotkeys", command=self.register_hotkeys).pack(pady=20)

    def register_hotkeys(self):
        keyboard.unhook_all()
        hotkeys = self.settings.get("hotkeys")
        
        try:
            if hasattr(self.logic, 'test_detection'):
                keyboard.add_hotkey(hotkeys['test_btn'], self.logic.test_detection)
            
            if hasattr(self.logic, 'test_color_detection'):
                keyboard.add_hotkey(hotkeys['test_color'], self.logic.test_color_detection)
                
            if hasattr(self.logic, 'test_movement'):
                keyboard.add_hotkey(hotkeys['test_movement'], self.logic.test_movement)

            keyboard.add_hotkey(hotkeys['start'], self.logic.start)
            keyboard.add_hotkey(hotkeys['refresh'], self.refresh_macro)
            
            self.log("Hotkeys registered")
            
            if hasattr(self, 'start_btn') and self.start_btn.winfo_exists():
                self.start_btn.configure(text=f"Start Macro ({hotkeys['start'].upper()})")
            if hasattr(self, 'refresh_btn') and self.refresh_btn.winfo_exists():
                self.refresh_btn.configure(text=f"Reload Macro ({hotkeys['refresh'].upper()})")
        except Exception as e:
            self.log(f"Hotkey Error: {e}")

    def refresh_macro(self):
        self.logic.stop()
        self.settings.load()
        self.register_hotkeys()
        self.log("Macro Refreshed")

    def update_moves(self, val):
        self.settings.set("selected_option", int(val))

    def update_hotkey(self, action):
        key = self.hotkey_entries[action].get().lower()
        hotkeys = self.settings.get("hotkeys")
        hotkeys[action] = key
        self.settings.set("hotkeys", hotkeys)
        self.register_hotkeys() 
        self.log(f"Updated {action} hotkey to {key}")

    def update_move_name(self, idx):
        names = self.settings.get("move_names")
        names[idx] = self.move_entries[idx].get()
        self.settings.set("move_names", names)

    def update_tolerance(self, val):
        self.settings.set("color_tolerance", int(val))
        self.tolerance_val_label.configure(text=f"Value: {int(val)}")

    def log(self, message):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.configure(text=f"Status: {message}")
        print(message)

    def pick_point(self, key):
        self.root.withdraw()
        PointSelector(lambda x, y: self.save_point(key, x, y))

    def save_point(self, key, x, y):
        self.root.deiconify()
        self.settings.settings["positions"][key] = [x, y]
        self.settings.save()
        self.root.after(100, lambda: self.log(f"Saved {key} at {x}, {y}"))

    def pick_region(self, key):
        self.root.withdraw()
        Overlay(lambda x1, y1, x2, y2: self.save_region(key, x1, y1, x2, y2))

    def save_region(self, key, x1, y1, x2, y2):
        self.root.deiconify()
        self.settings.settings["regions"][key] = [x1, y1, x2, y2]
        self.settings.save()
        self.root.after(100, lambda: self.log(f"Saved {key} region"))
        if self.overlay_switch.get() == 1:
            self.show_overlays()

    def pick_color(self, clover):
        self.root.withdraw()
        ColorPicker(lambda color: self.save_color(clover, color))

    def save_color(self, clover, color):
        self.root.deiconify()
        colors = self.settings.get("clover_colors")
        if not colors:
            colors = {}
        colors[clover] = list(color)
        
        self.settings.set("clover_colors", colors)
        self.settings.save()
        
        color_hex = '#%02x%02x%02x' % tuple(color)
        self.color_previews[clover].configure(fg_color=color_hex)
        self.color_labels[clover].configure(text=str(list(color)))
        self.root.after(100, lambda: self.log(f"Saved {clover} color: {color}"))

    def reset_clover_colors(self):
        
        default_mapping = {k: list(v) for k, v in self.DEFAULT_CLOVER_COLORS.items()}
        
        self.settings.set("clover_colors", default_mapping)
        self.settings.save()
        
        for clover, color in default_mapping.items():
            color_hex = '#%02x%02x%02x' % tuple(color)
            self.color_previews[clover].configure(fg_color=color_hex)
            self.color_labels[clover].configure(text=str(color))
            
        self.log("Colors reset to defaults.")

    def exit_app(self):
        self.logic.stop()
        self.root.destroy()
        os._exit(0)

    def setup_statistics_tab(self):
        tab = self.tabview.tab("Statistics")
        
        ctk.CTkLabel(tab, text="Training Statistics", font=("Arial", 20, "bold")).pack(pady=20)
        
        self.xp_label = ctk.CTkLabel(tab, text=f"Total Gold Used: {self.settings.get('total_xp', 0)}", font=("Arial", 16, "bold"))
        self.xp_label.pack(pady=(10, 20))
        
        self.move_xp_labels = []
        move_names = self.settings.get("move_names", ["", "", ""])
        move_stats = self.settings.get("move_stats", [0, 0, 0])
        
        for i in range(3):
            name = move_names[i] if move_names[i] else f"Move {i+1}"
            lbl = ctk.CTkLabel(tab, text=f"{name}: {move_stats[i]} Gold", font=("Arial", 14))
            lbl.pack(pady=2)
            self.move_xp_labels.append(lbl)

        self.reset_xp_btn = ctk.CTkButton(tab, text="Reset Statistics", 
                                         fg_color="#A13333", hover_color="#732424",
                                         command=self.reset_xp)
        self.reset_xp_btn.pack(pady=30)

    def update_xp_display(self):
        xp = self.settings.get("total_xp", 0)
        move_stats = self.settings.get("move_stats", [0, 0, 0])
        move_names = self.settings.get("move_names", ["", "", ""])

        if hasattr(self, 'xp_label') and self.xp_label.winfo_exists():
            self.xp_label.configure(text=f"Total Gold Used: {xp}")
        
        if hasattr(self, 'move_xp_labels'):
            for i, lbl in enumerate(self.move_xp_labels):
                if lbl.winfo_exists():
                    name = move_names[i] if move_names[i] else f"Move {i+1}"
                    lbl.configure(text=f"{name}: {move_stats[i]} Gold")

    def reset_xp(self):
        self.settings.set("total_xp", 0)
        self.settings.set("move_stats", [0, 0, 0])
        self.update_xp_display()
        self.log("Statistics Reset")

    def toggle_overlays(self):
        if self.overlay_switch.get() == 1:
            self.show_overlays()
        else:
            self.hide_overlays()

    def show_overlays(self):
        self.hide_overlays() 
        regions = self.settings.get("regions")
        colors = ["red", "green", "blue", "yellow", "cyan"]
        for i, (key, rect) in enumerate(regions.items()):
            if any(v != 0 for v in rect):
                color = colors[i % len(colors)]
                self.overlays[key] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color=color)

    def hide_overlays(self):
        for overlay in self.overlays.values():
            overlay.destroy()
        self.overlays = {}

