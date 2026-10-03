"""`cavedossier gui`: the catalog, the workspace reader, jobs and the HTTP surface."""

from __future__ import annotations

import dataclasses
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from cave_dossier.cli import build_parser
from cave_dossier.gui import catalog
from cave_dossier.gui.jobs import JobManager
from cave_dossier.gui.server import App, make_handler
from cave_dossier.gui import workflow
from cave_dossier.gui.server import _Server
from cave_dossier.gui.state import Workspace, classify, sb_versions, tools_dir


# ── catalog ─────────────────────────────────────────────────────────


def _everything_ticked(action: catalog.Action) -> dict:
    selected: dict = {}
    for option in action.options:
        if option.kind == "flag":
            selected[option.flag] = True
        elif option.kind == "int":
            selected[option.flag] = "3"
        elif option.kind == "choice":
            selected[option.flag] = option.choices[-1]
        else:
            selected[option.flag] = "Lovel Kukuljan"
    return selected


@pytest.mark.parametrize("action", [a for a in catalog.ACTIONS if a.tool == "cli"],
                         ids=lambda a: a.id)
def test_every_cli_action_parses(action):
    """A catalog entry the real parser rejects would be a dead button."""
    for selected in ({}, _everything_ticked(action)):
        args = catalog.build_args(action, broj=1220, query="Hrđava", selected=selected)
        build_parser().parse_args(args)


def test_every_script_action_names_a_real_tool():
    tools = tools_dir()
    assert tools is not None, "dev checkout should find stages/3N-nacrt/production/tools"
    for action in catalog.ACTIONS:
        if action.tool not in ("cli", "manual"):
            assert (tools / action.tool).is_file(), action.id
            assert action.file_kind, f"{action.id}: a 3N script needs a file"


def test_catalog_ids_unique_and_stages_known():
    ids = [a.id for a in catalog.ACTIONS]
    assert len(ids) == len(set(ids))
    labels = {s.label for s in catalog.STAGES}
    assert {a.stage for a in catalog.ACTIONS} <= labels


def test_write_detection():
    by = catalog.BY_ID
    assert catalog.is_write(by["karta"], {}) is not None
    assert catalog.is_write(by["sb-stats"], {}) is None
    # a safe flag turns a writer into a dry run
    assert catalog.is_write(by["photos-process"], {"--dry-run": True}) is None
    assert catalog.is_write(by["3n-k3c"], {"--local": True}) is None
    # an unsafe flag turns a reader into a writer
    assert catalog.is_write(by["intake-map"], {}) is None
    assert "preimenuje" in catalog.is_write(by["intake-map"], {"--apply": True})


def test_build_args_validation():
    by = catalog.BY_ID
    with pytest.raises(catalog.ActionError):
        catalog.build_args(by["karta"])  # no broj
    with pytest.raises(catalog.ActionError):
        catalog.build_args(by["sb-audit-authors"], selected={"--limit": "abc"})
    with pytest.raises(catalog.ActionError):
        catalog.build_args(by["report"], query="x", selected={"--gate": "nope"})
    with pytest.raises(catalog.ActionError):
        catalog.build_args(by["3n-k1"], broj=1)  # no file
    assert catalog.build_args(by["3n-k3a"], file="a b.csx",
                              selected={"--layout": "2", "--force": True}) == \
        ["a b.csx", "--force", "--layout", "2"]


# ── workspace ───────────────────────────────────────────────────────


@pytest.mark.parametrize("name,kind", [
    ("Hrđava_špilja-1s.csx", "raw"),
    ("Hrđava_špilja-1s_pp.csx", "pp"),
    ("Hrđava_špilja-1s_pp_lt.csx", "lt"),
    ("Hrđava_špilja-1s_pp_lt_fin.csx", "fin"),
    ("Hrđava_špilja-1s_pp_lt_backup.csx", "backup"),
    ("x_plan.pdf", "plan"),
    ("x_profile.pdf", "profile"),
    ("x_dimenzije.json", "dimenzije"),
    ("SB_1220_nacrt.pdf", "nacrt"),
    ("SB_1220_sastavnica.pdf", "sastavnica"),
    ("SB_1220_OSZ.docx", "osz"),
    ("295_stari_2026-09-01.docx", "doc"),
    ("SB_1249_Nožata jama_DGrozić_1.jpg", "photo_processed"),
    ("20250618_134630.jpg", "photo"),
    ("Nožata tlocrt.pdf", "pdf"),
])
def test_classify(name, kind):
    assert classify(Path(name), 1220) == kind


