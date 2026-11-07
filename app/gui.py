import customtkinter as ctk
import tkinter as tk
from settings import SpatialSettings
from overlay import Overlay, PointSelector, ColorPicker, PersistentOverlay
from updater import SpatialUpdater
from logic_library import LibraryLogic
from logic_mining import MiningLogic
from logic_fishing import FishingLogic
import keyboard
from theme import c
from ui_style import dialog_keys, FONT, big_toggle, style_toggle, save_while_typing, sound_picker, fast_scroll_frame, seconds_combo, help_box, general_settings, StepCard, Checklist, OptionGroup, CARD, RunPanel, msg_kind
import os
import links
import time
import threading
import collections
from gui_library import LibraryPages
from gui_routes import RoutePages
from gui_popups import PopupPages

FAIL_MSG = "Capture failed - drag a bigger box."


def open_log_file(parent):
    import applog
    from tkinter import messagebox
    if not applog.open_log():
        messagebox.showinfo("Log", f"No log file yet. It will be here: {applog.log_path()}", parent=parent)


class MacroSelector:
    def __init__(self, root, on_select, current_version):
        self.root = root
        self.on_select = on_select
        self.current_version = current_version
        self.root.title("VunVun's Macro Hub")
        fit_window(self.root, 820, 520, 600, 400)

        self.updater = SpatialUpdater(current_version, "Vunoxoulia", "Clover-Retribution-Macro-App")
        self.frame = ctk.CTkFrame(self.root, fg_color="transparent", corner_radius=0)
        self.frame.pack(fill="both", expand=True)
        self.setup_ui()

    def show(self):
        self.root.title("VunVun's Macro Hub")
        fit_window(self.root, 820, 520, 600, 400)
        self.frame.pack(fill="both", expand=True)
        if getattr(self, "_addons_dirty", False):
            self._addons_dirty = False
            self.redraw_menu()
            return
        self._refresh_live()

    def redraw_menu(self):
        for w in self.frame.winfo_children():
            w.destroy()
        self.setup_ui()

    def _refresh_live(self):
        target = self._continue_target()
        btn = getattr(self, "_continue_btn", None)
        if btn is not None and btn.winfo_exists():
            if target:
                btn.configure(text=f"▶  Continue: {target[0]}", command=target[1])
                if not btn.winfo_manager():
                    btn.pack(side="right", before=self._every_btn)
            else:
                btn.pack_forget()
        from logic_events import WATCHER
        top, lbl = getattr(self, "_badges", {}).get("Event Notifier", (None, None))
        if top is not None and top.winfo_exists():
            if WATCHER.running and lbl is None:
                lbl = ctk.CTkLabel(top, text="on", font=(FONT, 11, "bold"), fg_color="#14432a", text_color="#7ee0a6",
                                   corner_radius=6, width=34, height=20)
                lbl.pack(side="right")
            elif not WATCHER.running and lbl is not None:
                lbl.destroy()
                lbl = None
            self._badges["Event Notifier"] = (top, lbl)
        self.root.after(30, self._fill_status)

    def launch_library(self):
        SpatialSettings().set("last_macro", "library_new")
        self.on_select("Library Macro", LibraryLogic, tabs=["Main", "Setup", "Options", "Hotkeys", "Statistics"],
                       tutorial_url="video_library")

    def open_theme_editor(self):
        import theme
        from tkinter import colorchooser
        old = getattr(self, "_theme_win", None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        win = ctk.CTkToplevel(self.root)
        self._theme_win = win
        win.title("Custom theme")
        dialog_keys(win)
        win.geometry("420x290")
        win.resizable(False, False)
        win.transient(self.root)
        win.after(150, win.lift)
        cols = theme.custom_colors()
        card = ctk.CTkFrame(win, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
        card.pack(fill="both", expand=True, padx=12, pady=12)
        t = ctk.CTkLabel(card, text="Custom theme", font=(FONT, 14, "bold"), text_color="#e6b84f")
        t.pack(anchor="w", padx=10, pady=(8, 2))
        help_box(card, "Pick three colours. Backgrounds and darker shades are worked out from the main colour. "
                       "Save & use switches to the Custom theme (it stays in the theme list).", t)
        swatches = {}
        for key, label in (("primary", "Main colour (buttons, selected page)"),
                           ("hover", "When the mouse is on a button"),
                           ("accent", "Accent (titles, gold lines)")):
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=10, pady=4)
            sw = tk.Frame(row, width=26, height=26, bg=cols[key], highlightthickness=1)
            sw.pack(side="left")
            ctk.CTkLabel(row, text=label, font=(FONT, 12)).pack(side="left", padx=8)

            def choose(k=key, sw=sw, label=label):
                got = colorchooser.askcolor(color=cols[k], parent=win, title=label)[1]
                if got:
                    cols[k] = got.lower()
                    sw.configure(bg=cols[k])
            ctk.CTkButton(row, text="Pick", width=60, height=28, font=(FONT, 12), fg_color="#34463d",
                          hover_color="#2a3a33", command=choose).pack(side="right")
            swatches[key] = sw

        def reset():
            cols.update(theme.CUSTOM_DEFAULT)
            for k, sw in swatches.items():
                sw.configure(bg=cols[k])

        def save():
            theme.save_custom(cols)
            win.destroy()
            self.set_theme("Custom")
        bottom = ctk.CTkFrame(card, fg_color="transparent"); bottom.pack(fill="x", padx=10, pady=(8, 10))
        ctk.CTkButton(bottom, text="Reset", width=80, height=28, font=(FONT, 12), fg_color="#34463d",
                      hover_color="#2a3a33", command=reset).pack(side="left")
        ctk.CTkButton(bottom, text="Save & use", width=110, height=28, font=(FONT, 12, "bold"),
                      fg_color="#1c8f52", hover_color="#16743f", command=save).pack(side="right")

    def set_theme(self, name):
        import theme
        theme.apply(name, save=True)
        self.root.configure(fg_color=ctk.ThemeManager.theme["CTk"]["fg_color"])
        for w in self.frame.winfo_children():
            w.destroy()
        self.setup_ui()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        head = ctk.CTkFrame(self.frame, fg_color="transparent")
        head.pack(fill="x", padx=32, pady=(26, 4))
        ctk.CTkLabel(head, text="Select a macro", font=(FONT, 26, "bold"), text_color="#e6b84f").pack(side="left")
        ver = ctk.CTkLabel(head, text=f"v{self.current_version}", font=(FONT, 12), text_color="#a39d86")
        ver.pack(side="left", padx=10, pady=(8, 0))
        clicks = []

        def ver_click(_e=None):
            now = time.time()
            clicks[:] = [t for t in clicks if now - t < 2.0] + [now]
            if len(clicks) >= 5:
                clicks.clear()
                self.enter_access_key()
        ver.bind("<Button-1>", ver_click)
        target = self._continue_target()
        self._continue_btn = ctk.CTkButton(head, text="", height=32, font=(FONT, 13, "bold"),
                                           fg_color="#1c8f52", hover_color="#16743f")
        if target:
            self._continue_btn.configure(text=f"▶  Continue: {target[0]}", command=target[1])
            self._continue_btn.pack(side="right")
        self._every_btn = ctk.CTkButton(head, text="⚙  Every macro", width=120, height=32, font=(FONT, 12),
                                        fg_color="#2a3a33", hover_color="#34463d", command=self.open_general)
        self._every_btn.pack(side="right", padx=8)

        self.cards_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.cards_frame.pack(expand=True, fill="both", padx=20, pady=(6, 4))
        from logic_events import WATCHER
        cards = [
            ("Library", "📚", "Auto spell clover mastery", self.launch_library),
            ("Skill", "⚔", "AFK rotation, combos and item use", self.launch_smart),
            ("Event Notifier", "🔔", "Posts chat events to Discord", self.launch_events),
            ("Mining", "⛏", "Mining away", self.launch_mining),
            ("Fishing", "🎣", "Auto fishy", self.launch_fishing),
        ]
        import entitlements
        self._addon_names = [a["name"] for a in entitlements.known_addons()]
        for a in entitlements.known_addons():
            cards.append((a.get("title") or a["name"], a.get("icon") or "✦", a.get("desc") or "",
                          lambda n=a["name"]: self.launch_addon(n)))
        self._status_labels = {}
        self._badges = {}
        for k, (title, icon, desc, cmd) in enumerate(cards):
            badge = "on" if title == "Event Notifier" and WATCHER.running else None
            self.create_card(title, icon, desc, cmd, k // 3, k % 3, badge)
        self.root.after(30, self._fill_status)
        self.root.after(300, self._refresh_addons)

        bar = ctk.CTkFrame(self.frame, fg_color="transparent")
        bar.pack(fill="x", side="bottom", pady=(4, 14), padx=24)
        bar.grid_columnconfigure(1, weight=1)
        footer = ctk.CTkFrame(bar, fg_color="transparent")
        footer.grid(row=0, column=0, sticky="w")
        small = dict(height=28, font=(FONT, 12), corner_radius=6)
        ctk.CTkButton(footer, text="↻  Check for updates", width=150, fg_color="#2a3a33", hover_color="#34463d",
                      command=self.check_updates, **small).pack(side="left", padx=(0, 6))
        ctk.CTkButton(footer, text="Patch notes", width=100, fg_color="#2a3a33", hover_color="#34463d",
                      command=self.show_patch_notes, **small).pack(side="left")
        log_menu = tk.Menu(self.frame, tearoff=0, bg=c("#15201b"), fg=c("#e8dfc5"), activebackground=c("#1c8f52"),
                           activeforeground="#ffffff")
        log_menu.add_command(label="  Open log", command=self.open_log)
        log_menu.add_command(label="  Save debug report...", command=self.save_debug_report)
        log_btn = ctk.CTkButton(footer, text="Log ▾", width=70, fg_color="#2a3a33", hover_color="#34463d", **small)
        log_btn.configure(command=lambda: log_menu.tk_popup(log_btn.winfo_rootx(),
                                                            log_btn.winfo_rooty() - 2 * 26))
        log_btn.pack(side="left", padx=(6, 0))
        import theme
        edit_custom = "Edit custom..."

        def picked(v):
            if v == edit_custom:
                pick.set(theme.current())
                self.open_theme_editor()
            else:
                self.set_theme(v)
        pick = ctk.CTkOptionMenu(footer, values=list(theme.THEMES) + [edit_custom], width=110, height=28,
                                 font=(FONT, 12), fg_color="#2a3a33", button_color="#34463d",
                                 button_hover_color="#22302a", command=picked)
        pick.set(theme.current())
        pick.pack(side="left", padx=6)

        links_frame = ctk.CTkFrame(bar, fg_color="transparent")
        links_frame.grid(row=0, column=1, sticky="e")

        def fit_footer(_e=None):
            try:
                one_line = footer.winfo_reqwidth() + links_frame.winfo_reqwidth() + 12 <= bar.winfo_width()
                where = dict(row=0, column=1, sticky="e", pady=0) if one_line else \
                    dict(row=1, column=0, columnspan=2, sticky="e", pady=(6, 0))
                if links_frame.grid_info().get("row") != where["row"]:
                    links_frame.grid_forget()
                    links_frame.grid(**where)
            except Exception:
                pass
        for part in (bar, footer, links_frame):
            tk.Misc.bind(part, "<Configure>", fit_footer, "+")
        link_btn = dict(small, width=96, fg_color="#2a3a33")
        ctk.CTkButton(links_frame, text="▶  YouTube", hover_color="#8f2a22", text_color="#ff6b6b", **link_btn,
                      command=lambda: links.open_link("youtube")).pack(side="left", padx=3)
        ctk.CTkButton(links_frame, text="Discord", hover_color="#c99a2e", text_color="#e6b84f", **link_btn,
                      command=lambda: links.open_link("discord")).pack(side="left", padx=3)

        donate_menu = tk.Menu(self.frame, tearoff=0, bg=c("#15201b"), fg=c("#e8dfc5"), activebackground=c("#1c8f52"),
                              activeforeground="#ffffff", font=(FONT, 12))
        donate_menu.add_command(label="  Robux  (Roblox store)", command=lambda: links.open_link("donate_robux"))
        donate_menu.add_command(label="  Real money  (Ko-fi)", command=lambda: links.open_link("donate_money"))
        donate_btn = ctk.CTkButton(links_frame, text="♥  Donate ▾", hover_color="#c99a2e", text_color="#e6b84f",
                                   **link_btn)
        donate_btn.configure(command=lambda: donate_menu.tk_popup(donate_btn.winfo_rootx(),
                                                                  donate_btn.winfo_rooty() + donate_btn.winfo_height()))
        donate_btn.pack(side="left", padx=3)
        bar.after_idle(fit_footer)
        if not SpatialSettings().get("tour_done", False):
            self.root.after(500, self.show_tips)

    TIPS = (
        ("Pick a macro", "Press Launch on a card. The line under each card says if that macro is ready, or how "
                         "many setup steps are left."),
        ("Set it up in order", "Inside a macro, open Setup first and do the steps from the top. ✓ = done, "
                               "✗ = missing (it says what to do), · = nothing checks that step - use its Test."),
        ("Start and watch", "Main has Start / Stop (F6), what the macro is doing and the last messages. If it stops "
                            "with something missing, 'Fix it' opens the step to fix."),
        ("Shared settings", "Pop Up, Events, Hotkeys and General change every macro. Colours: the theme list at the "
                            "bottom of this menu. These tips come back with 'Show tips again' on the General page."),
    )

    def show_tips(self):
        old = getattr(self, "_tips_win", None)
        if old is not None and old.winfo_exists():
            return
        win = self._tips_win = ctk.CTkToplevel(self.root)
        win.title("Quick tips")
        dialog_keys(win)
        win.geometry("460x230")
        win.resizable(False, False)
        win.transient(self.root)
        win.after(150, win.lift)
        state = {"i": 0}
        head = ctk.CTkLabel(win, text="", font=(FONT, 16, "bold"), text_color="#e6b84f", anchor="w")
        head.pack(fill="x", padx=18, pady=(16, 4))
        body = ctk.CTkLabel(win, text="", font=(FONT, 13), anchor="w", justify="left", wraplength=420)
        body.pack(fill="both", expand=True, padx=18)
        row = ctk.CTkFrame(win, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(4, 14))
        count = ctk.CTkLabel(row, text="", font=(FONT, 12), text_color="#a39d86")
        count.pack(side="left", padx=4)

        def done():
            SpatialSettings().set("tour_done", True)
            win.destroy()

        def show():
            title, text = self.TIPS[state["i"]]
            head.configure(text=title)
            body.configure(text=text)
            count.configure(text=f"{state['i'] + 1} of {len(self.TIPS)}")
            nxt.configure(text="Done" if state["i"] == len(self.TIPS) - 1 else "Next  →")

        def next_tip():
            if state["i"] >= len(self.TIPS) - 1:
                done()
            else:
                state["i"] += 1
                show()
        nxt = ctk.CTkButton(row, text="", width=100, height=30, fg_color="#1c8f52", hover_color="#16743f",
                            command=next_tip)
        nxt.pack(side="right")
        ctk.CTkButton(row, text="Skip", width=70, height=30, fg_color="#34463d", hover_color="#2a3a33",
                      command=done).pack(side="right", padx=6)
        win.protocol("WM_DELETE_WINDOW", done)
        show()

    def launch_events(self):
        from gui_events import EventsOnlyLogic
        SpatialSettings().set("last_macro", "events")
        self.on_select("Event Notifier", EventsOnlyLogic, tabs=["Events"])

    def launch_smart(self):
        from gui_smart import SmartMacroGUI
        SpatialSettings().set("last_macro", "skill")
        self.on_select("Skill Macro", None, gui_class=SmartMacroGUI)

    def launch_mining(self):
        SpatialSettings().set("last_macro", "mining")
        self.on_select("Mining Macro", MiningLogic, tabs=["Main", "Setup", "Options", "Hotkeys"], tutorial_url="video_mining")

    def launch_fishing(self):
        SpatialSettings().set("last_macro", "fishing")
        self.on_select("Fishing Macro", FishingLogic, tabs=["Main", "Setup", "Options", "Hotkeys"],
                       tutorial_url="video_fishing")

    def _refresh_addons(self, done=None):
        def work():
            import entitlements
            try:
                addons, why = entitlements.refresh_addons()
            except Exception as e:
                addons, why = None, str(e)
            self.root.after(0, lambda: after(addons, why))

        def after(addons, why):
            if addons is not None and [a["name"] for a in addons] != getattr(self, "_addon_names", []):
                if self.frame.winfo_exists() and self.frame.winfo_manager():
                    self.redraw_menu()
                else:
                    self._addons_dirty = True
            if done:
                done(addons or [], why)
        threading.Thread(target=work, daemon=True).start()

    def launch_addon(self, name):
        import entitlements
        title = entitlements.addon_title(name)
        lbl = getattr(self, "_status_labels", {}).get(title)
        if lbl is not None and lbl.winfo_exists():
            lbl.configure(text="Opening... (can take up to a minute)", text_color="#e6b84f")

        def work():
            mod, why = entitlements.load_addon(name)
            self.root.after(0, lambda: opened(mod, why))

        def opened(mod, why):
            from tkinter import messagebox
            if lbl is not None and lbl.winfo_exists():
                lbl.configure(text="")
            if mod is not None and hasattr(mod, "launch"):
                SpatialSettings().set("last_macro", f"addon:{name}")
                mod.launch(self)
                return
            messagebox.showwarning(title, f"Couldn't open {title}: {why}.\n\nIf your key was reset or turned off, "
                                          "ask for a new one.", parent=self.root)
            self._refresh_addons()
        threading.Thread(target=work, daemon=True).start()

    def enter_access_key(self):
        import entitlements
        win = ctk.CTkToplevel(self.root)
        win.title("Access key")
        win.geometry("460x210")
        win.transient(self.root); win.after(150, win.lift)
        ctk.CTkLabel(win, text="Enter your access key", font=(FONT, 15, "bold"),
                     text_color="#e6b84f").pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(win, text="This ties the key to this PC. Swapped your motherboard or reinstalled Windows? "
                               "Ask for a reset.", font=(FONT, 12), text_color="#a39d86",
                     justify="left", wraplength=420).pack(anchor="w", padx=16)
        entry = ctk.CTkEntry(win, width=420, font=(FONT, 13)); entry.pack(padx=16, pady=10)
        entry.insert(0, entitlements.read_key())
        status = ctk.CTkLabel(win, text="", font=(FONT, 12, "bold"), wraplength=420); status.pack(padx=16)
        row = ctk.CTkFrame(win, fg_color="transparent"); row.pack(pady=8)
        btn = ctk.CTkButton(row, text="Save & check", width=130, fg_color="#1c8f52", hover_color="#16743f")

        def checked(addons, why):
            if not win.winfo_exists():
                return
            btn.configure(state="normal")
            mine = [a for a in addons if not a.get("dev")]
            if mine:
                status.configure(text="Key accepted: " + ", ".join(a.get("title") or a["name"] for a in mine),
                                 text_color="#7ee0a6")
                win.after(900, win.destroy)
            elif not entry.get().strip():
                status.configure(text="Key removed.", text_color="#a39d86")
            else:
                status.configure(text=f"Not accepted: {why}.", text_color="#f08a7e")

        def apply():
            entitlements.save_key(entry.get())
            btn.configure(state="disabled")
            status.configure(text="Checking with the server... (can take up to a minute)", text_color="#e6b84f")
            self._refresh_addons(done=checked)
        btn.configure(command=apply)
        btn.pack(side="left", padx=4)
        dialog_keys(win, ok=lambda: btn.cget("state") == "normal" and apply())
        ctk.CTkButton(row, text="Close", width=90, fg_color="#34463d", hover_color="#2a3a33",
                      command=win.destroy).pack(side="left", padx=4)

    LAST_NAMES = {"library_new": "Library", "skill": "Skill",
                  "events": "Event Notifier", "mining": "Mining", "fishing": "Fishing"}

    def _continue_target(self):
        last = SpatialSettings().get("last_macro") or ""
        if last.startswith("addon:"):
            import entitlements
            name = last[6:]
            if name in [a["name"] for a in entitlements.known_addons()]:
                return entitlements.addon_title(name), lambda: self.launch_addon(name)
            return None
        fn = {"library_new": self.launch_library, "skill": self.launch_smart, "events": self.launch_events, "mining": self.launch_mining,
              "fishing": self.launch_fishing}.get(last)
        return (self.LAST_NAMES[last], fn) if fn else None

    def setup_status(self, key):
        if key == "library":
            cls = LibraryLogic
        elif key == "fishing":
            cls = FishingLogic
        elif key == "skill":
            from logic_smart import SmartMacroLogic as cls
        elif key == "mining":
            cls = MiningLogic
        else:
            return None
        try:
            if key == "mining":
                from route_nav import RouteNav
                logic = MiningLogic.__new__(MiningLogic)
                RouteNav.__init__(logic, _CheckOnly(self.root))
                return logic.setup_problems()
            return cls(_CheckOnly(self.root)).setup_problems()
        except Exception as e:
            print(f"Couldn't check the {key} setup: {e}")
            return None

    def _fill_status(self):
        keys = {"Library": "library", "Mining": "mining", "Fishing": "fishing", "Skill": "skill"}
        todo = [(title, lbl, keys[title]) for title, lbl in self._status_labels.items()
                if title in keys and lbl.winfo_exists()]

        def work():
            results = [(lbl, self.setup_status(key)) for _, lbl, key in todo]
            try:
                self.root.after(0, lambda: show(results))
            except Exception:
                pass

        def show(results):
            for lbl, probs in results:
                if probs is None or not lbl.winfo_exists():
                    continue
                if not probs:
                    text, col = "✓ Ready", "#1f9d55"
                elif any(p.get("block") for p in probs):
                    text, col = f"✗ Not set up ({len(probs)} to fix)", "#f08a7e"
                else:
                    text, col = f"● {len(probs)} step{'s' if len(probs) > 1 else ''} left", "#e6b84f"
                lbl.configure(text=text, text_color=col)
        threading.Thread(target=work, daemon=True).start()

    def open_general(self):
        old = getattr(self, "_general_win", None)
        if old is not None and old.winfo_exists():
            old.lift()
            return
        win = self._general_win = ctk.CTkToplevel(self.root)
        win.title("Settings for every macro")
        dialog_keys(win)
        win.geometry("520x360")
        win.transient(self.root)
        win.after(150, win.lift)
        general_settings(fast_scroll_frame(win, padx=6, pady=6), SpatialSettings())

    def open_log(self):
        open_log_file(self.root)

    def save_debug_report(self):
        from tkinter import filedialog, messagebox
        import report
        name = time.strftime("VunVun_debug_report_%Y-%m-%d_%H%M.zip")
        path = filedialog.asksaveasfilename(parent=self.root, title="Save debug report", initialfile=name,
                                            defaultextension=".zip", filetypes=[("Zip file", "*.zip")],
                                            initialdir=os.path.join(os.path.expanduser("~"), "Desktop"))
        if not path:
            return
        try:
            put = report.save_report(path, SpatialSettings().settings, self.current_version)
        except Exception as e:
            messagebox.showerror("Debug report", f"Couldn't save it: {e}", parent=self.root)
            return
        messagebox.showinfo("Debug report", "Saved: " + path + "\n\nIt has: " + ", ".join(put) +
                            ".\nSend this file with your bug report.", parent=self.root)

    def show_patch_notes(self):
        import requests
        from tkinter import messagebox
        notes_url = "https://raw.githubusercontent.com/Vunoxoulia/Clover-Retribution-Macro-App/main/docs/PATCH_NOTES.txt"
        try:
            response = requests.get(notes_url, timeout=5)
            if response.status_code == 200:
                notes_window = ctk.CTkToplevel(self.root)
                notes_window.title("Latest Patch Notes")
                dialog_keys(notes_window)
                notes_window.geometry("600x400")
                notes_window.attributes("-topmost", True)
                textbox = ctk.CTkTextbox(notes_window, font=("Consolas", 14), fg_color="#15201b", text_color="#f3ecd8")
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
        card = ctk.CTkFrame(self.cards_frame, corner_radius=10, fg_color="#15201b", border_color="#2a3a33",
                            border_width=1)
        card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text=icon, width=38, height=38, corner_radius=8, fg_color="#123326",
                     text_color="#7ed3a4", font=("Segoe UI Emoji", 18)).pack(side="left")
        title_lbl = ctk.CTkLabel(top, text=title, font=(FONT, 15, "bold"), text_color="#ffffff", justify="left",
                                 anchor="w")
        title_lbl.pack(side="left", padx=10, fill="x", expand=True)
        lbl = None
        if badge:
            lbl = ctk.CTkLabel(top, text=badge, font=(FONT, 11, "bold"), fg_color="#14432a", text_color="#7ee0a6",
                               corner_radius=6, width=34, height=20)
            lbl.pack(side="right")
        self._badges[title] = (top, lbl)
        desc_lbl = ctk.CTkLabel(card, text=description, font=(FONT, 12), text_color="#a39d86", justify="left",
                                anchor="w", wraplength=200)
        desc_lbl.pack(fill="x", padx=14)

        def wrap(_e=None):
            if not (title_lbl.winfo_exists() and desc_lbl.winfo_exists()):
                return
            room = max(60, card.winfo_width() - 28)
            badge_w = 38 if lbl is not None else 0
            title_lbl.configure(wraplength=max(50, room - 62 - badge_w))
            desc_lbl.configure(wraplength=room)
        tk.Misc.bind(card, "<Configure>", wrap, "+")
        status = ctk.CTkLabel(card, text="", font=(FONT, 12, "bold"), anchor="w", height=18)
        status.pack(fill="x", padx=14, pady=(4, 0))
        self._status_labels[title] = status
        btn = ctk.CTkButton(card, text="Launch", command=command, height=30,
                            font=(FONT, 13, "bold"), fg_color="#1c8f52", hover_color="#16743f")
        if command is None:
            btn.configure(state="disabled", fg_color="#2a3a33", text_color_disabled="#857f6c")
        btn.pack(side="bottom", fill="x", padx=14, pady=14)
        self.cards_frame.grid_columnconfigure(column, weight=1, uniform="card")
        self.cards_frame.grid_rowconfigure(row, weight=1, uniform="card")

def work_area():
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0):
            return r.left, r.top, r.right, r.bottom
    except Exception:
        pass
    return None


