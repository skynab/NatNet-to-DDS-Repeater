"""Translations for the GUIs.

Each language is one JSON file in the top-level `locales/` folder, named by
language code (en.json, zh_CN.json, ...). A file maps a message id to its
text. Text can contain {placeholders} in Python str.format syntax, such as
{fps:.1f}; translations must keep the same placeholder names, but may move
them. Keys starting with "_" are metadata ("_language_name" is shown in the
language menu). A missing message falls back to English.

Dropping a new <code>.json file into locales/ adds a language. To check every
file against en.json (missing ids, unknown ids, placeholder mismatches):

    python -m natnet_dds.i18n
"""
import json
import locale
import os
import string
import sys

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")
FALLBACK = "en"
# The chosen language is shared by both GUIs.
PREFS_FILE = os.path.join(os.path.expanduser("~"), ".natnet_dds_gui_language.json")

_cache = {}
_current = FALLBACK


def _load(code):
    if code not in _cache:
        try:
            with open(os.path.join(LOCALES_DIR, code + ".json"), encoding="utf-8") as f:
                _cache[code] = json.load(f)
        except (OSError, ValueError) as e:
            print("[i18n] could not load %s.json: %s" % (code, e), file=sys.stderr)
            _cache[code] = {}
    return _cache[code]


def available_languages():
    """[(code, display name)] for every file in locales/, English first."""
    try:
        codes = sorted(f[:-5] for f in os.listdir(LOCALES_DIR) if f.endswith(".json"))
    except OSError:
        codes = []
    codes.sort(key=lambda c: (c != FALLBACK, c))
    return [(c, _load(c).get("_language_name", c)) for c in codes]


def set_language(code):
    global _current
    _current = code if code in dict(available_languages()) else FALLBACK


def current_language():
    return _current


def tr(key, **kwargs):
    """Translated text for `key`, formatted with kwargs."""
    text = _load(_current).get(key)
    if text is None:
        text = _load(FALLBACK).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # A broken translation should never crash the GUI: use English.
            return _load(FALLBACK).get(key, key).format(**kwargs)
    return text


def _system_language():
    try:
        loc = locale.getlocale()[0] or ""
    except ValueError:
        loc = ""
    loc = loc or os.environ.get("LANG", "")
    return "zh_CN" if loc.lower().startswith("zh") else FALLBACK


def load_saved_language():
    """Apply the language saved by either GUI, else the system language."""
    code = None
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            code = json.load(f).get("language")
    except (OSError, ValueError, AttributeError):
        pass
    set_language(code or _system_language())
    return _current


def save_language(code):
    set_language(code)
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump({"language": _current}, f)
    except OSError:
        pass


def _placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def check():
    """Compare every locale file with en.json. Returns the number of problems."""
    reference = {k: v for k, v in _load(FALLBACK).items() if not k.startswith("_")}
    problems = 0
    for code, name in available_languages():
        if code == FALLBACK:
            continue
        data = _load(code)
        msgs = []
        for key, en_text in reference.items():
            if key not in data:
                msgs.append("missing      %s" % key)
            elif _placeholders(data[key]) != _placeholders(en_text):
                msgs.append("placeholders %s: expected %s, found %s" % (
                    key, sorted(_placeholders(en_text)), sorted(_placeholders(data[key]))))
        for key in data:
            if not key.startswith("_") and key not in reference:
                msgs.append("unknown      %s (not in en.json)" % key)
        print("%s.json (%s): %s" % (code, name, "OK" if not msgs else "%d problem(s)" % len(msgs)))
        for m in msgs:
            print("    " + m)
        problems += len(msgs)
    return problems


if __name__ == "__main__":
    sys.exit(1 if check() else 0)