@pytest.fixture()
def drive(tmp_path: Path, settings):
    """A fake Drive: two SB versions, an intake tree, one map excerpt."""
    root = tmp_path / "Speleo baza SUE"
    intake = root / "!!!Digitalizacija" / "!Za digitalizirat"
    leaf = intake / "!!Grupa" / "SB_1220_Hrđava špilja_Flavio"
    leaf.mkdir(parents=True)
    for name in ("a.csx", "a_pp.csx", "a_pp_lt.csx", "SB_1220_OSZ.docx", "desktop.ini"):
        (leaf / name).write_text("x", encoding="utf-8")
    (intake / "Neimenovana mapa").mkdir()
    (intake / "Neimenovana mapa" / "f.txt").write_text("x", encoding="utf-8")
    (intake / "primjeri").mkdir()
    (root / "!Speleo_baza_SUE_v2.4.xlsm").write_text("x", encoding="utf-8")
    (root / "!Speleo_baza_SUE_v3.0.xlsm").write_text("x", encoding="utf-8")
    (root / "!!Isječci karte").mkdir()
    (root / "!!Isječci karte" / "SB_1220.png").write_bytes(b"png")
    ws_settings = dataclasses.replace(
        settings, local_drive_root=root,
        archive_dirs={"intake_dir": "!!!Digitalizacija/!Za digitalizirat",
                      "map_excerpts_dir": "!!Isječci karte"},
        intake_ignore_folders=["primjeri"],
    )
    return Workspace(ws_settings), root, leaf


def test_sb_versions_newest_first(drive):
    _, root, _ = drive
    assert [v["name"] for v in sb_versions(root)] == [
        "!Speleo_baza_SUE_v3.0.xlsm", "!Speleo_baza_SUE_v2.4.xlsm"]


def test_caves_and_detail(drive):
    ws, _, leaf = drive
    caves, unprefixed = ws.caves()
    assert [(c.broj, c.name, c.group) for c in caves] == [(1220, "Hrđava špilja_Flavio", "!!Grupa")]
    assert unprefixed == ["Neimenovana mapa"]  # primjeri is ignored, not listed
    detail = ws.cave_detail(1220)
    kinds = sorted(f["kind"] for f in detail["files"])
    assert kinds == ["lt", "osz", "pp", "raw"]  # desktop.ini skipped
    assert detail["karta"]["exists"] is True
    assert ws.candidate_files(1220, "lt") == [str(leaf / "a_pp_lt.csx")]
    assert ws.cave_detail(9999)["leaves"] == []


def test_path_guard(drive, tmp_path):
    ws, root, leaf = drive
    assert ws.is_allowed(leaf / "a.csx")
    outside = tmp_path / "outside.txt"  # beside the fake Drive, not in it
    outside.write_text("x", encoding="utf-8")
    assert not ws.is_allowed(outside)


# ── jobs ────────────────────────────────────────────────────────────


def _wait(job, timeout=15.0):
    end = time.time() + timeout
    while job.running and time.time() < end:
        time.sleep(0.05)
    assert not job.running


def test_job_output_and_stdin(tmp_path):
    jobs = JobManager(tmp_path / "logs")
    script = "print('pitanje?', flush=True); x = input(); print('odgovor:', x)"
    job = jobs.start("test", [sys.executable, "-c", script], "test", tmp_path)
    end = time.time() + 15
    while "pitanje?" not in job.output()[0] and time.time() < end:
        time.sleep(0.05)
    assert job.send("SVE")
    _wait(job)
    text, offset = job.output()
    assert "odgovor: SVE" in text and job.returncode == 0
    assert job.output(offset) == ("", offset)
    assert "odgovor: SVE" in job.log_path.read_text(encoding="utf-8")


def test_job_kill(tmp_path):
    jobs = JobManager(None)
    job = jobs.start("spava", [sys.executable, "-c", "import time; time.sleep(60)"], "x", tmp_path)
    job.kill()
    _wait(job)
    assert job.returncode not in (None, 0)


# ── HTTP ────────────────────────────────────────────────────────────


