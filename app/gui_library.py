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
from ui_style import dialog_keys, FONT, big_toggle, style_toggle, save_while_typing, sound_picker, fast_scroll_frame, seconds_combo, help_box, \
    StepCard, OptionGroup, CARD, Checklist, search_box
import os
import links
import time
import threading


class LibraryPages:
    def setup_library_checklist(self):
        self._lib_holder = fast_scroll_frame(self.tabview.tab("Setup"))
        self._build_lib_checklist()
        self.tabview.on_show("Setup", lambda: self._checklist.refresh())

    def _build_lib_checklist(self):
        info = lambda n: (lambda state: self._lib_step_text(n, self.logic.dialog_mode()))
        steps = ((1, "Route to the wisp", ("lib_route",), self._step_route, info(1), None),
                 (2, "Moves and wisp dialogue", ("lib_manual_training", "lib_image_training", "lib_pic_"),
                  self._step_moves, info(2), None),
                 (3, "Gold clover check", ("lib_gold",), self._step_gold, info(3), None),
                 (4, "Test everything", (), self._step_test, info(4), None))
        self._checklist = Checklist(self._lib_holder, self.root, self.logic.setup_problems,
                                    lambda: self.tabview.get() == "Setup", steps, video="video_library",
                                    before_steps=self._full_auto_card)
        self._lib_steps, self._lib_progress = self._checklist.steps, self._checklist.progress
        self.refresh_routes()
        self._apply_manual_limit()
        self._checklist.refresh(open_first=True)

    def _full_auto_card(self, holder):
        fa = self._full_card = ctk.CTkFrame(holder, fg_color="#15201b", border_color="#1c8f52", border_width=1,
                                            corner_radius=8)
        fa.pack(fill="x", padx=8, pady=(4, 4))
        t = ctk.CTkLabel(fa, text="Quick setup: Full Auto Setup (optional)", font=(FONT, 14, "bold"), text_color="#1c8f52")
        t.pack(anchor="w", padx=8, pady=(6, 0))
        help_box(fa, "Record or pick your Route in step 1 first, and pick Image in step 2. Then stand "
                     "at the desk and press the button: it finds your hotbar, walks to the wisp, reads every "
                     "move (Image: also takes each button's picture) and sets the dialogue. You only choose which "
                     "moves to train at the end. The minigame needs no setup: it's seen by the health / mana bar "
                     "going away.", t)
        ctk.CTkButton(fa, text="Start Full Auto Setup", height=32, font=(FONT, 13, "bold"), fg_color="#1f9d55",
                      hover_color="#187a43", command=self.full_auto_setup).pack(fill="x", padx=8, pady=(6, 8))

    def _step_route(self, body):
        self._route_card(body, "Dialogue (F1)", self.logic.test_detection,
                         "Test Path (F3)", self.logic.test_path,
                         f"At the desk: {self.logic.rec_key()} → walk to the wisp (jumps and E are recorded too) → {self.logic.rec_key()}.")
        self._stand_box = ctk.CTkFrame(body, fg_color="transparent")
        self._stand_guide(self._stand_box)
        self.refresh_routes()

    def _stand_guide(self, parent):
        from PIL import Image
        from ui_style import make_collapsible
        head = ctk.CTkFrame(parent, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(head, text="Where to stand", font=(FONT, 13, "bold"), anchor="w").pack(side="left")
        ctk.CTkLabel(parent, text="The built-in route only works from this exact spot and direction. "
                                  "Do this before you press Start.", font=(FONT, 12), text_color="#cfc6ab",
                     wraplength=420, justify="left", anchor="w").pack(fill="x", padx=10, pady=(4, 2))
        for file, text in (("stand_1.png", "1. Go here (the red circle)"), ("stand_2.png", "2. Face this way")):
            ctk.CTkLabel(parent, text=text, font=(FONT, 13, "bold"), anchor="w").pack(fill="x", padx=10, pady=(4, 2))
            try:
                im = Image.open(os.path.join(self.logic._builtin_dir(), file)).convert("RGB")
                pic = ctk.CTkImage(light_image=im, dark_image=im, size=(420, 420 * im.height // im.width))
                ctk.CTkLabel(parent, text="", image=pic).pack(anchor="w", padx=10, pady=(0, 4))
            except Exception as e:
                print(f"Where to stand: {e}")
        make_collapsible(parent, self.settings.get("stand_guide_open", True),
                         lambda is_open: self.settings.set("stand_guide_open", bool(is_open)))

    def _step_moves(self, body):
        self.dialog_card = ctk.CTkFrame(body, **CARD)
        self.dialog_card.pack(fill="x", padx=15, pady=4)
        self.build_dialog_card()

    def _step_gold(self, body):
        self.gold_card = ctk.CTkFrame(body, **CARD)
        self.gold_card.pack(fill="x", padx=15, pady=4)
        self.build_gold_card()

    def _step_test(self, body):
        ctk.CTkLabel(body, text="Stand at the desk and press Full test: it walks the route, opens the wisp's "
                                "dialogue and hovers each move it finds. Nothing is clicked.",
                     font=(FONT, 12), justify="left", anchor="w", wraplength=440).pack(fill="x", padx=15, pady=(2, 4))
        row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", padx=15, pady=(0, 4))
        hk = self.settings.get("hotkeys", {})
        ctk.CTkButton(row, text=f"Full test ({(hk.get('test_full') or 'f5').upper()})", width=130, height=30,
                      font=(FONT, 12, "bold"), fg_color="#1f9d55", hover_color="#187a43",
                      command=lambda: self.test_find_moves(walk=True)).pack(side="left")

    def _lib_step_text(self, n, mode):
        if n == 1:
            menu = getattr(self, "route_menu", None)
            return f"Route: {menu.get()}" if menu is not None and menu.winfo_exists() else ""
        if n == 2:
            if mode == "manual":
                k = sum(1 for m in self.logic.manual_moves() if m.get("train"))
                return f"Manual: {k} move spot{'s' if k != 1 else ''} ticked."
            flags = self.logic.train_flags()
            k = sum(flags)
            if not k:
                return "No move ticked yet - tick the moves to train."
            missing = sum(1 for i, f in enumerate(flags) if f and not self.logic.has_dialog_template(f"move_{i + 1}"))
            return (f"{k} move{'s' if k != 1 else ''} ticked"
                    + (f" - {missing} without a picture." if missing else ", each with its picture."))
        if n == 3:
            return ("Hotbar set - press Test to see it read the clovers." if self.logic.gold_mode() == "auto"
                    else "A spot is set for every ticked move.")
        return "Run this once the steps above are done."

    def _sound_option(self, b):
        sound_row = ctk.CTkFrame(b, fg_color="transparent")

        def flip_sound():
            self.settings.set("sound_when_done", bool(snd.get()))
            sound_row.pack(anchor="w", padx=4, pady=(0, 4), after=snd) if snd.get() else sound_row.pack_forget()
        snd = ctk.CTkCheckBox(b, text="Play a sound when every move is trained (the macro stops)",
                              font=(FONT, 12), command=flip_sound)
        if self.settings.get("sound_when_done", False):
            snd.select()
        snd.pack(anchor="w", padx=4, pady=2)
        sound_picker(sound_row, "done").pack(anchor="w")
        if snd.get():
            sound_row.pack(anchor="w", padx=4, pady=(0, 4), after=snd)

    def _options_page(self, page="Options"):
        holder = fast_scroll_frame(self.tabview.tab(page))
        groups = self._option_groups = []
        top = ctk.CTkFrame(holder, fg_color="transparent"); top.pack(fill="x", padx=15, pady=(8, 2))
        adv = ctk.BooleanVar(value=bool(self.settings.get("options_advanced", False)))
        note = ctk.CTkLabel(holder, text="", font=(FONT, 12), text_color="#a39d86", anchor="w", justify="left")

        def changed(shown):
            hidden = 0 if adv.get() else sum(1 for g in groups if g.advanced)
            words = search.get().strip()
            if words and not shown:
                text = f"No setting matches '{words}'." + (" Some are hidden - try Advanced." if hidden else "")
            elif hidden and not words:
                text = f"{hidden} more group{'s' if hidden != 1 else ''} (timings, colours...) under Advanced."
            else:
                text = ""
            note.configure(text=text)
            note.pack_forget()
            if text:
                note.pack(fill="x", padx=18, pady=(2, 8))
        search = search_box(top, groups, adv.get, on_change=changed)
        search.pack(side="left", fill="x", expand=True)

        def flip(v):
            adv.set(v == "Advanced")
            self.settings.set("options_advanced", adv.get())
            search.refresh()
        seg = ctk.CTkSegmentedButton(top, values=["Basic", "Advanced"], font=(FONT, 12, "bold"), command=flip)
        seg.set("Advanced" if adv.get() else "Basic")
        seg.pack(side="right", padx=(8, 0))
        self.root.after_idle(search.refresh)

        def group(title, advanced=False):
            g = OptionGroup(holder, title, advanced)
            g.place_me(fill="x", padx=15, pady=4)
            groups.append(g)
            return g.body
        return group

    def _num_row(self, parent, text, key, values, current, default, minimum=0.0, label_width=None, unit=""):
        row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", padx=4, pady=2)
        kw = {"width": label_width, "anchor": "w"} if label_width else {}
        ctk.CTkLabel(row, text=text, font=(FONT, 12), **kw).pack(side="left")
        box = self._num_combo(row, key, values, current, minimum=minimum)
        box.pack(side="left", padx=6)
        if unit:
            ctk.CTkLabel(row, text=unit, font=(FONT, 12), text_color="#a39d86").pack(side="left")

        def reset():
            from tkinter import messagebox
            if messagebox.askyesno("Reset", f"Set '{text}' back to {default:g}?", parent=self.root):
                self.settings.set(key, default)
                box.set(f"{default:g}")
                self.log(f"{text}: back to {default:g}.")
        ctk.CTkButton(row, text=f"Reset ({default:g})", width=78, height=24, font=(FONT, 11), fg_color="#2a3a33",
                      hover_color="#34463d", command=reset).pack(side="right")
        return box

    def setup_library_options(self):
        group = self._options_page()
        b = group("Training order")
        order = ctk.BooleanVar(value=bool(self.settings.get("train_in_order", False)))
        ctk.CTkCheckBox(b, text="Train in order (1 → 2 → 3 ..., one each, skips gold)", variable=order, font=(FONT, 12),
                        command=lambda: self.settings.set("train_in_order", bool(order.get()))).pack(anchor="w", padx=4, pady=2)

        self._sound_option(group("When finished"))


        self._minigame_extras(group("Minigame: chat and clover area"))

        b = group("Timing", advanced=True)
        for key, text, values, current, default, low in (
                ("after_training_wait", "Wait after Clover Training (s) - Image",
                 ["0.5", "1", "1.5", "2", "3", "5"], self.logic.after_training_wait(), 5.0, 0.0),
                ("dialog_wait", "Wait before each click (s) - Manual dialogue",
                 ["0.5", "1", "1.5", "2", "3", "5"], self.settings.get("dialog_wait", 5.0), 5.0, 0.0),
                ("after_move_wait", "Wait after clicking the move (s)",
                 ["0.5", "1", "2", "3", "3.5", "5"], self.logic.after_move_wait(), 1.0, 0.0)):
            self._num_row(b, text, key, values, current, default, minimum=low)

        self.setup_clover_tab(group("Clover colours", advanced=True))

        b = group("Share setup")
        share = ctk.CTkFrame(b, fg_color="transparent"); share.pack(fill="x")
        share_t = ctk.CTkLabel(share, text="Your setup in one file", font=(FONT, 12))
        share_t.pack(side="left", padx=4)
        ctk.CTkButton(share, text="Import", width=80, height=26, fg_color="#34463d", hover_color="#2a3a33",
                      command=self.import_library_setup).pack(side="right", padx=(2, 4))
        ctk.CTkButton(share, text="Export", width=80, height=26, fg_color="#34463d", hover_color="#2a3a33",
                      command=self.export_library_setup).pack(side="right", padx=2)
        help_box(b, "Export saves your moves, dialogue setup, pictures and route in one file to give "
                    "someone; Import loads one.", share_t)

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

    def _out_of_the_way(self, fn):
        self.root.after(0, self.root.withdraw)
        time.sleep(0.35)
        try:
            return fn()
        finally:
            self.root.after(0, self.root.deiconify)

    def full_auto_setup(self):
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
        rows, names, pictures = res["rows"], res["names"], res["pictures"]
        rows_of = {r["slot"]: r["slot"] - 1 for r in rows}
        win, body, bottom = self._moves_window("Full Auto Setup - check your moves", rows, names,
                                               extra_h=30 + 20 * len(res.get("notes") or []))
        ctk.CTkLabel(body, text=notes, font=(FONT, 12), justify="left", anchor="w").pack(fill="x", padx=4, pady=(6, 6))
        ctk.CTkLabel(body, text="Check each slot's move and tick what to train (already maxed ones are unticked). "
                                "If one is wrong, pick the right one from its list.",
                     font=(FONT, 12, "bold"), wraplength=620, justify="left").pack(anchor="w", padx=4, pady=(0, 4))
        widgets = self._move_rows(body, rows, names, pictures, rows_of,
                                  maxed=[slot for slot, gold in res["gold"].items() if gold])

        def apply(start=False):
            from logic_library import MAX_MOVES
            chosen, _ = self._picked_moves(widgets, rows_of)
            used = {c["move"] for c in chosen}
            self.logic.apply_auto_setup(chosen, pictures, clear=[i for i in range(MAX_MOVES) if i not in used])
            win.destroy()
            self.reload_library_settings()
            self.log("Full Auto Setup applied." + (" Starting here at the wisp..." if start else ""))
            if start:
                self.toggle_macro()

        def cancel():
            runner.restore()
            win.destroy()
            self.reload_library_settings()
            self.log("Full Auto Setup cancelled - old settings put back.")
        win.protocol("WM_DELETE_WINDOW", cancel)
        ctk.CTkButton(bottom, text="Apply", width=110, fg_color="#1c8f52", hover_color="#16743f",
                      command=apply).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="Apply + Start", width=130, fg_color="#1f9d55", hover_color="#187a43",
                      command=lambda: apply(True)).pack(side="left", padx=4)
        ctk.CTkButton(bottom, text="Cancel", width=90, fg_color="#34463d", hover_color="#2a3a33",
                      command=cancel).pack(side="left", padx=4)

    def _ocr_ok(self):
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

    def _ocr_check_on_open(self):
        from utils import SpatialUtils
        if getattr(SpatialUtils, "_screen_read_checked", False):
            return
        if not getattr(self, "_idle_watch", False):
            self._idle_watch, self._last_input = True, time.time()
            for seq in ("<ButtonPress>", "<KeyPress>", "<MouseWheel>"):
                self.root.bind_all(seq, lambda e: setattr(self, "_last_input", time.time()), add="+")
        try:
            if not self.root.winfo_exists():
                return
            if time.time() - self._last_input < 2.5:
                self.root.after(1000, self._ocr_check_on_open)
                return
        except Exception:
            return
        SpatialUtils._screen_read_checked = True
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
            if self._ocr_ok():
                self.log("Text reading: OK (read the built-in test words 'Clover Training').")
            else:
                self.log("Text reading doesn't work - see the popup (Auto setup needs it).")
        threading.Thread(target=run, daemon=True).start()

    def auto_setup_moves(self):
        from tkinter import messagebox
        if self.logic.running:
            self.log("Stop the macro first."); return
        self.log("Auto setup: switching to Roblox (hotbar visible)...")

        from logic_library import MAX_MOVES
        flags = self.logic.train_flags()
        ticked = {self.logic.move_slot(i): i for i in range(MAX_MOVES) if flags[i]}
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
                return
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
                out = self.logic.scan_move_list(alive=lambda: not self.logic.running,
                                                keep_unread=self.logic.dialog_mode() == "image")
                if not out:
                    seen["path"] = self.logic.save_debug_shot("auto_setup")
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

    def _moves_window(self, title, rows, names, extra_h=0):
        from gui import fit_window
        image_mode = self.logic.dialog_mode() == "image"
        win = ctk.CTkToplevel(self.root)
        win.title(title)
        dialog_keys(win)
        height = 190 + extra_h + 40 * len(rows) + (30 if image_mode else 20) * ((len(names) + 1) // 2)
        fit_window(win, 780 if image_mode else 660, height, 560, 300)
        win.transient(self.root); win.after(150, win.lift)
        bottom = ctk.CTkFrame(win, fg_color="transparent"); bottom.pack(side="bottom", pady=10)
        return win, fast_scroll_frame(win), bottom

    def _move_rows(self, parent, rows, names, pictures, rows_of, maxed=()):
        image_mode = self.logic.dialog_mode() == "image"

        def thumb(name, h=22):
            pic = pictures.get(name)
            if not image_mode or pic is None or not getattr(pic, "size", 0):
                return None
            try:
                from PIL import Image
                im = Image.fromarray(pic[:, :, ::-1])
                im.thumbnail((200, h))
                return ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
            except Exception:
                return None
        seen = ctk.CTkFrame(parent, fg_color="#101814", corner_radius=6); seen.pack(fill="x", padx=4, pady=(0, 6))
        ctk.CTkLabel(seen, text=f"Seen in the dialogue ({len(names)}):", font=(FONT, 11, "bold"),
                     text_color="#b5e8c9").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 0))
        for i, n in enumerate(names):
            key = getattr(self.logic, "_auto_keys", {}).get(n)
            img = thumb(n)
            if img:
                lbl = ctk.CTkLabel(seen, text=f"  {n}", image=img, compound="left", font=(FONT, 11),
                                   text_color="#cfc6ab")
                lbl._img = img
            else:
                lbl = ctk.CTkLabel(seen, text=f"• {n}" + (f"  → '{key.capitalize()}'" if key else "  → (no unique word)"),
                                   font=(FONT, 11), text_color="#cfc6ab")
            lbl.grid(row=1 + i // 2, column=i % 2, sticky="w", padx=8, pady=1)
        ctk.CTkLabel(seen, text="").grid(row=99, column=0, pady=0)
        widgets = []
        for r in rows:
            row = ctk.CTkFrame(parent, fg_color="#15201b", corner_radius=6); row.pack(fill="x", padx=4, pady=2)
            var = ctk.BooleanVar(value=bool(r["match"]) and r["slot"] not in maxed)
            mv = rows_of.get(r["slot"])
            ctk.CTkCheckBox(row, text=(f"Move {mv + 1} · slot {r['slot']}" if mv is not None else f"Slot {r['slot']}"),
                            variable=var, width=120,
                            font=(FONT, 12, "bold")).pack(side="left", padx=6, pady=6)
            pick = r["match"] or (r["suggest"][0] if r["suggest"] else "(skip)")
            note = ctk.CTkLabel(row, text="", font=(FONT, 11), wraplength=250, justify="left")

            def show_word(choice, r=r, note=note):
                key = getattr(self.logic, "_auto_keys", {}).get(choice)
                if image_mode and choice != "(skip)":
                    img = thumb(choice, 24)
                    note.configure(image=img, compound="left",
                                   text="" if img else "no picture of it - capture it in Settings",
                                   text_color="#e6b84f")
                    note._img = img
                    return
                if choice == "(skip)":
                    note.configure(image=None)
                    note.configure(text="skipped", text_color="#a39d86")
                elif not key:
                    note.configure(text="no word that's unique to this move - switch the Wisp dialogue to "
                                        "Image mode for it", text_color="#e6b84f")
                elif choice == r["match"]:
                    note.configure(text=f"will look for '{key.capitalize()}'  (hotbar: {r['hotbar'][:20] or '?'})",
                                   text_color="#7ee0a6" if r["score"] >= 0.7 else "#e6b84f")
                else:
                    note.configure(text=f"will look for '{key.capitalize()}'  (picked by you)", text_color="#cfc6ab")
            choices = list(dict.fromkeys([m for m in r["suggest"] if m in names] + names)) + ["(skip)"]

            def picked(choice, var=var, show=show_word):
                var.set(choice != "(skip)")
                show(choice)
            om = ctk.CTkOptionMenu(row, values=choices, width=230, height=26, command=picked)
            om.set(pick)
            om.pack(side="left", padx=4)
            note.pack(side="left", padx=6)
            if r["slot"] in maxed:
                ctk.CTkLabel(row, text="already maxed", font=(FONT, 11), text_color="#e6b84f").pack(side="right", padx=8)
            show_word(pick)
            widgets.append((r, var, om))
        return widgets

    def _picked_moves(self, widgets, rows_of):
        chosen = [{"slot": r["slot"], "name": om.get(), "train": bool(v.get()), "hotbar": r["hotbar"],
                   **({"move": rows_of[r["slot"]]} if r["slot"] in rows_of else {})}
                  for r, v, om in widgets if om.get() != "(skip)"]
        skipped = [r["slot"] for r, v, om in widgets if om.get() == "(skip)"]
        for slot in skipped:
            self.log(f"Auto setup: slot {slot} left on (skip) - its Move row is now empty")
        return chosen, [rows_of[s] for s in skipped if s in rows_of]

    def _auto_setup_confirm(self, rows, names, pictures):
        rows_of = getattr(self, "_auto_rows", {})
        win, body, bottom = self._moves_window("Auto setup - confirm", rows, names)
        ctk.CTkLabel(body, text="Check each slot's move. If one is wrong, just pick the right one from its list - "
                                "the list holds every move seen in the wisp's dialogue. Untick what you don't "
                                "want to train, then Apply.",
                     font=(FONT, 12), wraplength=620, justify="left").pack(anchor="w", padx=4, pady=(6, 4))
        widgets = self._move_rows(body, rows, names, pictures, rows_of)

        def apply():
            chosen, clear = self._picked_moves(widgets, rows_of)
            self.logic.apply_auto_setup(chosen, pictures, clear=clear)
            win.destroy()
            self.log(f"Auto setup: {len(chosen)} move(s) filled in. Press Find moves to double-check.")
            self.reload_library_settings()
        ctk.CTkButton(bottom, text="Apply", width=120, fg_color="#1f9d55", hover_color="#187a43",
                      command=apply).pack()

    def reload_library_settings(self):
        holder = getattr(self, "_lib_holder", None)
        if holder is None or not holder.winfo_exists():
            return
        for w in holder.winfo_children():
            w.destroy()
        self._build_lib_checklist()

    def test_find_moves(self, walk=False):
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
        mode = self.logic.dialog_mode()
        fa = getattr(self, "_full_card", None)
        steps = getattr(self, "_lib_steps", {})
        if fa is not None and fa.winfo_exists():
            if mode == "manual":
                fa.pack_forget()
            elif not fa.winfo_manager():
                fa.pack(fill="x", padx=8, pady=(4, 4), **({"before": steps[1]} if 1 in steps else {}))

    def _dialog_preview(self, parent, key, inline=False):
        try:
            from PIL import Image
            pic = Image.open(self.logic.dialog_template_path(key)).convert("RGB")
            pic.load()
            w, h = pic.size
            scale = min((180 if inline else 220) / max(w, 1), (24 if inline else 34) / max(h, 1), 2.0)
            size = (max(1, int(w * scale)), max(1, int(h * scale)))
            img = ctk.CTkImage(light_image=pic, dark_image=pic, size=size)
            if inline:
                ctk.CTkLabel(parent, text="", image=img).pack(side="left", padx=6)
                return
            holder = ctk.CTkFrame(parent, fg_color="transparent"); holder.pack(fill="x", padx=8, pady=(0, 4))
            ctk.CTkLabel(holder, text="", image=img).pack(side="left", padx=(158, 0))
        except Exception as e:
            print(f"preview {key}: {e}")

    def build_dialog_card(self):
        self._apply_manual_limit()
        card = getattr(self, "dialog_card", None)
        if card is None or not card.winfo_exists():
            return
        for w in card.winfo_children():
            w.destroy()
        mode = self.logic.dialog_mode()
        hk = self.settings.get("hotkeys", {})
        head = ctk.CTkFrame(card, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 2))
        title = ctk.CTkLabel(head, text="Moves and wisp dialogue", font=(FONT, 13, "bold"))
        title.pack(side="left")
        if mode == "image":
            ctk.CTkButton(head, text="Auto setup", width=100, height=24, font=(FONT, 11, "bold"),
                          fg_color="#1c8f52", hover_color="#16743f", command=self.auto_setup_moves).pack(side="right")
        tips = [self.DIALOG_HINTS[mode]]
        if mode == "image":
            tips.append(self.MOVES_HINTS["image"])
        else:
            tips.append("Ticked spots are trained in order: spot 1 until its gold clover shows (checked on its "
                        "hotbar slot), then spot 2, then 3. Just clicks - no reading, no scrolling.")
        tips.append("Talk to the wisp first so the buttons are on screen, then capture / pick. "
                    "Press Test Dialogue (F1) to check.")
        help_box(card, "\n\n".join(tips), title)
        seg = ctk.CTkSegmentedButton(card, values=["Image", "Manual"], font=(FONT, 12, "bold"),
                                     command=lambda v: (self.settings.set("dialog_mode", v.lower()), self.build_dialog_card()))
        seg.set(mode.capitalize())
        seg.pack(fill="x", padx=8, pady=(2, 4))
        tools = ctk.CTkFrame(card, fg_color="transparent"); tools.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkButton(tools, text=f"Full test ({(hk.get('test_full') or 'f5').upper()})", width=120, height=24,
                      font=(FONT, 11, "bold"), fg_color="#1f9d55", hover_color="#187a43",
                      command=lambda: self.test_find_moves(walk=True)).pack(side="left")
        ctk.CTkButton(tools, text=f"{'Hover spots' if mode == 'manual' else 'Find moves'} "
                                  f"({(hk.get('test_find') or 'f4').upper()})", width=120, height=24,
                      font=(FONT, 11, "bold"), fg_color="#1c8f52", hover_color="#16743f",
                      command=self.test_find_moves).pack(side="left", padx=6)
        if mode != "manual":
            ctk.CTkButton(tools, text="↕ Test scroll", width=100, height=24, font=(FONT, 11, "bold"),
                          fg_color="#34463d", hover_color="#2a3a33",
                          command=lambda: self._run_test(self.logic.test_scroll)).pack(side="left")
        if mode == "image":
            self._image_rows(card)
        else:
            self._manual_rows(card)
        ctk.CTkFrame(card, fg_color="transparent", height=4).pack()

    def _section(self, card, text, hint=""):
        ctk.CTkLabel(card, text=text, font=(FONT, 12, "bold"), text_color="#a39d86", anchor="w").pack(
            fill="x", padx=10, pady=(6, 0))
        if hint:
            ctk.CTkLabel(card, text=hint, font=(FONT, 11), text_color="#8f8a76", anchor="w", justify="left",
                         wraplength=400).pack(fill="x", padx=10)

    def _picture_line(self, parent, key, label="Capture"):
        ok = self.logic.has_dialog_template(key)
        ctk.CTkButton(parent, text="Re-capture" if ok else label, width=100, height=26,
                      fg_color="#1c8f52", hover_color="#16743f",
                      command=lambda k=key: self.capture_dialog_button(k)).pack(side="left")
        if ok:
            self._dialog_preview(parent, key, inline=True)
        else:
            ctk.CTkLabel(parent, text="no picture yet", font=(FONT, 12), text_color="#f08a7e").pack(side="left", padx=6)

    def _image_rows(self, card):
        from logic_library import MAX_MOVES
        self._section(card, "First menu")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Clover Training", width=112, anchor="w", font=(FONT, 12, "bold")).pack(side="left")
        self._picture_line(row, "clover_training")
        self._section(card, "Moves", "Tick the ones to train. Name = a backup if its picture isn't found. "
                                     "Slot = where it sits on your hotbar.")
        flags = self.logic.train_flags()
        names = self.logic.move_names()
        slots = self.logic._nine("gold_move_slots", lambda k: k + 1)
        self.train_vars, self.move_entries = [], []
        for i in range(MAX_MOVES):
            box = ctk.CTkFrame(card, fg_color="transparent"); box.pack(fill="x", padx=8, pady=(3, 0))
            r1 = ctk.CTkFrame(box, fg_color="transparent"); r1.pack(fill="x")
            var = ctk.BooleanVar(value=flags[i])
            ctk.CTkCheckBox(r1, text=f"Move {i + 1}", variable=var, width=90, font=(FONT, 12, "bold"),
                            command=self._save_train_flags).pack(side="left")
            sel = ctk.CTkOptionMenu(r1, values=[str(k) for k in range(1, MAX_MOVES + 1)], width=58, height=26,
                                    command=lambda v, idx=i: self.logic.set_move_slot(idx, v))
            sel.set(str(slots[i]))
            sel.pack(side="right")
            ctk.CTkLabel(r1, text="slot", font=(FONT, 12)).pack(side="right", padx=(6, 3))
            e = ctk.CTkEntry(r1, placeholder_text="name on the wisp's button", font=(FONT, 12))
            if names[i]:
                e.insert(0, names[i])
            e.pack(side="left", fill="x", expand=True, padx=(4, 0))
            e.bind("<FocusOut>", lambda ev, idx=i: self.update_move_name(idx))
            save_while_typing(e, lambda idx=i: self.update_move_name(idx))
            self.train_vars.append(var)
            self.move_entries.append(e)
            if flags[i]:
                r2 = ctk.CTkFrame(box, fg_color="transparent"); r2.pack(fill="x", padx=(28, 0), pady=(2, 2))
                self._picture_line(r2, f"move_{i + 1}", "Capture picture")

    def _manual_rows(self, card):
        from logic_library import MANUAL_MOVES
        self._section(card, "First menu")
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text="Clover Training", width=112, anchor="w", font=(FONT, 12, "bold")).pack(side="left")
        pt = self.logic.manual_point("clover_training")
        ctk.CTkButton(row, text="Pick spot", width=96, height=26, fg_color="#1c8f52", hover_color="#16743f",
                      command=lambda: self.pick_dialog_point("clover_training")).pack(side="left", padx=2)
        ctk.CTkLabel(row, text=f"({pt[0]}, {pt[1]})" if pt else "not set", font=(FONT, 12),
                     text_color="#7ee0a6" if pt else "#f08a7e").pack(side="left", padx=6)
        self._section(card, "Move spots", "Only the first 3 buttons of the list (no scrolling).")
        mm = self.logic.manual_moves()
        for i in range(MANUAL_MOVES):
            key = f"move_{i + 1}"
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
            var = ctk.BooleanVar(value=bool(mm[i].get("train")))
            ctk.CTkCheckBox(row, text=f"Move spot {i + 1}", variable=var, width=122, font=(FONT, 12, "bold"),
                            command=lambda i=i, v=var: (self.logic.manual_moves()[i].__setitem__("train", bool(v.get())),
                                                        self.settings.save())).pack(side="left")
            pt = self.logic.manual_point(key)
            ctk.CTkButton(row, text="Pick spot", width=96, height=26, fg_color="#1c8f52", hover_color="#16743f",
                          command=lambda k=key: self.pick_dialog_point(k)).pack(side="left", padx=2)
            ctk.CTkLabel(row, text=f"({pt[0]}, {pt[1]})" if pt else "not set", font=(FONT, 12),
                         text_color="#7ee0a6" if pt else "#f08a7e", width=62).pack(side="left", padx=2)
            sel = ctk.CTkOptionMenu(row, values=[str(k) for k in range(1, 10)], width=58, height=26,
                                    command=lambda v, i=i: (self.logic.manual_moves()[i].__setitem__("slot", int(v)),
                                                            self.settings.save()))
            sel.set(str(mm[i].get("slot") or i + 1))
            sel.pack(side="right")
            ctk.CTkLabel(row, text="slot", font=(FONT, 12)).pack(side="right", padx=(6, 3))

    def capture_dialog_button(self, key):
        self._capture_box(lambda box: self.logic.capture_dialog_button(key, box), "Button captured.",
                          after=self.build_dialog_card)

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
        card = getattr(self, "dialog_card", None)
        if card is not None and card.winfo_exists():
            if getattr(self, "_dialog_redraw", None):
                self.root.after_cancel(self._dialog_redraw)
            self._dialog_redraw = self.root.after(500, lambda: (setattr(self, "_dialog_redraw", None),
                                                                self.build_dialog_card()))

    def _minigame_extras(self, tab):
        hc = ctk.CTkFrame(tab, fg_color="transparent")
        hc.pack(fill="x")
        row = ctk.CTkFrame(hc, fg_color="transparent"); row.pack(fill="x", padx=4, pady=(2, 2))
        sw = ctk.CTkSwitch(row, text="Hide chat during the minigame", font=(FONT, 13, "bold"),
                           command=lambda: self.settings.set("hide_chat_in_minigame", bool(sw.get())))
        if self.settings.get("hide_chat_in_minigame"):
            sw.select()
        sw.pack(side="left")
        help_box(hc, "The chat's white Here / Global / Friends tabs look like silver clovers. Pick the chat "
                     "button at the top of Roblox: it's clicked to close chat when a minigame starts and "
                     "again to open it after.", sw)
        row = ctk.CTkFrame(hc, fg_color="transparent"); row.pack(fill="x", padx=4, pady=(4, 6))
        ctk.CTkButton(row, text="Pick chat button", width=150, height=28, fg_color="#1c8f52", hover_color="#16743f",
                      command=lambda: self.pick_point("chat_button")).pack(side="left")
        pos = self.settings.get("regions", {}).get("chat_button", [0, 0])
        self.chat_btn_lbl = ctk.CTkLabel(row, text=f"({pos[0]}, {pos[1]})" if any(pos) else "not set",
                                         font=(FONT, 12), text_color="#7ee0a6" if any(pos) else "#f08a7e")
        self.chat_btn_lbl.pack(side="left", padx=8)

        row = ctk.CTkFrame(tab, fg_color="transparent"); row.pack(fill="x", padx=4, pady=(4, 2))
        ctk.CTkButton(row, text="Clover Region", width=150, height=28, fg_color="#1c8f52", hover_color="#16743f",
                      command=lambda: self.pick_region("score")).pack(side="left")
        self.clover_region_lbl = ctk.CTkLabel(tab, text="", font=(FONT, 12), justify="left", wraplength=420)
        self.clover_region_lbl.pack(anchor="w", padx=4, pady=(0, 4))
        self._show_clover_region()
        self.overlay_switch = ctk.CTkSwitch(tab, text="Show Scan Areas", command=self.toggle_overlays, font=(FONT, 12))
        self.overlay_switch.pack(anchor="w", padx=4, pady=(2, 4))

    def build_gold_card(self):
        gc = getattr(self, "gold_card", None)
        if gc is None or not gc.winfo_exists():
            return
        for w in gc.winfo_children():
            w.destroy()
        mode = self.logic.gold_mode()
        head = ctk.CTkFrame(gc, fg_color="transparent"); head.pack(fill="x", padx=8, pady=(6, 0))
        t = ctk.CTkLabel(head, text="Gold Clover detection", font=(FONT, 14, "bold"), text_color="#1c8f52")
        t.pack(side="left")
        help_box(gc, "Drag a SMALL box over the spot where each move's 3rd clover appears." if mode == "manual" else
                     "Auto finds your hotbar by itself (it switches to the Roblox window you used last). Or drag ONE box over it with "
                     "Set hotbar: from the TOP of the clovers to the bottom of the icons, first icon to last.", t)
        seg = ctk.CTkSegmentedButton(gc, values=["Automatic", "Manual"], font=(FONT, 12, "bold"),
                                     command=lambda v: (self.settings.set("gold_mode", v.lower()), self.build_gold_card()))
        seg.set("Automatic" if mode == "auto" else "Manual")
        seg.pack(fill="x", padx=8, pady=4)
        self.gold_status = {}
        if mode == "manual":
            regions = self.settings.get("regions", {})
            flags = self.logic.train_flags()
            for i in [k + 1 for k, on in enumerate(flags) if on]:
                row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=2)
                ctk.CTkButton(row, text=f"Set Move {i}'s spot", width=150, height=28, fg_color="#1c8f52",
                              hover_color="#16743f", command=lambda idx=i: self.pick_region(f"gold_clover_{idx}")).pack(side="left")
                ok = any(regions.get(f"gold_clover_{i}", [0, 0, 0, 0]))
                lbl = ctk.CTkLabel(row, text="set" if ok else "not set", font=(FONT, 12),
                                   text_color="#7ee0a6" if ok else "#f08a7e")
                lbl.pack(side="left", padx=8)
                self.gold_status[i] = lbl
            self._gold_color_rows(gc)
            ctk.CTkLabel(gc, text="", height=4).pack()
            return

        hb = self.settings.settings.setdefault("gold_hotbar", {"region": [0, 0, 0, 0], "slots": 6})
        row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkButton(row, text="Auto", width=62, height=28, fg_color="#1c8f52", hover_color="#16743f",
                      command=self.auto_gold_hotbar).pack(side="left", padx=(0, 4))
        ctk.CTkButton(row, text="Set hotbar", width=96, height=28, fg_color="#34463d", hover_color="#2a3a33",
                      command=self.pick_gold_hotbar).pack(side="left")
        ok = self.logic.gold_hotbar()[0] is not None
        ctk.CTkLabel(row, text="set" if ok else "not set", font=(FONT, 12),
                     text_color="#7ee0a6" if ok else "#f08a7e").pack(side="left", padx=6)
        ctk.CTkLabel(row, text="Slots", font=(FONT, 12)).pack(side="left", padx=(4, 2))
        om = ctk.CTkOptionMenu(row, values=[str(i) for i in range(1, 11)], width=52, height=26,
                               command=lambda v: (hb.__setitem__("slots", int(v)), self.settings.save(), self.build_gold_card()))
        om.set(str(hb.get("slots", 6)))
        om.pack(side="left")
        ctk.CTkButton(row, text="Show", width=56, height=28, fg_color="#34463d", hover_color="#2a3a33",
                      command=self.show_gold_spots).pack(side="right")
        ctk.CTkButton(row, text="Test", width=56, height=28, fg_color="#34463d", hover_color="#2a3a33",
                      command=self.test_gold).pack(side="right", padx=4)
        ctk.CTkLabel(gc, text="Which hotbar slot each move is: Setup → step 2 Moves and wisp dialogue → slot.",
                     font=(FONT, 12), text_color="#cfc6ab", wraplength=400, justify="left", anchor="w").pack(
            fill="x", padx=8)
        self.gold_test_lbl = ctk.CTkLabel(gc, text="", font=(FONT, 12), justify="left", wraplength=420, anchor="w")
        self.gold_test_lbl.pack(fill="x", padx=8)
        self._gold_color_rows(gc)
        ctk.CTkLabel(gc, text="", height=4).pack()

    def _gold_color_rows(self, gc):
        own = self.settings.get("gold_color")
        row = ctk.CTkFrame(gc, fg_color="transparent"); row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(row, text="Gold colour", font=(FONT, 12, "bold")).pack(side="left")
        shown = own or list(self.logic.GOLD_CLOVER_COLOR)
        ctk.CTkFrame(row, width=22, height=22, corner_radius=4, border_width=1, border_color="#a39d86",
                     fg_color="#%02x%02x%02x" % tuple(int(v) for v in shown[:3])).pack(side="left", padx=6)
        ctk.CTkLabel(row, text=(f"your pick {tuple(own[:3])}" if own else "built-in"), font=(FONT, 12),
                     text_color="#cfc6ab").pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Pick colour", width=90, height=26, fg_color="#1c8f52", hover_color="#16743f",
                      command=self.pick_gold_color).pack(side="left", padx=2)
        if own:
            ctk.CTkButton(row, text="Built-in", width=70, height=26, fg_color="#34463d", hover_color="#2a3a33",
                          command=lambda: (self.settings.set("gold_color", None), self.build_gold_card())).pack(side="left", padx=2)

    def pick_gold_color(self):
        self._hide_for_pick()

        def done(color):
            self.root.deiconify()
            self.settings.set("gold_color", [int(c) for c in color[:3]])
            self.log(f"Gold colour set to {tuple(color[:3])} - press Test to check a maxed move reads gold.")
            self.build_gold_card()
        ColorPicker(done)

    def auto_gold_hotbar(self):
        def run():
            from utils import go_to_roblox
            hwnd = go_to_roblox(self.log)
            if not hwnd:
                return
            self.logic._roblox_hwnd = hwnd
            if self.logic.auto_find_gold_hotbar():
                self.root.after(0, lambda: (self.build_gold_card(), self.show_gold_spots()))
        threading.Thread(target=run, daemon=True).start()

    def pick_gold_hotbar(self):
        self._hide_for_pick()

        def done(x1, y1, x2, y2):
            self.root.deiconify()
            hb = self.settings.settings.setdefault("gold_hotbar", {"slots": 6})
            hb["region"] = [x1, y1, x2, y2]
            hb.pop("spots", None)
            self.settings.save()
            self.build_gold_card()
            self.log("Hotbar saved. Press Show to check the yellow boxes sit on each 3rd-clover spot.")
        Overlay(done)

    def show_gold_spots(self):
        r, n = self.logic.gold_hotbar()
        if not r:
            self.log("Set the hotbar first."); return
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

    def setup_clover_tab(self, parent):
        tab = parent
        t = ctk.CTkLabel(tab, text="Clover colours (what gets clicked)", font=(FONT, 14, "bold"), text_color="#1c8f52")
        t.pack(anchor="w", padx=18, pady=(14, 4))
        help_box(tab, "Tol (tolerance) is how far a colour may drift from the picked one.\n"
                      "Lower (1-10): very strict, best for stable lighting. Higher (20-40): allows in-game lighting shifts.\n"
                      "Clicking wrong spots? Lower it. Not clicking the clovers? Raise it.", t)

        self.color_previews, self.color_labels = {}, {}
        self.clover_tol_sliders, self.clover_tol_labels = {}, {}

        colors = self.settings.get("clover_colors", self.DEFAULT_CLOVER_COLORS)
        clover_tols = self.settings.get("clover_tolerances", {})

        for c in ["bronze", "silver", "gold"]:
            card = ctk.CTkFrame(tab, fg_color="#15201b", border_color="#2a3a33", border_width=1, corner_radius=8)
            card.pack(pady=4, fill="x", padx=15)

            f_color = ctk.CTkFrame(card, fg_color="transparent")
            f_color.pack(pady=(6, 2), fill="x", padx=10)

            ctk.CTkLabel(f_color, text=c.capitalize(), width=60, font=(FONT, 12, "bold"), text_color="#ffffff").pack(side="left", padx=5)

            color = colors.get(c, self.DEFAULT_CLOVER_COLORS[c])
            preview = ctk.CTkFrame(f_color, width=20, height=20, fg_color='#%02x%02x%02x' % tuple(color), corner_radius=4)
            preview.pack(side="left", padx=5)
            self.color_previews[c] = preview

            lbl = ctk.CTkLabel(f_color, text=str(color), font=(FONT, 12), text_color="#e8dfc5")
            lbl.pack(side="left", padx=5)
            self.color_labels[c] = lbl

            ctk.CTkButton(f_color, text="Pick", width=50, fg_color="#1c8f52", hover_color="#16743f", command=lambda cl=c: self.pick_color(cl)).pack(side="right", padx=5)

            f_tol = ctk.CTkFrame(card, fg_color="transparent")
            f_tol.pack(pady=(0, 6), fill="x", padx=10)

            ctk.CTkLabel(f_tol, text="Tol:", width=30, font=(FONT, 12), text_color="#e8dfc5").pack(side="left", padx=(60, 5))

            tol_val = clover_tols.get(c, self.DEFAULT_CLOVER_TOLERANCES[c])
            slider = ctk.CTkSlider(f_tol, from_=1, to=100, number_of_steps=99, height=16,
                                  command=lambda val, cl=c: self.update_clover_tolerance(cl, val))
            slider.set(tol_val)
            slider.pack(side="left", fill="x", expand=True, padx=5)
            self.clover_tol_sliders[c] = slider

            val_lbl = ctk.CTkLabel(f_tol, text=str(int(tol_val)), width=35, font=(FONT, 13, "bold"), text_color="#ffffff")
            val_lbl.pack(side="right", padx=5)
            self.clover_tol_labels[c] = val_lbl

        ctk.CTkButton(tab, text="Reset to Defaults", fg_color="#d9483b", hover_color="#b83a2f", font=(FONT, 12, "bold"), command=self.reset_clover_colors).pack(pady=10)

    def update_move_name(self, idx):
        names = self.logic.move_names() if hasattr(self.logic, "move_names") else self.settings.get("move_names")
        new_name = self.move_entries[idx].get()
                                                              
        if new_name != names[idx]:
            old = names[idx]
            names[idx] = new_name
            self.settings.set("move_names", names)
            norm = lambda t: "".join(c for c in (t or "").lower() if c.isalnum())
            if norm(old) != norm(new_name) and hasattr(self.logic, "reset_move_gold"):
                self.logic.reset_move_gold(idx)
        self.update_gold_display()

    def update_clover_tolerance(self, color_type, val):
        tols = self.settings.get("clover_tolerances", {})
        tols[color_type] = int(val)
        self.settings.set("clover_tolerances", tols)
        if color_type in self.clover_tol_labels:
            self.clover_tol_labels[color_type].configure(text=str(int(val)))
        self.log(f"{color_type.capitalize()} Tolerance: {int(val)}")

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

    def _show_clover_region(self):
        r = self.settings.get("regions", {}).get("score", [0, 0, 0, 0])
        mine = r[2] > r[0] and r[3] > r[1]
        if hasattr(self, "clover_region_lbl"):
            self.clover_region_lbl.configure(
                text=f"YOUR box is used {tuple(r)}, below Roblox's top bar - Full Auto Setup switches back "
                     "to automatic" if mine else
                "automatic: the whole Roblox window below Roblox's top bar (Show Scan Areas draws it)",
                text_color="#e6b84f" if mine else "#7ee0a6")

    def setup_statistics_tab(self):
        tab = fast_scroll_frame(self.tabview.tab("Statistics"))
        ctk.CTkLabel(tab, text="Gold Statistics", font=(FONT, 18, "bold"), text_color="#1c8f52").pack(pady=(12, 8))

        card = ctk.CTkFrame(tab, **CARD); card.pack(fill="x", padx=20, pady=6)
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=12, pady=(8, 2))
        self.gold_label = ctk.CTkLabel(row, text="", font=(FONT, 15, "bold"), text_color="#e6b84f", anchor="w")
        self.gold_label.pack(side="left")
        help_box(card, "Every training ever (250 gold each), It never resets - not even with "
                       "Reset all.", self.gold_label)
        ctk.CTkLabel(card, text="Never resets", font=(FONT, 11), text_color="#a39d86").pack(anchor="w", padx=12,
                                                                                            pady=(0, 8))

        spells = ctk.CTkFrame(tab, **CARD); spells.pack(fill="x", padx=20, pady=6)
        head = ctk.CTkFrame(spells, fg_color="transparent"); head.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkButton(head, text="Reset all", width=80, height=24, font=(FONT, 11), fg_color="#34463d",
                      hover_color="#b83a2f", command=self.reset_gold).pack(side="right")
        self.spells_label = ctk.CTkLabel(head, text="", font=(FONT, 14, "bold"), anchor="w")
        self.spells_label.pack(side="left")
        help_box(spells, "Gold used per move since you last reset it, added up. Reset one move or all of them "
                         "when you start training something new - the lifetime number keeps counting.",
                 self.spells_label)
        self.move_stats_labels = [self._stat_row(spells, "", (FONT, 13), "#ffffff", lambda i=i: self.reset_stat(i))
                                  for i in range(self.logic.stats_moves())]
        ctk.CTkFrame(spells, fg_color="transparent", height=4).pack()
        self.update_gold_display()

    def _stat_row(self, parent, name, font, color, on_reset):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=3)
        ctk.CTkButton(row, text="Reset", width=60, height=24, font=(FONT, 11), fg_color="#34463d",
                      hover_color="#b83a2f", command=on_reset).pack(side="right")
        lbl = ctk.CTkLabel(row, text=name, font=font, text_color=color, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        return lbl

    def _move_stats(self):
        nine = getattr(self.logic, "_nine", None)
        if nine:
            return nine("move_names", ""), nine("move_stats", 0)
        return self.settings.get("move_names", ["", "", ""]), self.settings.get("move_stats", [0, 0, 0])

    def update_gold_display(self):
        lbl = getattr(self, "gold_label", None)
        if lbl is None or not lbl.winfo_exists():
            return
        lbl.configure(text=f"Lifetime used: {self.logic.lifetime_gold():,} gold")
        self.spells_label.configure(text=f"Current sum of spells: {self.logic.spells_gold():,} gold")
        names, stats = self._move_stats()
        for i, row in enumerate(getattr(self, "move_stats_labels", [])[:len(names)]):
            row.configure(text=f"{names[i] or f'Move {i + 1}'}: {int(stats[i] or 0):,}")

    def reset_stat(self, i):
        names, _ = self._move_stats()
        self.logic.reset_spells_gold(i)
        self.log(f"{names[i] or f'Move {i + 1}'}: gold used reset (lifetime keeps counting)")
        self.update_gold_display()

    def reset_gold(self):
        self.logic.reset_spells_gold()
        self.log("All moves' gold reset (lifetime keeps counting)")
        self.update_gold_display()
