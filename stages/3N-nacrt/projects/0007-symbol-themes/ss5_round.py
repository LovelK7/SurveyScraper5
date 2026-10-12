"""One theme round on a real TopoDroid export: KORAK 1 -> headless import ->
KORAK 2 (izvorno) -> themes -> plan+profile prints -> comparison sheets.
The import is cached by the raw file's hash.

usage: python ss5_round.py LABEL RAW.csx [--themes boja,crno-bijelo]
"""
import argparse, hashlib, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

STAGE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOOLS = os.path.join(STAGE, "production", "tools")
RUNS = os.path.join(STAGE, "projects", "0007-symbol-themes", "runs")
sys.path.insert(0, TOOLS)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import csurvey_driver, theme_round, theme_apply  # noqa: E402


def sh(args):
    r = subprocess.run([sys.executable] + args, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise SystemExit("FAILED %s\n%s%s" % (args, r.stdout, r.stderr))
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label"); ap.add_argument("raw")
    ap.add_argument("--themes", default="boja,crno-bijelo")
    ap.add_argument("--date", default=None)
    a = ap.parse_args()
    import datetime
    date = a.date or datetime.date.today().isoformat()
    run = os.path.join(RUNS, "%s-%s" % (date, a.label))
    os.makedirs(run, exist_ok=True)
    tids = [t for t in a.themes.split(",") if t]

    h = hashlib.sha1(open(a.raw, "rb").read()).hexdigest()[:12]
    cache = os.path.join(theme_round.cache_root(), "survey-" + h)
    raw, prep, lt = (os.path.join(cache, n) for n in ("ss5_tdx_raw.csx", "ss5_prep.csx", "ss5_lt.csx"))
    if not os.path.exists(lt):
        os.makedirs(cache, exist_ok=True)
        shutil.copyfile(a.raw, raw)
        print(sh([os.path.join(TOOLS, "preprocess_tdx_csx.py"), raw, "-o", prep, "--force"]).splitlines()[-1])
        nodtd, _ = theme_round.ensure_nodtd(csurvey_driver.find_csurvey_dir(),
                                            os.path.join(theme_round.cache_root(), "csurvey-nodtd"))
        csurvey_driver.recalc(prep, lt, csurvey_dir=nodtd)
        print("imported ->", lt)
    else:
        print("import cache", cache)
    for f in (raw, prep):
        shutil.copyfile(f, os.path.join(run, os.path.basename(f)))
    iz = os.path.join(run, "ss5_izvorno.csx")
    out = sh([os.path.join(TOOLS, "fix_imported_linetypes.py"), lt, "-o", iz, "--no-theme", "--force"])
    print(out.strip())
    variants = ["izvorno"]
    for t in tids:
        o = os.path.join(run, "ss5_%s.csx" % t)
        txt = sh([os.path.join(TOOLS, "theme_apply.py"), "apply", iz, "--theme", t, "--pre", prep,
                  "-o", o, "--json", os.path.join(run, "report_%s.json" % t)])
        print(txt.strip())
        variants.append(t)
    for t in tids:
        shutil.copyfile(os.path.join(STAGE, "production", "themes", t, "theme.json"),
                        os.path.join(run, "%s.theme.json" % t))

    real = csurvey_driver.find_csurvey_dir()

    def one(v):
        d = os.path.join(run, "pdf_" + v)
        os.makedirs(d, exist_ok=True)
        err = None
        for _ in range(2):
            try:
                return v, csurvey_driver.print_pdfs(os.path.join(run, "ss5_%s.csx" % v), d,
                                                    design="Both", csurvey_dir=real)
            except csurvey_driver.DriverError as e:
                err = e
        raise SystemExit("print %s: %s" % (v, err))
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, variants))

    import pymupdf
    from PIL import Image, ImageDraw, ImageFont, ImageChops
    f = ImageFont.truetype("arial.ttf", 28)
    for view in ("plan", "profile"):
        ims = []
        for v in variants:
            d = pymupdf.open(os.path.join(run, "pdf_%s" % v, "ss5_%s_%s.pdf" % (v, view)))
            pm = d[0].get_pixmap(dpi=150, alpha=False)
            ims.append((v, Image.frombytes("RGB", (pm.width, pm.height), pm.samples)))
        box = None
        for _, im in ims:
            b = ImageChops.invert(im.convert("L")).point(lambda x: 255 if x > 20 else 0).getbbox()
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
        box = (max(0, box[0] - 20), max(0, box[1] - 20), box[2] + 20, box[3] + 20)
        cr = [(v, im.crop(box)) for v, im in ims]
        w, hh = cr[0][1].size
        sheet = Image.new("RGB", (w * len(cr) + 20 * (len(cr) - 1), hh + 50), "white")
        dr = ImageDraw.Draw(sheet)
        for i, (v, im) in enumerate(cr):
            sheet.paste(im, (i * (w + 20), 50))
            dr.text((i * (w + 20) + 10, 10), v, fill="black", font=f)
        sheet.save(os.path.join(run, "ss5_%s_usporedba.png" % view))
    print("->", run)


if __name__ == "__main__":
    main()
