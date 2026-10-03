#!/usr/bin/env python3
"""The TDX mapping a survey file is processed with: the shared default plus
that cave's own override.

tdx-mapping.json (beside the tools) is the default everyone uses. A cave may
carry `tdx-mapping-objekt.json` in its SB_<broj>_... folder; it holds only what
differs from the default (same schema), and KORAK 1 (preprocess_tdx_csx.py)
and KORAK 2 (fix_imported_linetypes.py) apply it to that cave's files only.
The dashboard's mapping page writes it (user decision 2026-10-03: per cave,
never the shared default).

Override semantics, per section:
  points / lines / areas   an entry replaces the default's entry for that
                           TopoDroid name; `null` removes it (natural import
                           behaviour)
  generic                  per key
  postimport               a dict value (centerline, sign_sizes, label_sizes,
                           designproperties, viewoptions) merges per key, `null` removing
                           one; any other value replaces
Keys starting with "_" are comments and never merged or diffed.

  python tdx_mapping.py show FILE      which mapping FILE would be processed with
"""

import copy
import json
import os
import re
import sys

sys.dont_write_bytecode = True

OVERRIDE_NAME = "tdx-mapping-objekt.json"
DEFAULT_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "tdx-mapping.json")
ENTRY_SECTIONS = ("points", "lines", "areas")
# How far up from a survey file to look for the override. A cave's survey
# sits in its SB_ leaf or a subfolder of it; the leaf ends the walk.
_MAX_UP = 4
_LEAF = re.compile(r"^SB_0*\d+", re.I)


def _is_comment(key):
    return isinstance(key, str) and key.startswith("_")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_override(path):
    """The override governing `path` (a survey file or a folder), or None."""
    d = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    for _ in range(_MAX_UP):
        cand = os.path.join(d, OVERRIDE_NAME)
        if os.path.isfile(cand):
            return cand
        if _LEAF.match(os.path.basename(d)):
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def _merge_dict(base, over):
    out = dict(base)
    for k, v in over.items():
        if _is_comment(k):
            continue
        if v is None:
            out.pop(k, None)
        else:
            out[k] = copy.deepcopy(v)
    return out


def merge(default, override):
    """default + override -> the effective mapping (inputs untouched)."""
    out = copy.deepcopy(default)
    for section, value in (override or {}).items():
        if _is_comment(section):
            continue
        if section in ENTRY_SECTIONS or section == "generic":
            out[section] = _merge_dict(out.get(section, {}), value or {})
        elif section == "postimport":
            post = dict(out.get("postimport", {}))
            for k, v in (value or {}).items():
                if _is_comment(k):
                    continue
                if v is None:
                    post.pop(k, None)
                elif isinstance(v, dict) and isinstance(post.get(k), dict):
                    post[k] = _merge_dict(post[k], v)
                else:
                    post[k] = copy.deepcopy(v)
            out["postimport"] = post
        else:
            out[section] = copy.deepcopy(value)
    return out


def _diff_dict(base, eff):
    out = {}
    for k, v in eff.items():
        if not _is_comment(k) and base.get(k) != v:
            out[k] = copy.deepcopy(v)
    for k in base:
        if not _is_comment(k) and k not in eff:
            out[k] = None
    return out


def diff(default, effective):
    """The smallest override that turns `default` into `effective`.

    merge(default, diff(default, effective)) == effective, comments aside.
    An empty result means the cave needs no override file.
    """
    out = {}
    for section in ENTRY_SECTIONS + ("generic",):
        d = _diff_dict(default.get(section, {}), effective.get(section, {}))
        if d:
            out[section] = d
    base, eff = default.get("postimport", {}), effective.get("postimport", {})
    post = {}
    for k in set(base) | set(eff):
        if _is_comment(k):
            continue
        if k not in eff:
            post[k] = None
        elif isinstance(eff[k], dict) and isinstance(base.get(k), dict):
            d = _diff_dict(base[k], eff[k])
            if d:
                post[k] = d
        elif base.get(k) != eff[k]:
            post[k] = copy.deepcopy(eff[k])
    if post:
        out["postimport"] = post
    return out


def effective_for(path, default_path=DEFAULT_MAP):
    """(mapping, override_path|None) that a survey file is processed with.

    A missing default gives {} (the tools fall back to their built-ins); a
    broken override is reported and ignored, never fatal - the default still
    produces a usable file.
    """
    default = load_json(default_path) if os.path.exists(default_path) else {}
    over_path = find_override(path)
    if over_path is None:
        return default, None
    try:
        override = load_json(over_path)
    except (OSError, ValueError) as e:
        print("WARNING: %s se ne moze procitati (%s) - koristim zadano mapiranje"
              % (over_path, e))
        return default, None
    return merge(default, override), over_path


def write_override(leaf_dir, default, effective):
    """Write (or remove, when nothing differs) the cave's override.

    -> the path written, or None when the override was removed / not needed.
    """
    path = os.path.join(leaf_dir, OVERRIDE_NAME)
    over = diff(default, effective)
    if not over:
        if os.path.exists(path):
            os.remove(path)
        return None
    over = {"_readme": "Prilagodba mapiranja SAMO za ovaj objekt - razlike od "
                       "zajednickog tdx-mapping.json. Pise je nadzorna ploca "
                       "(3N > Mapiranje); KORAK 1 i KORAK 2 je koriste. "
                       "Obrisi datoteku za povratak na zadano.", **over}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(over, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "show":
        print(__doc__)
        return 2
    mapping, over = effective_for(argv[1])
    print("override: %s" % (over or "- (zadano)"))
    print(json.dumps(mapping, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