def fit_window(root, w, h, min_w, min_h):
    area = work_area()
    if area:
        try:
            scale = float(root._get_window_scaling())
        except Exception:
            scale = 1.0
        room_w = (area[2] - area[0] - 16) / scale
        room_h = (area[3] - area[1] - 45) / scale
        w, h = min(w, room_w), min(h, room_h)
        min_w, min_h = min(min_w, room_w), min(min_h, room_h)
    root.minsize(int(min_w), int(min_h))
    root.geometry(f"{int(w)}x{int(h)}")
    if area:
        try:
            root.update_idletasks()
            x, y = root.winfo_x(), root.winfo_y()
            pw, ph = int(w * scale) + 16, int(h * scale) + 45
            nx = max(area[0], min(x, area[2] - pw))
            ny = max(area[1], min(y, area[3] - ph))
            if (nx, ny) != (x, y):
                root.geometry(f"+{nx}+{ny}")
        except Exception:
            pass
    return int(w)


class _CheckOnly:
    def __init__(self, root):
        self.root = root
        self.settings = SpatialSettings()

    def log(self, *a, **k):
        pass

    def __getattr__(self, name):
        return lambda *a, **k: None


NAV_ICONS = {
    "Main": "⌂", "Settings": "✎", "Setup": "✎", "Minigame": "✿", "Areas": "✿", "Clover Clicker": "✿",
    "Fishing Settings": "✎", "Pop Up": "❐", "Events": "♪", "Hotkeys": "⌨", "Statistics": "▤",
    "Routes": "⤳", "Moves": "✦",
    "Rotation": "⟳", "Skill Combo": "⇉", "Items": "❖", "Timers": "⧖", "General": "⚙", "Options": "≡", "Logs": "▤",
}
SIDEBAR_WIDE, SIDEBAR_NARROW = 150, 56
_ICON_CACHE = {}


