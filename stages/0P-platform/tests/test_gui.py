"""`cavedossier gui`: the catalog, the workspace reader, jobs and the HTTP surface."""

from __future__ import annotations

import dataclasses
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from cave_dossier.cli import build_parser
from cave_dossier.gui import catalog
from cave_dossier.gui.jobs import JobManager
from cave_dossier.gui.server import App, make_handler
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
              opener=lambda target, app=None, reveal=False: opened.append(target))
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
