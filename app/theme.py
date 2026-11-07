import copy
import os
import re
import customtkinter as ctk

THEMES = {
    "Green": {"tint": None, "swap": {}},
    "Crimson": {
        "tint": (1.0, 0.70, 0.70),
        "swap": {"#1c8f52": "#a3262e", "#16743f": "#861d24", "#123326": "#3a1418", "#14432a": "#4a1a1f"},
    },
    "Midnight": {
        "tint": (0.80, 0.74, 1.0),
        "swap": {"#1c8f52": "#6d4bd8", "#16743f": "#5838b8", "#123326": "#231a45", "#14432a": "#2c2158",
                 "#e6b84f": "#7fd6e8", "#c99a2e": "#5fb3c8", "#5c4515": "#1f4a55",
                 "#f3ecd8": "#e9e6f5", "#e8dfc5": "#ddd8ee", "#cfc6ab": "#c3bedb", "#a39d86": "#9c97b5",
                 "#857f6c": "#7d7896"},
    },
    "Royal": {
        "tint": (0.74, 0.84, 1.0),
        "swap": {"#1c8f52": "#2f5fd0", "#16743f": "#244bab", "#123326": "#16244a", "#14432a": "#1b2d5c",
                 "#f3ecd8": "#f4f6fb", "#e8dfc5": "#e3e8f2", "#cfc6ab": "#c9d1e0", "#a39d86": "#9aa5b8",
                 "#857f6c": "#7e8899"},
    },
}
DEFAULT = "Royal"

CUSTOM_DEFAULT = {"primary": "#2f5fd0", "hover": "#244bab", "accent": "#e6b84f"}


def _custom_file():
    from settings import get_base_path
    return os.path.join(get_base_path(), "theme_custom.json")


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _shade(h, f):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * f))) for v in _rgb(h))


def custom_colors():
    cols = dict(CUSTOM_DEFAULT)
    try:
        import json
        with open(_custom_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        for k in cols:
            v = str(data.get(k) or "").strip().lower()
            if _HEX.fullmatch(v):
                cols[k] = v
    except (OSError, ValueError):
        pass
    return cols


def _build_custom(cols):
    p, hv, ac = cols["primary"], cols["hover"], cols["accent"]
    top = max(_rgb(p)) or 1
    tint = tuple(0.72 + 0.28 * v / top for v in _rgb(p))
    return {"tint": tint,
            "swap": {"#1c8f52": p, "#16743f": hv, "#123326": _shade(p, 0.30), "#14432a": _shade(p, 0.38),
                     "#e6b84f": ac, "#c99a2e": _shade(ac, 0.85), "#5c4515": _shade(ac, 0.40)}}


def save_custom(cols):
    import json
    clean = {k: str(cols.get(k) or CUSTOM_DEFAULT[k]).lower() for k in CUSTOM_DEFAULT}
    try:
        with open(_custom_file(), "w", encoding="utf-8") as fh:
            json.dump(clean, fh, indent=2)
    except OSError:
        pass
    THEMES["Custom"] = _build_custom(clean)


THEMES["Custom"] = _build_custom(dict(CUSTOM_DEFAULT))
_current = DEFAULT
_base_theme = None
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def _file():
    from settings import get_base_path
    return os.path.join(get_base_path(), "theme.txt")


def saved():
    try:
        with open(_file(), encoding="utf-8") as f:
            name = f.read().strip()
        return name if name in THEMES else DEFAULT
    except OSError:
        return DEFAULT


def current():
    return _current


def c(color):
    if not isinstance(color, str) or not _HEX.fullmatch(color):
        return color
    th = THEMES[_current]
    low = color.lower()
    if low in th["swap"]:
        return th["swap"][low]
    if not th["tint"]:
        return color
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    if g >= r and g >= b and g - min(r, g, b) <= 0.4 * g + 8:
        rf, gf, bf = th["tint"]
        return "#%02x%02x%02x" % tuple(min(255, int(g * f)) for f in (rf, gf, bf))
    return color


def _map(v):
    if isinstance(v, (list, tuple)):
        return type(v)(c(x) for x in v)
    return c(v)


def _colors(kw):
    for k in list(kw):
        if "color" in k:
            kw[k] = _map(kw[k])
    return kw


def _patch(cls):
    if "__init__" in cls.__dict__:
        init = cls.__init__

        def __init__(self, *a, **kw):
            init(self, *a, **_colors(kw))
        cls.__init__ = __init__
    if "configure" in cls.__dict__:
        conf = cls.configure

        def configure(self, *a, **kw):
            return conf(self, *a, **_colors(kw))
        cls.configure = configure


def install(theme_file):
    global _base_theme
    ctk.set_default_color_theme(theme_file)
    _base_theme = copy.deepcopy(ctk.ThemeManager.theme)
    THEMES["Custom"] = _build_custom(custom_colors())
    for name in dir(ctk):
        cls = getattr(ctk, name)
        if name.startswith("CTk") and isinstance(cls, type):
            _patch(cls)
    apply(saved())


def apply(name, save=False):
    global _current
    _current = name if name in THEMES else DEFAULT
    th = copy.deepcopy(_base_theme)
    for d in th.values():
        for k, v in d.items():
            if "color" in k:
                d[k] = _map(v)
    ctk.ThemeManager.theme.clear()
    ctk.ThemeManager.theme.update(th)
    if save:
        try:
            with open(_file(), "w", encoding="utf-8") as f:
                f.write(_current)
        except OSError:
            pass
