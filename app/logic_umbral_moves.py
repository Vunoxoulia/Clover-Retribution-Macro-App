"""Umbral Abyss Stone's moves: the Skill Macro's move list (hotbar snapshots = ready check, priority, aim,
delays, repeat, M2 / M1 click), kept apart from your Skill Macro loadouts, plus the kill check (reading the
reward popup, like Items)."""
import copy
import difflib
import time

from logic_smart import SmartMacroLogic, DEFAULT_SMART
from utils import RobloxInputDriver

UMBRAL_SNAP_FOLDER = "Umbral Abyss Stone"      # its own snapshot folder (data/smart_templates/<this>)
KILL_WORDS_DEFAULT = ["mastery", "exp"]


class UmbralMoves(SmartMacroLogic):
    """The Skill Macro engine on Umbral's own settings ('umbral_skill'). `owner` = the Umbral macro:
    its Start / Stop is this one's too."""

    def __init__(self, owner):
        self.owner = owner
        super().__init__(owner.app)

    # follows the Umbral macro's own running flag (Stop / F6 stops a fight mid-move)
    @property
    def running(self):
        return bool(getattr(self.owner, "running", False))

    @running.setter
    def running(self, value):
        pass

    @property
    def cfg(self):
        st = self.app.settings.settings
        cfg = st.get("umbral_skill")
        if not isinstance(cfg, dict):
            cfg = {"rotation": copy.deepcopy(DEFAULT_SMART["rotation"]), "only_when_focused": True}
            st["umbral_skill"] = cfg
        cfg.setdefault("only_when_focused", True)
        rot = cfg.setdefault("rotation", {})
        for k, v in DEFAULT_SMART["rotation"].items():
            rot.setdefault(k, copy.deepcopy(v))
        return cfg

    def loadouts(self):                                  # one fixed set, no Skill Macro loadouts here
        return {UMBRAL_SNAP_FOLDER: {}}

    def active_loadout(self):
        return UMBRAL_SNAP_FOLDER

    def moves(self):
        moves = super().moves()
        for m in moves:
            if not m.get("umbral_v1"):                   # new move: aim at the Juggernaut by default
                m["mouse_mode"] = "jug"
                m["umbral_v1"] = True
        self._carry_old_combo(moves)
        return moves

    def _carry_old_combo(self, moves):
        """Once: the old 3-step combo becomes the moves' priority order, waits and clicks."""
        st = self.app.settings.settings
        old = st.get("umbral_combo")
        if not old or st.get("umbral_combo_carried"):
            return
        st["umbral_combo_carried"] = True
        n = 0
        for step in old:
            key = str(step.get("key") or "").strip().lower()
            m = next((mv for mv in moves if str(mv.get("key")) == key), None)
            if not m:
                continue
            n += 1
            m["priority"] = n
            m["repeat"] = int(step.get("repeat") or 1)
            if step.get("click"):
                m["click"], m["click_btn"] = True, step.get("click_btn", "m2")
                m["m1_delay"] = float(step.get("delay") or 0.3)
                m["after_click"] = float(step.get("after_click") or 0.1)
            else:
                m["delay_after"] = float(step.get("delay") or 0)
        for m in moves:                                  # moves that weren't in the combo go after it
            if str(m.get("key")) not in [str(s.get("key") or "").strip().lower() for s in old]:
                n += 1
                m["priority"] = n
        self.app.settings.save()

    # ---------- one cast ----------
    def cast(self, slot, m, aim_at):
        """mouse move -> delay before -> key -> M2 / M1 (if ticked) -> [repeat] -> delay after.
        aim_at() = where the Juggernaut is now (or None). Returns True when it really cast
        (with a snapshot: the slot no longer looks ready)."""
        for n in range(max(1, int(m.get("repeat") or 1))):
            if not self.running:
                return False
            mode = m.get("mouse_mode", "none")
            with RobloxInputDriver._lock:
                if mode == "jug":
                    pos = aim_at()
                    if pos:
                        self.owner.aim_at(pos)
                elif mode == "move":
                    self.owner.aim_at((int(m.get("x", 0)), int(m.get("y", 0))))
                self._wait(float(m.get("delay_before") or 0))
                self._press(m["key"])
                self._m1_after(m)
            if n < int(m.get("repeat") or 1) - 1:
                self._wait(max(0.05, float(m.get("repeat_delay") or 0.15)))
        self._wait(max(float(m.get("delay_after") or 0), float(self.cfg["rotation"]["cast_delay"])))
        score = self.read_slots().get(slot)
        if score is not None and score >= self.slot_threshold(slot):
            return False                                 # still ready: the key didn't take
        self.last_cast[slot] = time.time()
        self.cast_count[slot] = self.cast_count.get(slot, 0) + 1
        return True

    # ---------- kill check: the reward popup (read like Items) ----------
    def kill_region(self):
        r = self.app.settings.get("regions", {}).get("umbral_kill_region") or [0, 0, 0, 0]
        return r if r[2] > r[0] and r[3] > r[1] else None

    def kill_words(self):
        words = self.app.settings.get("umbral_kill_words")
        if not isinstance(words, list):
            words = list(KILL_WORDS_DEFAULT)
        return [w for w in (str(x).strip() for x in words) if w]

    def read_kill_text(self):
        region = self.kill_region()
        if not region:
            return []
        res = self.utils.get_text_from_region(region)
        if self.utils.ocr_reader is False:
            self.app.log(self.utils.ocr_error or "Text reading (OCR) couldn't start.")
        return [text for _, text, conf in res if conf > 0.4]

    def kill_word_in(self, texts):
        """The first kill word found in the read lines (same forgiving match as Items), or None."""
        for word in self.kill_words():
            w = self._norm(word)
            for t in texts:
                t = self._norm(t)
                if w and (w in t or any(difflib.SequenceMatcher(None, w, t[i:i + len(w)]).ratio() >= 0.8
                                        for i in range(0, max(1, len(t) - len(w) + 1)))):
                    return word
        return None
