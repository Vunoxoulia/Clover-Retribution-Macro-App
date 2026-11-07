import copy
import time

KEPT = ("gold_mode", "move_names", "train_moves", "gold_move_slots", "dialog_mode", "gold_hotbar", "regions")


class FullSetup:
    def __init__(self, lib):
        self.lib = lib
        self.app = lib.app
        self.notes = []
        self.backup = {k: copy.deepcopy(self.app.settings.settings.get(k)) for k in KEPT}

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
        st = self.app.settings.settings
        for k, v in self.backup.items():
            if v is None:
                st.pop(k, None)
            else:
                st[k] = v
        self.app.settings.save()

    def run(self):
        lib = self.lib
        from utils import SpatialUtils, roblox_admin_problem
        mode = lib.dialog_mode()
        if mode == "manual":
            return self.fail("checks", "Full Auto Setup works with Image mode - pick Image in Wisp dialogue")
        if not SpatialUtils.ocr_works():
            return self.fail("checks", SpatialUtils.ocr_error or "the text reader doesn't work - install the "
                                                                 "Visual C++ Redistributable (x64)")
        if roblox_admin_problem():
            return self.fail("checks", "Roblox runs as administrator - open it normally")
        if not lib.load_route():
            return self.fail("checks", "no route to the wisp - pick or record one first (Route, F9)")
        if not lib.wait_focus_for_test(15):
            return self.fail("checks", "Roblox wasn't clicked into")

        self.say("finding your hotbar...")
        filled = lib.auto_find_gold_hotbar()
        if not filled:
            return self.fail("hotbar", "couldn't see the hotbar")
        hotbar = [(s, t) for s, t in (lib.read_hotbar_names() or []) if s <= 9]
        if not any(t for _, t in hotbar):
            return self.fail("hotbar", "couldn't read any move name on the hotbar")
        st = self.app.settings.settings
        st["gold_mode"] = "auto"
        lib.set_clover_region_auto()
        self.note(True, f"hotbar: {filled} slot(s), gold-clover spots set")
        if hasattr(self.app, "show_gold_spots"):
            self.app.root.after(0, self.app.show_gold_spots)

        self.say("walking to the wisp...")
        lib.go_to_wisp()
        if not self.alive():
            return self.fail("wisp", "stopped")
        if not lib.open_dialogue():
            return self.fail("wisp", "the dialogue didn't open (are you at the wisp?)")

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

        self.say("reading the move list...")
        listed = lib.scan_move_list(alive=self.alive, keep_unread=mode == "image")
        if not listed:
            return self.fail("move list", "couldn't read the move list")
        pictures = dict(listed)
        names = list(pictures)
        self.note(True, f"move list: {len(names)} move(s)")

        rows = lib.match_hotbar_to_list(hotbar, names)
        matched = [r for r in rows if r["match"]]
        self.note(len(matched) == len(rows), f"matched {len(matched)} of {len(rows)} hotbar slot(s)"
                  + ("" if len(matched) == len(rows) else " - pick the others from their lists below"))
        self.note(True, "wisp dialogue: Image mode")
        if mode == "image":
            bad = [r["match"] for r in matched if pictures.get(r["match"]) is None]
            if bad:
                self.note(False, "no clear button picture of: " + ", ".join(bad)
                          + " - Capture them in Wisp dialogue (debug shot in data/debug)")
            unread = sum(lib.UNREAD_NAME in n for n in names)
            if unread:
                self.note(False, f"{unread} button(s) couldn't be read - pick them from the lists below by their picture")


        gold = {r["slot"]: lib.slot_is_gold(r["slot"]) for r in rows}
        self.note(True, "gold check done")
        self.say("done - check the summary and press Apply.")
        return {"ok": True, "rows": rows, "names": names, "pictures": pictures, "gold": gold, "notes": self.notes}

    def _save_button_picture(self, key, cx, cy):
        try:
            l, t = self.lib.get_roblox_window_region()[:2]
            _, boxes = self.lib.find_dialog(self.lib._screen())
            for x, y, w, h in boxes:
                if x <= cx - l <= x + w and y <= cy - t <= y + h:
                    return self.lib.capture_dialog_button(key, [l + x, t + y, l + x + w, t + y + h])
        except Exception:
            pass
        return False
