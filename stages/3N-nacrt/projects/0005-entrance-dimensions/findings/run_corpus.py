"""Run the entrance prototype over every .csx/.csz in a folder.

Usage: python run_corpus.py <folder>   -> summary on stdout, <folder>/_out/<name>.json + _entrance.png
"""
import glob, json, os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import entrance_dims_proto as ep
folder = os.path.abspath(sys.argv[1])
OUT = os.path.join(folder, "_out")
os.makedirs(OUT, exist_ok=True)
os.chdir(folder)
# <folder>/kinds.json = {"<file stem>": "pit"|"horizontal"} stands in for the registry type (SB / OSZ Vrsta objekta)
KINDS = json.load(open("kinds.json", encoding="utf-8")) if os.path.exists("kinds.json") else {}
# <folder>/entrances.json = {"<file stem>": "<station>"} when the operator knows the entrance station
ENTRANCES = json.load(open("entrances.json", encoding="utf-8")) if os.path.exists("entrances.json") else {}
for f in sorted(f for f in glob.glob("*.csx") + glob.glob("*.csz") if "_backup" not in f):
    stem = os.path.splitext(f)[0]
    try:
        rep, ctx = ep.analyse(f, KINDS.get(stem), ENTRANCES.get(stem))
        if ctx is not None:
            ep.draw(rep, ctx, os.path.join(OUT, stem + "_entrance.png"))
        json.dump(rep, open(os.path.join(OUT, stem + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        osz = rep.get("osz", {})
        print("## %-46s %-10s %-4s %s x %s  [%s]  entrance %s via %s  splays %s" % (
            f[:46], rep.get("kind", "?"), "raw" if rep["raw"] else "", osz.get("sirina_ulaza"), osz.get("visina_duljina_ulaza"),
            ",".join(str(s) for s in osz.get("sources", [])), rep.get("entrance"), rep.get("entrance_how", "")[:40], rep.get("splays_at_station")))
        print("   kind:", rep.get("kind_why"))
        for w in rep["warnings"]:
            print("   WARN", w)
        if rep.get("kind") == "horizontal":
            p, pr = rep["plan"], rep["profile"]
            print("   width  %-5s a=%s b=%s | walls %s" % (p["width_m"], p["side_a"], p["side_b"], p["wall_narrowest"] and p["wall_narrowest"]["width_m"]))
            print("   height %-5s up=%s down=%s | walls %s" % (pr["height_m"], pr["up"], pr["down"], pr["wall_narrowest"] and pr["wall_narrowest"]["height_m"]))
        elif rep.get("kind") == "pit":
            print("   splay cloud %s | wall footprint %s" % (rep["plan"].get("splay_cloud"), rep["plan"].get("wall_footprint")))
    except Exception:
        print("## %-46s ERROR" % f[:46]); traceback.print_exc(limit=2)
