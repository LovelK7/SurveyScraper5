"""Run wall_side_proto over the csx_entrances corpus; one summary line per design + every doubtful wall."""
import glob, os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wall_side_proto as w
CORPUS = os.path.join(HERE, "..", "..", "..", "example", "csx_entrances")
files = sorted(glob.glob(os.path.join(CORPUS, "*.csx")) + glob.glob(os.path.join(CORPUS, "*.CSZ")))
allrep = []
for f in files:
    rep = w.analyse(f, png="--png" in sys.argv)
    allrep.append(rep)
    if "error" in rep:
        print("%-48s %s" % (rep["file"][:48], rep["error"])); continue
    for d, D in rep["designs"].items():
        ws = [r for r in D["walls"] if r["type"] == w.AREA_TYPE]
        L = sum(r["length"] for r in ws if r["cave_side"] == "left")
        R = sum(r["length"] for r in ws if r["cave_side"] == "right")
        U = sum(r["length"] for r in ws if r["cave_side"] is None)
        weak = [r for r in ws if r["score"] is not None and (abs(r["score"]) < 0.6 or r["coverage"] < 0.5)]
        print("%-48s %-7s seqs=%-3d left=%6.1fm right=%6.1fm none=%5.1fm weak=%d" % (rep["file"][:48], d, len(ws), L, R, U, len(weak)))
        for r in weak:
            print("      weak %d.%d n=%d L=%.2f score=%s cov=%s med=%s" % (r["item"], r["seq"], r["n"], r["length"], r["score"], r["coverage"], r["median_dist"]))
json.dump(allrep, open(os.path.join(HERE, "_out", "corpus_sides.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