def nav_icon(ch, color, size=16):
    key = (ch, color, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    img = None
    try:
        from PIL import Image, ImageDraw, ImageFont
        fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        path = next(os.path.join(fonts, f) for f in ("seguisym.ttf", "segoeui.ttf")
                    if os.path.exists(os.path.join(fonts, f)))
        big = size * 3
        font = ImageFont.truetype(path, int(big * 0.8))
        pic = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        d = ImageDraw.Draw(pic)
        x1, y1, x2, y2 = d.textbbox((0, 0), ch, font=font)
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        d.text(((big - (x2 - x1)) / 2 - x1, (big - (y2 - y1)) / 2 - y1), ch, font=font, fill=rgb + (255,))
        pic = pic.resize((size, size), Image.LANCZOS)
        img = ctk.CTkImage(light_image=pic, dark_image=pic, size=(size, size))
    except Exception:
        img = None
    _ICON_CACHE[key] = img
    return img

class SidebarNav:
    def __init__(self, root, title):
        self.root = root
        self.sidebar = ctk.CTkFrame(root, width=SIDEBAR_WIDE, corner_radius=0, fg_color="#0c1310")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        top = ctk.CTkFrame(self.sidebar, fg_color="transparent"); top.pack(fill="x", padx=8, pady=(10, 0))
        self.menu_btn = ctk.CTkButton(top, text="☰", width=34, height=30, corner_radius=8, font=(FONT, 16),
                                      fg_color="transparent", hover_color="#22302a", text_color="#cfc6ab",
                                      command=self.toggle)
        self.menu_btn.pack(side="left")
        self.title_lbl = ctk.CTkLabel(self.sidebar, text=title, font=(FONT, 15, "bold"), text_color="#e6b84f",
                                      wraplength=130, justify="left")
        self.title_lbl.pack(anchor="w", padx=14, pady=(4, 6))
        self.title_line = ctk.CTkFrame(self.sidebar, height=2, fg_color="#e6b84f", corner_radius=1)
        self.title_line.pack(fill="x", padx=14, pady=(0, 8))
        self.collapsed = False
        self.compact = False
        self._full_need, self._fit_job = 0, None
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="x", padx=8)
        self.footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=8, pady=10)
        self.content = ctk.CTkFrame(root, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        self.pages, self.buttons, self.current = {}, {}, None
        self._headings = []
        self._on_show = {}
        self._builders = {}
        self.sidebar.bind("<Configure>", lambda e: self._schedule_fit(), add="+")
        if SpatialSettings().get("sidebar_collapsed", False):
            self.root.after_idle(lambda: self.set_collapsed(True))

    def _label(self, name, collapsed):
        if collapsed:
            return "" if self._icon(name) else name[:1]
        return f" {name}" if self._icon(name) else f"  {name}"

    def _icon(self, name, selected=False):
        from theme import c
        ch = NAV_ICONS.get(name, "")
        return nav_icon(ch, c("#0c1310" if selected else "#cfc6ab")) if ch else None

    def toggle(self):
        self.set_collapsed(not self.collapsed, save=True)

    def set_collapsed(self, on, save=False):
        if on == self.collapsed or not self.sidebar.winfo_exists():
            return
        self.collapsed = on
        diff = SIDEBAR_WIDE - SIDEBAR_NARROW
        self.sidebar.configure(width=SIDEBAR_NARROW if on else SIDEBAR_WIDE)
        for name, btn in self.buttons.items():
            btn.configure(text=self._label(name, on), anchor="center" if on else "w")
        self._apply_chrome()
        for b in self.footer.winfo_children():
            if isinstance(b, ctk.CTkButton):
                if not hasattr(b, "_full_text"):
                    b._full_text = b.cget("text")
                b.configure(text=b._full_text.split()[0] if on else b._full_text, anchor="center" if on else "w")
        try:
            w, h = int(getattr(self.root, "_min_width", 0) or 0), int(getattr(self.root, "_min_height", 0) or 0)
            if w:
                new_w = max(200, w - diff) if on else w + diff
                self.root.minsize(new_w, h)
                if not on and self.root.winfo_width() < new_w:
                    self.root.geometry(f"{new_w}x{self.root.winfo_height()}")
        except Exception as e:
            print(f"Sidebar: couldn't change the window's minimum width ({e})")
        if save:
            SpatialSettings().set("sidebar_collapsed", on)

    def _apply_chrome(self):
        small = self.collapsed or self.compact
        if small:
            self.title_lbl.pack_forget()
            self.title_line.pack_forget()
        elif not self.title_lbl.winfo_manager():
            self.title_lbl.pack(anchor="w", padx=14, pady=(4, 6), before=self.nav_frame)
            self.title_line.pack(fill="x", padx=14, pady=(0, 8), before=self.nav_frame)
        for lbl, line in self._headings:
            if small:
                lbl.pack_forget()
                line.pack(fill="x", padx=6, pady=(3, 1) if self.compact else (4, 2))
            else:
                line.pack_forget()
                lbl.pack(anchor="w", padx=6)
        for btn in self.buttons.values():
            btn.configure(height=25 if self.compact else 31)
            btn.pack_configure(pady=0 if self.compact else 1)

    def _schedule_fit(self):
        if self._fit_job is None:
            self._fit_job = self.root.after(80, self._fit)

    def _fit(self):
        self._fit_job = None
        try:
            if not self.sidebar.winfo_exists():
                return
            avail = self.sidebar.winfo_height()
            if avail < 100:
                return
            need = self.nav_frame.winfo_y() + self.nav_frame.winfo_reqheight() + self.footer.winfo_reqheight() + 24
            if not self.compact and need > avail:
                self._full_need, self.compact = need, True
                self._apply_chrome()
            elif self.compact and self._full_need and self._full_need + 4 <= avail:
                self.compact = False
                self._apply_chrome()
        except Exception as e:
            print(f"Sidebar fit: {e}")

    def footer_button(self, text, command, pady=0):
        b = ctk.CTkButton(self.footer, text=text.split()[0] if self.collapsed else text, width=1,
                          anchor="center" if self.collapsed else "w", height=32, fg_color="transparent",
                          border_color="#34463d", border_width=1, hover_color="#22302a", text_color="#e8dfc5",
                          command=command)
        b._full_text = text
        b.pack(fill="x", pady=pady)
        return b

    def heading(self, text):
        box = ctk.CTkFrame(self.nav_frame, fg_color="transparent")
        box.pack(fill="x", pady=(2 if self._headings else 0, 0))
        lbl = ctk.CTkLabel(box, text=text.upper(), font=(FONT, 10, "bold"), text_color="#8f8a76", height=16)
        line = ctk.CTkFrame(box, height=1, fg_color="#34463d", corner_radius=0)
        if self.collapsed or self.compact:
            line.pack(fill="x", padx=6, pady=(4, 2))
        else:
            lbl.pack(anchor="w", padx=6)
        self._headings.append((lbl, line))

    def add(self, name):
        page = ctk.CTkFrame(self.content, fg_color="#121b17", corner_radius=10)
        btn = ctk.CTkButton(self.nav_frame, text=self._label(name, self.collapsed), width=1,
                            image=self._icon(name), compound="left",
                            anchor="center" if self.collapsed else "w",
                            height=25 if self.compact else 31, corner_radius=8, font=(FONT, 13),
                            fg_color="transparent", hover_color="#22302a", text_color="#cfc6ab",
                            command=lambda n=name: self.set(n))
        btn.pack(fill="x", pady=1)
        self.pages[name], self.buttons[name] = page, btn
        if self.current is None:
            self.set(name)
        return page

    ALIASES = {}
    MERGED = ("Settings", "Minigame", "Fishing Settings")

    def _real(self, name):
        if name in self.pages:
            return name
        if name in self.MERGED and "Setup" in self.pages:
            return "Setup"
        return self.ALIASES.get(name, name)

    def on_show(self, name, fn):
        self._on_show[name] = fn

    def tab(self, name):
        return self.pages[self._real(name)]

    def set(self, name):
        name = self._real(name)
        if self.current:
            self.pages[self.current].pack_forget()
            self.buttons[self.current].configure(fg_color="transparent", text_color="#cfc6ab", font=(FONT, 13),
                                                 image=self._icon(self.current))
        self.pages[name].pack(fill="both", expand=True)
        self.buttons[name].configure(fg_color="#1c8f52", text_color="#0c1310", font=(FONT, 13, "bold"),
                                     image=self._icon(name, selected=True))
        self.current = name
        self._build(name)
        fn = self._on_show.get(name)
        if fn:
            try:
                fn()
            except Exception as e:
                print(f"Page {name}: {e}")

    def lazy(self, name, builder):
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

    def add_grouped(self, names, groups):
        names = list(names)
        if len({groups.get(n, "Options") for n in names}) < 2:
            for n in names:
                self.add(n)
            return
        for section in NAV_SECTIONS:
            mine = [n for n in sorted(names, key=lambda n: NAV_ORDER.get(n, 99)) if groups.get(n, "Options") == section]
            if mine:
                self.heading(section)
                for n in mine:
                    self.add(n)
        if names[0] in self.pages:
            self.set(names[0])


NAV_SECTIONS = ("Setup", "Status", "Options", "Shared")
NAV_GROUPS = {"Settings": "Setup", "Minigame": "Setup", "Options": "Options", "Fishing Settings": "Setup", "Setup": "Setup",
              "Rotation": "Setup", "Skill Combo": "Setup",
              "Main": "Status", "Statistics": "Status", "Logs": "Status",
              "Items": "Options", "Timers": "Options",
              "Pop Up": "Shared", "Events": "Shared", "Hotkeys": "Shared", "General": "Shared"}
NAV_ORDER = {}


class StartCheck:
    def _nav_obj(self):
        return getattr(self, "tabview", None) or getattr(self, "nav")

    def _start_with_check(self):
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
        nav = self._nav_obj()
        real = nav._real(page) if hasattr(nav, "_real") else page
        if real in getattr(nav, "pages", {}):
            nav.set(real)

        def show():
            w = self._target(name) or getattr(self, name, None)
            cl = getattr(self, "_checklist", None)
            if w is None and cl is not None:
                cl.build_all()
                w = self._target(name) or getattr(self, name, None)
            p = w
            while p is not None:
                if isinstance(p, StepCard):
                    p.show(True)
                    break
                p = getattr(p, "master", None)
            self.root.after(120, lambda: self._blink(w))
        self.root.after(150, show)

    def _blink(self, w):
        if w is None:
            return
        try:
            self.root.update_idletasks()
            p = w.master
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
                                          border_color="#e6b84f" if on else orig[1])
        except Exception:
            try:
                row, orig_bg = w.master, w.master.cget("fg_color")
                flip = lambda on: row.configure(fg_color="#5c4515" if on else orig_bg)
            except Exception:
                return
        for k in range(8):
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
        dialog_keys(win)
        win.minsize(540, 120)
        win.transient(self.root)
        win.after(150, win.lift)
        blocked = any(p["block"] for p in show)

        def close():
            self._setup_dialog = None
            win.destroy()
        ctk.CTkLabel(win, text="Can't start yet:" if blocked else "Your setup is missing something:",
                     font=(FONT, 14, "bold"), text_color="#f08a7e" if blocked else "#e6b84f").pack(
            anchor="w", padx=14, pady=(12, 6))
        ticks = {}
        for p in show:
            box = ctk.CTkFrame(win, fg_color="#15201b", corner_radius=6); box.pack(fill="x", padx=12, pady=3)
            top = ctk.CTkFrame(box, fg_color="transparent"); top.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkLabel(top, text=("X  " if p["block"] else "!  ") + p.get("short", p["text"]),
                         font=(FONT, 13, "bold"), anchor="w").pack(side="left")
            if p.get("go"):
                ctk.CTkButton(top, text="Go there  →", width=100, height=28, fg_color="#1c8f52", hover_color="#16743f",
                              command=lambda g=p["go"]: (close(), self.point_to(*g))).pack(side="right")
            if not p["block"]:
                var = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(box, text="Don't warn me about this again", variable=var,
                                font=(FONT, 11)).pack(anchor="w", padx=10, pady=(0, 6))
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
        ctk.CTkButton(row, text="Cancel", width=90, fg_color="#34463d", hover_color="#2a3a33",
                      command=close).pack(side="right")
        if not blocked:
            ctk.CTkButton(row, text="Start anyway", width=120, fg_color="#1c8f52", hover_color="#16743f",
                          command=start).pack(side="right", padx=6)
        win.protocol("WM_DELETE_WINDOW", close)


