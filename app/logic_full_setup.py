"""Full Auto Setup for the Library: one button sets up everything the Library needs.

You record / pick the ROUTE yourself (it's the one thing that stays manual). Then, standing at the desk:
  0. checks      text reader works, Roblox isn't admin, a route is recorded
  1. hotbar      finds it + the gold-clover spots, reads every filled slot's name
  2. wisp        walks the route, opens the dialogue
  3. menu        finds 'Clover Training' by its words, saves its picture, clicks it
  4. move list   reads every move (scrolling to Nevermind), keeps each button's picture
  5. match       hotbar slot -> move, each move's one unique word
  6. mode        the one you picked: Auto (words) or Image (also saves each button's picture); not Manual
  7. minigame    on the first Start after Apply: picks the move, sees the minigame start (black bars /
                 big change), saves the minigame snapshot by itself and plays it
  8. gold        checks which moves are already maxed
Nothing is lost if you cancel at the end: the old settings are put back.
"""
import copy
import time

KEPT = ("gold_mode", "move_names", "train_moves", "gold_move_slots", "dialog_mode", "gold_hotbar", "regions")


class FullSetup:
    def __init__(self, lib):
        self.lib = lib                     # the LibraryLogic
        self.app = lib.app
        self.notes = []                    # what was set (shown in the summary)
        self.backup = {k: copy.deepcopy(self.app.settings.settings.get(k)) for k in KEPT}

    # ---------- helpers ----------
    def say(self, msg):
        self.app.log(f"Full setup: {msg}")

    def note(self, ok, text):
        self.notes.append(("OK  " if ok else "--  ") + text)

    def alive(self):
        return self.lib.running

    def fail(self, step, why):
        path = self.lib.save_debug_shot(f"full_setup_{step}")
        self.say(f"stopped at '{step}': {why}")
        return {"ok": False, "step": step, "why": why, "debug": path, "notes": self.notes}

    def restore(self):
        """Cancel: put the settings back the way they were before the setup."""
        st = self.app.settings.settings
        for k, v in self.backup.items():
            if v is None:
                st.pop(k, None)
            else:
                st[k] = v
        self.app.settings.save()

    # ---------- the run ----------
    def run(self):
        lib = self.lib
        from utils import SpatialUtils, roblox_admin_problem
        # 0. checks
        mode = lib.dialog_mode()                         # the mode YOU picked: Auto (words) or Image (pictures)
        if mode == "manual":
            return self.fail("checks", "Full Auto Setup works with Auto or Image mode - pick one in Wisp dialogue")
        if not SpatialUtils.ocr_works():
            return self.fail("checks", SpatialUtils.ocr_error or "the text reader doesn't work - install the "
                                                                 "Visual C++ Redistributable (x64)")
        if roblox_admin_problem():
            return self.fail("checks", "Roblox runs as administrator - open it normally")
        if not lib.load_route():
            return self.fail("checks", "no route to the wisp - pick or record one first (Route, F9)")
        if not lib.wait_focus_for_test(15):
            return self.fail("checks", "Roblox wasn't clicked into")

        # 1. hotbar
        self.say("finding your hotbar...")
        filled = lib.auto_find_gold_hotbar()
        if not filled:
            return self.fail("hotbar", "couldn't see the hotbar")
        hotbar = [(s, t) for s, t in (lib.read_hotbar_names() or []) if s <= 9]
        if not any(t for _, t in hotbar):
            return self.fail("hotbar", "couldn't read any move name on the hotbar")
        st = self.app.settings.settings                  # saved once, by apply_auto_setup below
        st["gold_mode"] = "auto"                         # use the spots just found (not old manual boxes)
        lib.set_clover_region_auto()
        self.note(True, f"hotbar: {filled} slot(s), gold-clover spots set")
        if hasattr(self.app, "show_gold_spots"):           # show the yellow boxes for 3 s: proof it worked
            self.app.root.after(0, self.app.show_gold_spots)

        # 2. wisp
        self.say("walking to the wisp...")
        lib.go_to_wisp()
        if not self.alive():
            return self.fail("wisp", "stopped")
        st["dialog_mode"] = "auto"                       # read by words while setting up
        if not lib.open_dialogue():
            return self.fail("wisp", "the dialogue didn't open (are you at the wisp?)")

        # 3. first menu
        target, end = None, time.time() + 20
        while self.alive() and time.time() < end and not target:
            target = lib.find_training_button()
            if not target:
                time.sleep(0.4)
        if not target:
            return self.fail("menu", "couldn't find 'Clover Training'")
        (tx, ty), _ = target
        self._save_button_picture("clover_training", tx, ty)
        lib.human_click(tx, ty, duration=0.15)
        lib._park_mouse()
        time.sleep(lib.after_training_wait())
        self.note(True, "Clover Training found and saved")

        # 4. move list
        self.say("reading the move list...")
        listed = lib.scan_move_list(alive=self.alive)
        if not listed:
            return self.fail("move list", "couldn't read the move list")
        pictures = dict(listed)
        names = list(pictures)
        self.note(True, f"move list: {len(names)} move(s)")

        # 5. match + 6. mode
        rows = lib.match_hotbar_to_list(hotbar, names)
        rows = [r for r in rows if r["match"]]
        if not rows:
            return self.fail("match", "none of the hotbar moves were found in the move list")
        st["dialog_mode"] = mode                         # back to your mode (it read by words until now)
        weak = [r["match"] for r in rows if not r.get("keyword")] if mode == "auto" else []
        msg = f"wisp dialogue: {mode.capitalize()} mode"
        if weak:
            msg += f" (no unique word for: {', '.join(weak)} - its full name is used; Image mode tells them apart better)"
        self.note(not weak, msg)

        # apply: hotbar slot N -> Move N, every found move ticked for now (you choose at the end)
        chosen = [{"slot": r["slot"], "name": r["match"], "keyword": r.get("keyword"), "train": True,
                   "move": r["slot"] - 1} for r in rows]
        lib.apply_auto_setup(chosen, pictures)
        if mode == "image":
            bad = [c["name"] for c in chosen if pictures.get(c["name"]) is None]
            if bad:
                self.note(False, "no clear button picture of: " + ", ".join(bad)
                          + " - Capture them in Wisp dialogue (debug shot in data/debug)")

        # 7. minigame: done on the first Start after Apply (it picks a move, catches the minigame, saves the
        #    snapshot by itself and plays it) - see LibraryLogic._library_loop / capture_minigame_next
        self.note(True, "minigame detector: set up on the first Start (it picks a move and catches it)")

        # 8. gold
        gold = {c["move"]: lib.move_is_gold(c["move"]) for c in chosen}
        self.note(True, "gold check done")
        self.say("done - check the summary and press Apply.")
        return {"ok": True, "chosen": chosen, "gold": gold, "notes": self.notes}

    def _save_button_picture(self, key, cx, cy):
        """Save the dialogue button under (cx, cy) as an Image-mode picture."""
        try:
            l, t = self.lib.get_roblox_window_region()[:2]
            _, boxes = self.lib.find_dialog(self.lib._screen())
            for x, y, w, h in boxes:
                if x <= cx - l <= x + w and y <= cy - t <= y + h:
                    return self.lib.capture_dialog_button(key, [l + x, t + y, l + x + w, t + y + h])
        except Exception:
            pass
        return False