@pytest.fixture()
def server(drive):
    ws, root, leaf = drive
    opened: list = []
    app = App(ws=ws, jobs=JobManager(None), token="t0k",
              opener=lambda target, app=None, reveal=False: opened.append(target),
              deleter=lambda target: target.unlink())  # never the real Recycle Bin
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", opened, leaf
    httpd.shutdown()
    httpd.server_close()


def _call(base, path, body=None, token="t0k"):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, headers={
        "X-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def test_page_carries_token(server):
    base, _, _ = server
    with urllib.request.urlopen(base + "/", timeout=10) as res:
        assert 'CD_TOKEN = "t0k"' in res.read().decode()
    with urllib.request.urlopen(base + "/static/app.js", timeout=10) as res:
        assert res.status == 200


def test_api_needs_token(server):
    base, _, _ = server
    assert _call(base, "/api/state", token="wrong")[0] == 403


def test_api_caves_and_catalog(server):
    base, _, _ = server
    status, data = _call(base, "/api/caves")
    assert status == 200 and data["caves"][0]["broj"] == 1220
    status, data = _call(base, "/api/catalog")
    assert status == 200 and any(a["id"] == "3n-k3a" for a in data["actions"])


def test_run_refuses_unconfirmed_write_and_foreign_file(server):
    base, _, _ = server
    status, data = _call(base, "/api/run", {"action": "karta", "broj": 1220})
    assert status == 409 and "potvrda" in data["error"]
    status, _ = _call(base, "/api/run", {"action": "3n-inspect", "broj": 1220,
                                         "file": sys.executable})
    assert status == 400
    status, _ = _call(base, "/api/run", {"action": "nope"})
    assert status == 400


def test_open_guarded(server, tmp_path):
    base, opened, leaf = server
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    assert _call(base, "/api/open", {"what": "path", "path": str(leaf)})[0] == 200
    assert _call(base, "/api/open", {"what": "path", "path": str(outside)})[0] == 403
    assert _call(base, "/api/open", {"what": "sb"})[0] in (200, 400)
    assert opened[0] == leaf


def test_thumb_serves_only_the_caves_photos(server):
    base, _, leaf = server
    photo = leaf / "SB_1220_Hrđava špilja_LKukuljan_1.jpg"
    photo.write_bytes(bytes([0xFF, 0xD8]) + b"not-really-a-jpeg")  # Pillow fails -> original bytes
    query = urllib.parse.urlencode({"broj": 1220, "path": str(photo), "w": 240})
    with urllib.request.urlopen(f"{base}/api/thumb?{query}&t=t0k", timeout=10) as res:
        assert res.status == 200 and res.read().startswith(bytes([0xFF, 0xD8]))
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(f"{base}/api/thumb?{query}&t=wrong", timeout=10)
    assert err.value.code == 403
    other = urllib.parse.urlencode({"broj": 1220, "path": str(leaf / "a.csx")})
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(f"{base}/api/thumb?{other}&t=t0k", timeout=10)
    assert err.value.code == 404


def test_delete_photos_only_and_only_confirmed(server):
    base, _, leaf = server
    photo = leaf / "IMG_0001.jpg"
    photo.write_bytes(b"x")
    assert _call(base, "/api/delete", {"broj": 1220, "path": str(photo)})[0] == 409
    assert _call(base, "/api/delete", {"broj": 1220, "path": str(leaf / "a.csx"),
                                       "confirmed": True})[0] == 403
    assert (leaf / "a.csx").exists()
    status, data = _call(base, "/api/delete", {"broj": 1220, "path": str(photo), "confirmed": True})
    assert status == 200 and not photo.exists()


def test_cave_view_carries_workflow_and_locks(server):
    base, _, leaf = server
    (leaf / "~$_1220_OSZ.docx").write_text("lock", encoding="utf-8")
    status, data = _call(base, "/api/cave/1220")
    assert status == 200
    assert data["locks"] == ["~$_1220_OSZ.docx"]
    assert all(not f["name"].startswith("~$") for f in data["files"])
    ids = [s["id"] for s in data["workflow"]["steps"]]
    assert ids[:3] == ["mapa", "karta", "osz-prefill"] and "3n-k3c" in ids


def test_exclusive_bind_refuses_a_busy_port():
    """Windows SO_REUSEADDR let two dashboards share 8790 (2026-10-02)."""
    first = _Server(("127.0.0.1", 0), make_handler(App(ws=Workspace(None), token="x")))
    try:
        with pytest.raises(OSError):
            _Server(("127.0.0.1", first.server_address[1]), make_handler(App(token="y")))
    finally:
        first.server_close()


# ── workflow ────────────────────────────────────────────────────────


def _f(kind, name, t):
    return {"kind": kind, "name": name, "path": "/x/" + name, "modified": float(t), "size": 1}


def _states(steps):
    return {s.id: s.status for s in steps}


def test_workflow_fresh_cave_points_at_karta():
    detail = {"leaves": [{"path": "/x"}], "files": [], "karta": {"exists": False}}
    steps = workflow.build(detail)
    current = [s.id for s in steps if s.current]
    assert current == ["karta"]
    assert _states(steps)["3n-k1"] == "blocked"


def test_workflow_survey_change_makes_downstream_stale():
    files = [_f("raw", "a.csx", 100), _f("pp", "a_pp.csx", 200), _f("lt", "a_pp_lt.csx", 300),
             _f("fin", "a_pp_lt_fin.csx", 400), _f("plan", "a_plan.pdf", 500),
             _f("profile", "a_profile.pdf", 500), _f("dimenzije", "a_dimenzije.json", 500),
             _f("nacrt", "SB_1220_nacrt.pdf", 600), _f("osz", "SB_1220_OSZ.docx", 50)]
    detail = {"leaves": [{}], "files": files, "karta": {"exists": True}}
    osz = {"opis": "Ulaz je…", "duljina": "18", "dubina": "5"}
    states = _states(workflow.build(detail, osz, dims={"l": 18}))
    assert states["3n-k3c"] == "done" and states["osz-dims"] == "done"
    # The sketch is corrected again after finishing: 3a and everything after it moves.
    files[2] = _f("lt", "a_pp_lt.csx", 450)
    states = _states(workflow.build(detail, osz, dims={"l": 18}))
    assert states["3n-k3a"] == "stale"
    # The OSZ is filled after the nacrt was composed: 3c must be redone (postfill).
    files[2] = _f("lt", "a_pp_lt.csx", 300)
    files[8] = _f("osz", "SB_1220_OSZ.docx", 700)
    states = _states(workflow.build(detail, osz, dims={"l": 18}))
    assert states["3n-k3c"] == "stale"


def test_workflow_osz_waits_for_measured_lengths():
    files = [_f("osz", "SB_1220_OSZ.docx", 50), _f("dimenzije", "a_dimenzije.json", 60)]
    detail = {"leaves": [{}], "files": files, "karta": {"exists": True}}
    states = _states(workflow.build(detail, {"opis": "x"}, dims={"l": 18}))
    assert states["osz-dims"] == "todo"
    states = _states(workflow.build(detail, {"opis": "x", "duljina": "40", "dubina": "5"}, dims={"l": 18}))
    assert states["osz-dims"] == "stale"  # the OSZ disagrees with the survey
    assert _states(workflow.build(detail, None, "nečitljiv"))["osz-filled"] == "unknown"


# ── queue, karta, docs (2026-10-02, round 3) ────────────────────────


def test_queue_is_indexed_by_prefix_and_reaches_the_workflow(drive):
    ws, root, leaf = drive
    queue_dir = root / "!!Fotografije ulaza" / "!!Fotografije ulaza za istražit"
    queue_dir.mkdir(parents=True)
    (queue_dir / "SB_1220_ulaz.jpg").write_bytes(b"x")
    (queue_dir / "SB_0977_drugi.jpg").write_bytes(b"x")
    (queue_dir / "bez_prefiksa.jpg").write_bytes(b"x")
    ws._settings = dataclasses.replace(ws._settings, archive_dirs={
        **ws._settings.archive_dirs,
        "queued_photos_dir": "!!Fotografije ulaza/!!Fotografije ulaza za istražit"})
    assert {k: len(v) for k, v in ws.queue().items()} == {1220: 1, 977: 1}
    view = ws.cave_view(1220)
    assert [q["name"] for q in view["queued"]] == ["SB_1220_ulaz.jpg"]
    foto = next(s for s in view["workflow"]["steps"] if s["id"] == "foto")
    assert foto["status"] == "todo" and foto["action"] == "photos-pull"
    assert foto["preset"] == {"--apply": True}
    # a queued photo is servable/deletable like the cave's own
    assert ws.cave_file(1220, str(queue_dir / "SB_1220_ulaz.jpg"), {"queued"})
    assert ws.cave_file(1220, str(queue_dir / "SB_0977_drugi.jpg"), {"queued"}) is None


def test_karta_record_read_from_georef_csv(drive):
    ws, root, _ = drive
    (root / "!!Isječci karte" / "!georef_zapisi.csv").write_text(
        "Redni broj,Ime objekta,Georef zapis,Datum\n"
        "01220,Hrđava špilja,321762;Hrđava špilja;351016;5032974;0.7,2026-09-01\n",
        encoding="utf-8-sig")
    karta = ws.cave_detail(1220)["karta"]
    assert karta["record"]["Ime objekta"] == "Hrđava špilja"
    assert ws.cave_file(1220, karta["path"], {"karta"})["kind"] == "karta"


def test_doc_endpoint_serves_repo_markdown_only(server):
    base, _, _ = server
    status, data = _call(base, "/api/doc?path=STATUS.md")
    assert status == 200 and data["text"].startswith("# STATUS")
    assert _call(base, "/api/doc?path=pyproject.toml")[0] == 403
    assert _call(base, "/api/doc?path=../outside.md")[0] == 403
    assert _call(base, "/api/doc?path=nope.md")[0] == 404


def test_queue_reminder_names_queued_caves(monkeypatch, settings, capsys):
    from cave_dossier import cli
    import cave_dossier.photos.process as process

    monkeypatch.setattr(process, "staged_for_cave",
                        lambda _s, serial: [Path("a.jpg")] * 2 if serial == 7 else [])
    cli._queue_reminder(settings, [7, 8, None])
    out = capsys.readouterr().out
    assert "Redni broj 7" in out and "pull-staged 7 --apply" in out and "8" not in out.replace("7", "")


# ── ★ fast actions + intake create (2026-10-02, round 4) ────────────


def test_every_recipe_step_is_a_parsable_catalog_action():
    for recipe in catalog.RECIPES:
        for step in recipe.steps:
            action = catalog.BY_ID[step.action]
            if action.tool != "cli":
                continue
            args = catalog.build_args(action, broj=1220, query="x", selected=dict(step.options))
            build_parser().parse_args(args)


def _seq(title, code, keep_going=False):
    from cave_dossier.gui.jobs import SequenceStep

    return SequenceStep(title, [sys.executable, "-c", code], title, keep_going)


def test_sequence_stops_on_failure_unless_keep_going(tmp_path):
    jobs = JobManager(None)
    job = jobs.start_sequence("t", [_seq("a", "print('A')"), _seq("b", "raise SystemExit(99)"),
                                    _seq("c", "print('C')")], tmp_path)
    _wait(job)
    text = job.output()[0]
    assert "A" in text and "C\n" not in text and job.returncode == 99
    job = jobs.start_sequence("t", [_seq("b", "raise SystemExit(99)", keep_going=True),
                                    _seq("c", "print('CC'); raise SystemExit(1)")], tmp_path)
    _wait(job)
    assert "CC" in job.output()[0] and job.returncode == 99  # 1 = "not ready", not a failure


def test_recipe_needs_cave_and_confirmation(server):
    base, _, _ = server
    assert _call(base, "/api/recipe", {"recipe": "novi-objekt"})[0] == 400
    assert _call(base, "/api/recipe", {"recipe": "nope", "broj": 1220})[0] == 400
    status, data = _call(base, "/api/recipe", {"recipe": "novi-objekt", "broj": 1220})
    assert status == 409 and "Napravi mapu objekta" in data["error"]
    # the queue step drops out when nothing is queued; skipping everything is refused
    assert _call(base, "/api/recipe", {"recipe": "novi-objekt", "broj": 1220,
                                       "skip": [0, 1, 2, 4], "confirmed": True})[0] == 400


def test_intake_create_makes_then_reuses_the_leaf(settings, tmp_path, capsys):
    from cave_dossier import cli

    root = tmp_path / "Drive"
    intake = root / "!!!Digitalizacija" / "!Za digitalizirat"
    intake.mkdir(parents=True)
    s = dataclasses.replace(settings, local_drive_root=root,
                            archive_dirs={"intake_dir": "!!!Digitalizacija/!Za digitalizirat"})
    assert cli.cmd_intake_create(s, 1) == 0
    made = [d for d in intake.iterdir() if d.is_dir()]
    assert len(made) == 1 and made[0].name.startswith("SB_1_")
    assert cli.cmd_intake_create(s, 1) == 0
    assert [d for d in intake.iterdir() if d.is_dir()] == made
    assert "već postoji" in capsys.readouterr().out
    assert cli.cmd_intake_create(s, 99999) == 99


def test_sb_index_lists_every_row_with_a_redni_broj(drive):
    """The picker can choose a cave that has no folder yet (round 5)."""
    ws, _, _ = drive
    index = ws.sb_index()
    assert index["error"] is None and index["rows"]
    assert all(isinstance(r["broj"], int) and "name" in r for r in index["rows"])
    assert [r["broj"] for r in index["rows"]] == sorted(r["broj"] for r in index["rows"])
    assert ws.sb_index() is index  # cached until refresh
    ws.refresh()
    assert ws._sb_index is None


def test_duplicate_redni_broj_is_found_and_blocks_intake_create(settings, tmp_path, monkeypatch, capsys):
    """Three SB rows shared 1458 on 2026-10-02; the tools must refuse, not merge."""
    from cave_dossier import cli
    from cave_dossier.core.matching import CaveCandidate, duplicate_serials

    def cand(serial, name):
        return CaveCandidate(serial, name, None, None, None, name.lower())

    dups = duplicate_serials([cand(1458, "VP2"), cand(1458, "Ona mala špilja"), cand(1457, "VP1")])
    assert list(dups) == [1458] and len(dups[1458]) == 2

    root = tmp_path / "Drive"
    (root / "!!!Digitalizacija" / "!Za digitalizirat").mkdir(parents=True)
    s = dataclasses.replace(settings, local_drive_root=root,
                            archive_dirs={"intake_dir": "!!!Digitalizacija/!Za digitalizirat"})
    monkeypatch.setattr(cli, "duplicate_serials", lambda _c: {1: [cand(1, "A"), cand(1, "B")]})
    assert cli.cmd_intake_create(s, 1) == 99
    assert not any((root / "!!!Digitalizacija" / "!Za digitalizirat").iterdir())
    assert "nije jedinstven" in capsys.readouterr().err


# ── 3N mapping page (gui/mapping.py) ────────────────────────────────


def test_mapping_page_saves_only_the_difference_and_resets(server):
    base, _, leaf = server
    status, cat = _call(base, "/api/mapping-catalog")
    assert status == 200 and cat["targets"]["point"] and cat["tdx"]
    status, view = _call(base, "/api/mapping/1220")
    assert status == 200 and view["override_path"] is None and view["changed"] == []
    assert view["centerline_types"]["PlotPenColor"] == "color"

    eff = view["effective"]
    eff["postimport"]["centerline"]["PlotPenColor"] = -16776961   # blue
    eff["points"]["air-draught"] = {"label": "Z"}
    status, saved = _call(base, "/api/mapping/1220", {"effective": eff})
    assert status == 200 and saved["changed"] == ["points", "postimport"]
    written = json.loads((leaf / "tdx-mapping-objekt.json").read_text(encoding="utf-8"))
    assert written["points"] == {"air-draught": {"label": "Z"}}
    assert written["postimport"] == {"centerline": {"PlotPenColor": -16776961}}
    assert "lines" not in written  # only the difference is stored

    status, back = _call(base, "/api/mapping/1220/reset", {})
    assert status == 200 and back["override_path"] is None
    assert not (leaf / "tdx-mapping-objekt.json").exists()


def test_mapping_page_refuses_bad_input_and_caves_without_a_folder(server):
    base, _, leaf = server
    _, view = _call(base, "/api/mapping/1220")
    eff = view["effective"]
    eff["points"]["clay"] = {"orientation": 90}            # no target
    status, data = _call(base, "/api/mapping/1220", {"effective": eff})
    assert status == 400 and "clay" in data["error"]
    _, view = _call(base, "/api/mapping/1220")
    eff = view["effective"]
    eff["postimport"]["centerline"]["PlotPenWidth"] = "debelo"
    status, data = _call(base, "/api/mapping/1220", {"effective": eff})
    assert status == 400 and "PlotPenWidth" in data["error"]
    status, data = _call(base, "/api/mapping/999", {"effective": {}})
    assert status == 400 and "nema mapu" in data["error"]
    assert not (leaf / "tdx-mapping-objekt.json").exists()
