#!/usr/bin/env python3
"""Validate the shared cSurvey defaults after an edit (the /csurvey-defaults skill).

Loads both default files through the real 3N tools, exactly as KORAK 0/1/2 do,
and checks every value against the vocabularies those tools accept. Prints one
line per problem and exits 1 if there is any; prints a short summary otherwise.

  python .claude/skills/csurvey-defaults/check_defaults.py
"""

import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TOOLS = os.path.join(REPO, "stages", "3N-nacrt", "production", "tools")
sys.path.insert(0, TOOLS)
sys.dont_write_bytecode = True

import csurvey_app_settings as app  # noqa: E402
import fix_imported_linetypes as fixer  # noqa: E402
import preprocess_tdx_csx as pp  # noqa: E402

problems = []
mapping_path = os.path.join(TOOLS, "tdx-mapping.json")
catalog_path = os.path.join(TOOLS, "tdx-mapping-catalog.json")

try:
    mapping = json.load(open(mapping_path, encoding="utf-8"))
except ValueError as e:
    print("tdx-mapping.json is not valid JSON: %s" % e)
    sys.exit(1)
catalog = json.load(open(catalog_path, encoding="utf-8"))
norm = lambda s: s.lower().replace("-", "").replace("_", "")
targets = {
    "points": {norm(t["to"]) for t in catalog["targets"]["point"]},
    "lines": {t["to"] for t in catalog["targets"]["line"]},
    "areas": {t["to"] for t in catalog["targets"]["area"]},
}
tdx_names = {(r["kind"] + "s", r["name"]) for r in catalog["tdx"]}

# KORAK 1: symbols, lines, areas
for section in ("points", "lines", "areas"):
    for name, entry in mapping.get(section, {}).items():
        if name.startswith("_"):
            continue
        where = "%s.%s" % (section, name)
        if not isinstance(entry, dict):
            problems.append("%s: entry must be an object" % where)
            continue
        if (section, name) not in tdx_names:
            problems.append("%s: not a TopoDroid symbol name in the catalog (typo? th_name uses ':' not '=')" % where)
        if "to" in entry:
            want = norm(entry["to"]) if section == "points" else entry["to"]
            if want not in targets[section]:
                problems.append("%s: target %r is not a cSurvey %s target" % (where, entry["to"], section[:-1]))
        elif "label" in entry:
            if section != "points":
                problems.append("%s: label is points-only" % where)
        elif not entry.get("leave"):
            problems.append("%s: needs to, label or leave" % where)
        if "reverse" in entry and section != "lines":
            problems.append("%s: reverse is lines-only" % where)
        if "orientation" in entry and section != "points":
            problems.append("%s: orientation is points-only" % where)
try:
    pp.apply_mapping(mapping)
except Exception as e:  # noqa: BLE001
    problems.append("KORAK 1 cannot load the mapping: %s" % e)

# KORAK 2: postimport
post = mapping.get("postimport", {})
for key, value in post.get("centerline", {}).items():
    if key not in fixer.CENTERLINE_TYPES:
        problems.append("postimport.centerline.%s: unknown key (see CENTERLINE_TYPES)" % key)
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append("postimport.centerline.%s: must be a number" % key)
    elif fixer.CENTERLINE_TYPES[key] in ("color", "integer") and not isinstance(value, int):
        problems.append("postimport.centerline.%s: must be an integer" % key)
for key, entry in post.get("designproperties", {}).items():
    if key.startswith("_"):
        continue
    if not isinstance(entry, dict) or entry.get("type") not in fixer.DESIGN_PROPERTY_TYPES or "value" not in entry:
        problems.append("postimport.designproperties.%s: needs {type: one of %s, value}"
                        % (key, "/".join(sorted(fixer.DESIGN_PROPERTY_TYPES))))
for view, attrs in post.get("viewoptions", {}).items():
    if view.startswith("_"):
        continue
    if view not in fixer.VIEW_NAMES:
        problems.append("postimport.viewoptions.%s: unknown view (one of %s; no leading _)"
                        % (view, ", ".join(sorted(fixer.VIEW_NAMES))))
    elif not isinstance(attrs, dict) or not all(
            isinstance(v, int) and not isinstance(v, bool) for v in attrs.values()):
        problems.append("postimport.viewoptions.%s: needs {attribute: integer}" % view)
for key, size in post.get("sign_sizes", {}).items():
    if key.lower() not in fixer.SIGN_VALUES:
        problems.append("postimport.sign_sizes.%s: unknown sign name" % key)
    if str(size).lower() not in fixer.SIZES:
        problems.append("postimport.sign_sizes.%s: size %r not in %s" % (key, size, sorted(fixer.SIZES)))
for key, size in post.get("label_sizes", {}).items():
    if str(size).lower() not in fixer.SIZES:
        problems.append("postimport.label_sizes.%r: size %r not in %s" % (key, size, sorted(fixer.SIZES)))

# KORAK 0: app settings
try:
    _key, app_settings = app.load_profile(app.DEFAULT_PROFILE)
except (OSError, ValueError) as e:
    problems.append("csurvey-app-settings.json: %s" % e)
    app_settings = []

if problems:
    print("PROBLEMS (%d):" % len(problems))
    for p in problems:
        print("  - " + p)
    sys.exit(1)
cl = post.get("centerline", {})
print("OK: %d point / %d line / %d area mappings, %d centerline, %d designproperties, "
      "%d viewoptions, %d sign sizes, %d label sizes, %d app settings"
      % (len(mapping.get("points", {})), len(mapping.get("lines", {})), len(mapping.get("areas", {})),
         len(cl), len([k for k in post.get("designproperties", {}) if not k.startswith("_")]),
         len([k for k in post.get("viewoptions", {}) if not k.startswith("_")]),
         len(post.get("sign_sizes", {})), len(post.get("label_sizes", {})), len(app_settings)))