class SpatialGUI(StartCheck, LibraryPages, RoutePages, PopupPages):
    KIND = None
    NO_OK_EVENTS = False
    WINDOW_WIDTH = None

    def extra_builders(self):
        return {}

    def extra_hotkeys(self):
        return []

    def extra_counters(self):
        return []

    def on_region_saved(self, key):
        pass

    def __init__(self, root, title="Spatial Macro", logic_class=LibraryLogic, on_back=None, tabs=None, tutorial_url="#"):
        self.root = root
        self.on_back = on_back
        self.root.title(title)
        width = self.WINDOW_WIDTH or (720 if "Mining" in title else 650)
        self._fitted_width = fit_window(self.root, width, 760 if width == 800 else 700, width, 480)
        self._wanted_width = width
        self.tutorial_url = tutorial_url
        self.settings = SpatialSettings()
        self.logic = logic_class(self)
        self.overlays = {}
        self._recent = collections.deque(maxlen=20)
        self.tabs_to_show = list(tabs) if tabs else ["Main", "Setup", "Options", "Hotkeys", "Statistics"]
        if "Pop Up" not in self.tabs_to_show and not self._no_ok_events:
            idx = self.tabs_to_show.index("Hotkeys") if "Hotkeys" in self.tabs_to_show else len(self.tabs_to_show)
            self.tabs_to_show.insert(idx, "Pop Up")
        if "Events" not in self.tabs_to_show and not self._no_ok_events:
            self.tabs_to_show.insert(self.tabs_to_show.index("Pop Up") + 1, "Events")
        if "General" not in self.tabs_to_show and "Main" in self.tabs_to_show:
            self.tabs_to_show.append("General")
        self.DEFAULT_CLOVER_COLORS = {"gold": (255, 180, 51), "silver": (164, 178, 178), "bronze": (198, 62, 37)}
        self.DEFAULT_CLOVER_TOLERANCES = {"gold": 5, "silver": 5, "bronze": 5}
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)
        self.setup_ui()
        self.register_hotkeys()

    def setup_ui(self):
        ctk.set_appearance_mode("dark")
        self.tabview = SidebarNav(self.root, self.root.title())
        if self._fitted_width < self._wanted_width:
            self.root.after_idle(lambda: self.tabview.set_collapsed(True))
        self.tabview.add_grouped(self.tabs_to_show, NAV_GROUPS)
        if self.on_back:
            self.tabview.footer_button("←  Back to Menu", self.go_back)
        from logic_events import WATCHER
        if not self._no_ok_events:
            WATCHER.attach(self.settings)
        kind = self._kind
        builders = {"Main": self.setup_main_tab,
                    "Options": {"library": self.setup_library_options, "mining": self.setup_mining_options, "fishing": self.setup_fishing_options}.get(kind),
                    "Pop Up": self.setup_ok_tab, "Events": self.setup_events_tab,
                    "Hotkeys": self.setup_hotkeys_tab, "Statistics": self.setup_statistics_tab,
                    "Setup": {"library": self.setup_library_checklist, "mining": self.setup_mining_checklist,
                              "fishing": self.setup_fishing_checklist}.get(kind),
                    "General": self.setup_general_tab}
        builders.update(self.extra_builders())
        for name in self.tabs_to_show:
            if builders.get(name):
                self.tabview.lazy(name, builders[name])
        if self._is_library:
            self.root.after(1500, self._ocr_check_on_open)

    @property
    def _no_ok_events(self):
        return self.NO_OK_EVENTS

    @property
    def _kind(self):
        if self.KIND:
            return self.KIND
        if self._is_library:
            return "library"
        for k in ("mining", "fishing"):
            if k in self.root.title().lower():
                return k
        return "events"

    @property
    def _is_library(self):
        from logic_library import LibraryLogic
        return isinstance(self.logic, LibraryLogic)

    def _num_combo(self, parent, key, values, current, minimum=0.0):
        def save(v):
            try:
                self.settings.set(key, max(minimum, float(str(v).strip())))
            except (TypeError, ValueError):
                pass
        return seconds_combo(parent, values, current, save)

    def setup_main_tab(self):
        tab = self.tabview.tab("Main")
        ctk.CTkLabel(tab, text=self.root.title().upper(), font=(FONT, 20, "bold"), text_color="#1c8f52").pack(pady=(10, 2))


        status_card = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
        status_card.pack(fill="x", padx=20, pady=(6, 6))
        self.status_label = ctk.CTkLabel(status_card, text="Status: <Not Started>", font=(FONT, 13, "bold"), text_color="#f3ecd8")
        self.status_label.pack(pady=8, padx=10)

        main_btn = dict(height=40, corner_radius=8, font=(FONT, 13, "bold"))
        self.start_btn = ctk.CTkButton(tab, text="", command=self.toggle_macro, **main_btn)
        self.start_btn.pack(pady=(6, 4), fill="x", padx=40)
        self._shown_running = None
        self._sync_start_btn()

        self._always_ok_on = False
        if not self._no_ok_events:
            self.always_ok_btn = big_toggle(tab, self.toggle_always_ok)
            self._ok_toggles = [self.always_ok_btn]
            style_toggle(self.always_ok_btn, False, "Always Click Pop Ups")
            self.always_ok_btn.pack(pady=4, fill="x", padx=40)
            ok_hint = ctk.CTkLabel(tab, text="Set up pop ups (OK and others) on the Pop Up page", font=(FONT, 12),
                                   text_color="#cfc6ab", cursor="hand2")
            ok_hint.pack(pady=(0, 2))
            ok_hint.bind("<Button-1>", lambda e=None: self.tabview.set("Pop Up"))
        gen_hint = ctk.CTkLabel(tab, text="Click delay, keeping Roblox in focus and the badge: General page",
                                font=(FONT, 12), text_color="#cfc6ab", cursor="hand2")
        gen_hint.pack(pady=(0, 6))
        gen_hint.bind("<Button-1>", lambda e=None: self.tabview.set("General"))

        tutorial_link = ctk.CTkLabel(tab, text="Video Tutorial", font=(FONT, 14, "underline"), text_color="#4fd1c5", cursor="hand2")
        tutorial_link.pack(side="bottom", pady=(2, 8))
        tutorial_link.bind("<Button-1>", lambda e=None: links.open_link(self.tutorial_url))
        self.run_panel = RunPanel(tab, self.root, lambda: self.logic.running, self._run_counters(),
                                  self.logic.setup_problems, lambda go: self.point_to(*go), self.open_log,
                                  self._recent)
        self.run_panel.pack(fill="both", expand=True, padx=20, pady=(0, 4))

    DIALOG_HINTS = {
        "image": "With the dialogue open, drag a box around each button once. The macro clicks wherever that "
                 "picture shows up. Try this first.",
        "manual": "Click the exact spot of each button. Use it if Image misses. Don't move or resize Roblox afterwards.",
    }

    MOVES_HINTS = {
        "image": "Tick the moves to train, then capture each ticked move's button (Capture picture). Image finds the move "
                 "by its PICTURE, scrolling the list if needed; the name is a backup if the picture isn't found. "
                 "Slot = where it sits on your hotbar (for the gold clover check).",
    }

    def _ask(self, title, text, initial=""):
        d = ctk.CTkInputDialog(title=title, text=text)
        try:
            if initial: d._entry.insert(0, initial)
        except Exception:
            pass
        return d.get_input()

    def go_back(self):
        self.logic.stop()
        from utils import clear_keys
        clear_keys()
        if self.on_back: self.on_back()

    def setup_events_tab(self):
        from gui_events import EventsPage
        self.events_page = EventsPage(self.tabview.tab("Events"), self.root, self.settings)


    def setup_general_tab(self):
        general_settings(fast_scroll_frame(self.tabview.tab("General"), padx=4, pady=4), self.settings)

    def setup_hotkeys_tab(self):
        tab = self.tabview.tab("Hotkeys")
        ctk.CTkLabel(tab, text="Custom Hotkeys", font=(FONT, 16, "bold"), text_color="#1c8f52").pack(pady=10)
        only = ctk.BooleanVar(value=bool(self.settings.get("hotkeys_roblox_only", False)))

        def set_only():
            import utils
            self.settings.set("hotkeys_roblox_only", bool(only.get()))
            utils.HOTKEYS_ROBLOX_ONLY = bool(only.get())
        ctk.CTkCheckBox(tab, text="Hotkeys only work while Roblox is the focused window", variable=only,
                        font=(FONT, 12), command=set_only).pack(anchor="w", padx=24, pady=(0, 8))
        self.hotkey_entries = {}
        hotkeys = self.settings.get("hotkeys")
        actions = ["start"]

        extra = self.extra_hotkeys()
        if extra:
            for a, key, _, _ in extra:
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
            f = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
            f.pack(pady=3, fill="x", padx=20)
            display_names = {"start": "Start / Stop", "test_btn": "Test Ok Popup", "test_color": "Test Color",
                             "test_movement": "Test Movement"}
            if "Mining" in self.root.title():
                display_names.update({"test_btn": "Test Prompt", "test_movement": "Test Path"})
            elif "Library" in self.root.title():
                display_names.update({"test_btn": "Test Dialogue", "test_path": "Test Path", "test_find": "Find moves (list open)",
                                      "test_full": "Full test (route + moves)",
                                      "test_open": "Test opening (space + E)"})
            display_names.update({a: label for a, _, label, _ in extra})
            label_text = display_names.get(a, a.replace("_", " ").capitalize())
            ctk.CTkLabel(f, text=label_text, width=120, font=(FONT, 12, "bold"), anchor="w").pack(side="left", padx=10, pady=6)
            e = ctk.CTkEntry(f, width=80, font=(FONT, 12))
            e.insert(0, hotkeys.get(a, ""))
            e.pack(side="right", padx=10, pady=6)
            e.bind("<FocusOut>", lambda ev, ac=a: self.update_hotkey(ac))
            self.hotkey_entries[a] = e
        if hasattr(self.logic, "toggle_recording"):
            f = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
            f.pack(pady=3, fill="x", padx=20)
            ctk.CTkLabel(f, text="Record route", width=120, font=(FONT, 12, "bold"), anchor="w").pack(side="left", padx=10, pady=6)
            e = ctk.CTkEntry(f, width=80, font=(FONT, 12))
            e.insert(0, hotkeys.get("record", "f9"))
            e.pack(side="right", padx=10, pady=6)
            e.bind("<FocusOut>", lambda ev: self.update_hotkey("record"))
            self.hotkey_entries["record"] = e
            ctk.CTkLabel(f, text="start / stop  (e.g. f9, ctrl+p)", font=(FONT, 11),
                         text_color="#a39d86").pack(side="right", padx=4)
        ctk.CTkButton(tab, text="Apply Hotkeys", font=(FONT, 12, "bold"), fg_color="#1c8f52", hover_color="#16743f", command=self.register_hotkeys).pack(pady=20)

    def register_hotkeys(self):
        import utils
        utils.clear_keys()
        utils.HOTKEYS_ROBLOX_ONLY = bool(self.settings.get("hotkeys_roblox_only", False))
        hk = self.settings.get("hotkeys")

        def busy():
            return bool(self.logic.running) or self._test_busy()

        def roblox_ok():
            return not utils.HOTKEYS_ROBLOX_ONLY or bool(utils.foreground_roblox()) or busy()

        def try_add(key_name, callback):
            try:
                key_val = hk.get(key_name)
                if key_val:
                    utils.on_hotkey(key_val, callback)
            except Exception as e:
                self.log(f"Hotkey Error ({key_name}): {e}")

        def press_hotkey(key_name, callback, default=""):
            from utils import on_hotkey
            try:
                on_hotkey(hk.get(key_name) or default, callback)
            except Exception as e:
                self.log(f"Hotkey Error ({key_name}): {e}")

        start_key = str(hk.get('start') or "").strip()
        if start_key and "+" not in start_key:
            last = [0.0]

            def on_start(_e):
                if not roblox_ok():
                    return
                if time.time() - last[0] > 0.5:
                    last[0] = time.time()
                    self.toggle_macro()
            try:
                utils.on_key(start_key, on_start)
            except Exception as e:
                self.log(f"Hotkey Error (start): {e}")
        else:
            try:
                key_val = hk.get('start')
                if key_val:
                    utils.on_hotkey(key_val, self.toggle_macro, always=busy)
            except Exception as e:
                self.log(f"Hotkey Error (start): {e}")

        extra = self.extra_hotkeys()
        if extra:
            for a, key, _, fn in extra:
                hk.setdefault(a, key)
                press_hotkey(a, fn)
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
            elif hasattr(self.logic, 'test_path'):
                try_add('test_path', lambda: self._run_test(self.logic.test_path))
        if hasattr(self.logic, 'test_find_moves'):
            try_add('test_find', self.test_find_moves)
            try_add('test_full', lambda: self.test_find_moves(walk=True))
            try_add('test_open', lambda: self._run_test(self.logic.test_open_dialogue))

        if hasattr(self.logic, "toggle_recording"):
            press_hotkey("record", self.logic.toggle_recording, default="f9")

        self.log("Hotkeys registered")

    def _test_busy(self):
        t = getattr(self, "_test_thread", None)
        return bool(t is not None and t.is_alive())

    def toggle_macro(self):
        if self._test_busy():
            if self.logic.running:
                self.refresh_macro()
            else:
                self.logic.test_running = False
            self.log("Test stopped.")
            return
        if self.logic.running:
            self.refresh_macro()
        else:
            self.root.after(0, self._start_with_check)
            return
        self.root.after(0, self._sync_start_btn)

    def _sync_start_btn(self):
        try:
            if not self.start_btn.winfo_exists():
                return
        except Exception:
            return
        running = bool(self.logic.running)
        if not running and getattr(self, "_action_badge", None) is not None:
            from overlay import show_action
            show_action(self, "", False)
        if running != self._shown_running:
            key = self.settings.get("hotkeys", {}).get("start", "f6").upper()
            if running:
                self.start_btn.configure(text=f"■  Stop Macro ({key})", fg_color="#d9483b", hover_color="#b83a2f")
            else:
                self.start_btn.configure(text=f"▶  Start Macro ({key})", fg_color="#1f9d55", hover_color="#187a43")
            self._shown_running = running
        self.root.after(400, self._sync_start_btn)

    def refresh_macro(self):
        def stop():
            self.logic.stop()
            self.root.after(0, lambda: (self.register_hotkeys(), self.log("Macro stopped")))
        threading.Thread(target=stop, daemon=True).start()

    def _run_test(self, fn):
        import threading
        def wrapper():
            self.logic.test_running = True
            try:
                fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.log(f"Test failed: {e}")
            finally:
                def done():
                    self.logic.test_running = False
                    if not self.logic.running:
                        from overlay import show_action
                        show_action(self, "", False)
                self.root.after(5000, done)
        self._test_thread = threading.Thread(target=wrapper, daemon=True)
        self._test_thread.start()

    def update_hotkey(self, a):
        key = self.hotkey_entries[a].get().lower()
        hk = self.settings.get("hotkeys"); hk[a] = key; self.settings.set("hotkeys", hk); self.register_hotkeys()

    def log(self, msg, _printed=False, hold=0):
        if not _printed:
            print(msg)
        if threading.current_thread() is not threading.main_thread():
            try:
                self.root.after(0, lambda m=msg: self.log(m, _printed=True, hold=hold))
            except Exception:
                pass
            return
        self._remember(msg)
        if not hasattr(self, 'status_label'):
            return
        try:
            self.status_label.configure(text=f"Status: {msg}")
        except Exception:
            pass
        now = time.time()
        if not hold and now < getattr(self, "_bar_hold_until", 0):
            self._bar_pending = msg
            return
        if hold:
            self._bar_hold_until, self._bar_pending = now + hold, None
            self.root.after(int(hold * 1000) + 50, self._bar_release)
        self._show_on_bar(msg)

    def _remember(self, msg):
        entry = (time.strftime("%H:%M:%S"), str(msg), msg_kind(msg))
        recent = getattr(self, "_recent", None)
        if recent is not None:
            recent.append(entry)
        panel = getattr(self, "run_panel", None)
        if panel is not None:
            panel.add(entry)

    def open_log(self):
        open_log_file(self.root)

    def _run_counters(self):
        kind, lg = self._kind, self.logic
        out = []
        if kind == "library":
            out.append(("Gold used (lifetime)", lambda: f"{lg.lifetime_gold():,}"))
        if kind == "mining":
            out.append(("Laps", lambda: getattr(lg, "lap_no", 0)))
        out += self.extra_counters()
        if not self._no_ok_events:
            out.append(("Pop-ups clicked", lambda: getattr(lg, "popups_clicked", 0)))
        return out

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

    def _capture_box(self, save, saved_msg, after=None, delay=150, fail_msg=FAIL_MSG):
        self._hide_for_pick()

        def done(x1, y1, x2, y2):
            def finish():
                ok = save([x1, y1, x2, y2])
                self.root.deiconify()
                self.log(saved_msg if ok else fail_msg)
                if after:
                    after()
            self.root.after(delay, finish)
        Overlay(done)

    def _hide_for_pick(self):
        self.root.withdraw()
        self.root.update()
        time.sleep(0.2)

    def pick_region(self, key):
        self._hide_for_pick()
        Overlay(lambda x1, y1, x2, y2: self.save_region(key, x1, y1, x2, y2))

    def save_region(self, key, x1, y1, x2, y2):
        self.root.deiconify(); self.settings.settings["regions"][key] = [x1, y1, x2, y2]; self.settings.save()
        if key == "score":
            self._show_clover_region()
        if key == "mining_interact" and hasattr(self, "interact_area_lbl"):
            self._show_interact_area()
        self.on_region_saved(key)
        if key.startswith("gold_clover_") and getattr(self, "gold_status", {}).get(int(key[-1])):
            self.gold_status[int(key[-1])].configure(text="set", text_color="#7ee0a6")
        if key == "ok_scan_area":
            self.refresh_ok_status()
            if self._ok_switch_on():
                self.toggle_ok_area_overlay()

    def pick_point(self, key):
        self._hide_for_pick()
        PointSelector(lambda x, y: self.save_point(key, x, y))

    def save_point(self, key, x, y):
        self.root.deiconify()
        self.settings.settings["regions"][key] = [x, y]
        self.settings.save()
        if key == "chat_button" and hasattr(self, "chat_btn_lbl"):
            self.chat_btn_lbl.configure(text=f"({x}, {y})", text_color="#7ee0a6")
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

    def exit_app(self):
        self.logic.stop()
        from settings import flush_all
        flush_all()
        self.root.destroy(); os._exit(0)

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
            if key == "score" and not (rect and any(v != 0 for v in rect)) and hasattr(self.logic, "clover_area"):
                rect = self.logic.clover_area()
            if rect and any(v != 0 for v in rect):
                self.overlays[key] = PersistentOverlay(rect[0], rect[1], rect[2], rect[3], color=colors[i % len(colors)])

    def hide_overlays(self):
        for k in [k for k in self.overlays if k != "_ok_area"]:
            self.overlays.pop(k).destroy()

class OkPopupPage(SpatialGUI):

    def __init__(self, root, frame, settings, log, build=True):
        from gui_events import EventsOnlyLogic
        self.root = root
        self.settings = settings
        self._log_fn = log
        self.overlays = {}
        self.tabs_to_show = []
        self.tabview = type("OnePage", (), {"tab": staticmethod(lambda name: frame)})()
        self.logic = EventsOnlyLogic(self)
        self._always_ok_on = False
        self._ok_toggles = []
        self._built = False
        if build:
            self.build_page()

    def build_page(self):
        if not self._built:
            self._built = True
            self.setup_ok_tab()

    def log(self, msg):
        self._log_fn(msg)

    def close(self):
        try:
            self.logic.stop_global_ok_scanner()
        except Exception:
            pass
