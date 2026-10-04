"""`cavedossier gui` — a local web dashboard over every stage.

A standard-library HTTP server on 127.0.0.1 serving one page (``static/``) and
a small JSON API. The page is the mockup of the future GUI; the API is what a
real front end would talk to, so it is shaped as the program's actual surface:
state, caves, the action catalog, jobs, and "open this in its own app".

Safety: it binds to localhost only, and every API call must carry the random
token baked into the page it served — so another web page open in the same
browser cannot drive it. Only catalog actions run (``catalog.py``), with argv
built from validated inputs and no shell.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cave_dossier.core.paths import repo_root, workspace, workspace_root
from cave_dossier.gui import catalog, layouts, mapping, media
from cave_dossier.gui.jobs import JobManager, SequenceStep, cli_argv, script_argv
from cave_dossier.gui.state import Workspace, csurvey_exe, tools_dir

STATIC = Path(__file__).parent / "static"
_CONTENT_TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
                  ".svg": "image/svg+xml"}

DEFAULT_PORT = 8765


class _Server(ThreadingHTTPServer):
    """No address reuse. ``http.server`` turns SO_REUSEADDR on, and on Windows
    that lets a second server bind a port that is already serving — both then
    "listen", the older one answers, and the next-free-port fallback in
    ``serve`` never triggers (found 2026-10-02 with two dashboards on 8790).
    SO_EXCLUSIVEADDRUSE makes the second bind fail as it should."""

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        import socket

        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class ApiError(Exception):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


class App:
    """Everything the handler needs; one per server, easy to build in tests."""

    def __init__(self, ws: Workspace | None = None, jobs: JobManager | None = None,
                 token: str | None = None, opener=None, deleter=None) -> None:
        self.ws = ws or Workspace()
        log_dir = None
        try:
            log_dir = workspace("runs", "gui")
        except Exception:  # noqa: BLE001 — no workspace: jobs just are not logged
            pass
        self.jobs = jobs or JobManager(log_dir)
        self.token = token or secrets.token_urlsafe(16)
        self.opener = opener or _open_with_os
        self.deleter = deleter or media.recycle

    # ── actions ─────────────────────────────────────────────────────
    def run(self, body: dict) -> dict:
        action = catalog.BY_ID.get(str(body.get("action")))
        if action is None or action.tool == "manual":
            raise ApiError("Nepoznata radnja.")
        selected = body.get("options") or {}
        broj = _int_or_none(body.get("broj"))
        file = body.get("file") or None
        if action.file_kind:
            if broj is None:
                raise ApiError("Odaberi objekt (Redni broj).")
            allowed = self.ws.candidate_files(broj, action.file_kind)
            if file not in allowed:
                raise ApiError("Ta datoteka nije u mapi objekta ili nije za ovaj korak.")
        try:
            args = catalog.build_args(action, broj=broj, file=file,
                                      query=body.get("query"), selected=selected)
        except catalog.ActionError as exc:
            raise ApiError(str(exc)) from exc
        writes = catalog.is_write(action, selected)
        if writes and not body.get("confirmed"):
            raise ApiError(f"Potrebna potvrda: {writes}", HTTPStatus.CONFLICT)
        argv, display = self.argv_for(action, args)
        cwd = _safe_root()
        job = self.jobs.start(action.title, argv, display, cwd)
        return job.to_json()

    def recipe(self, body: dict) -> dict:
        """A ★ fast action: its steps as one sequence job. Each step is built
        exactly like a single run (catalog argv only); the writes of every
        step are confirmed together, and a ``queued`` step is dropped when the
        cave has nothing in the photo queue."""
        recipe = catalog.RECIPES_BY_ID.get(str(body.get("recipe")))
        if recipe is None:
            raise ApiError("Nepoznata brza radnja.")
        broj = _int_or_none(body.get("broj"))
        if broj is None:
            raise ApiError("Odaberi objekt (Redni broj).")
        skip = {int(i) for i in body.get("skip") or [] if str(i).isdigit()}
        queued = bool(self.ws.queue().get(broj))
        steps: list[SequenceStep] = []
        writes: list[str] = []
        for index, step in enumerate(recipe.steps):
            if index in skip or (step.when == "queued" and not queued):
                continue
            action = catalog.BY_ID[step.action]
            selected = dict(step.options)
            file = None
            if action.file_kind:
                candidates = self.ws.candidate_files(broj, action.file_kind)
                if not candidates:
                    raise ApiError(f"{action.title}: nema datoteke za taj korak.")
                file = candidates[0]
            try:
                args = catalog.build_args(action, broj=broj, file=file, selected=selected)
            except catalog.ActionError as exc:
                raise ApiError(f"{action.title}: {exc}") from exc
            argv, display = self.argv_for(action, args)
            steps.append(SequenceStep(action.title, argv, display, step.keep_going))
            what = catalog.is_write(action, selected)
            if what:
                writes.append(f"{action.title}: {what}")
        if not steps:
            raise ApiError("Nijedan korak nije odabran.")
        if writes and not body.get("confirmed"):
            raise ApiError("Potrebna potvrda: " + "; ".join(writes), HTTPStatus.CONFLICT)
        job = self.jobs.start_sequence(f"★ {recipe.title} · {broj}", steps, _safe_root())
        return job.to_json()

    def argv_for(self, action: catalog.Action, args: list[str]) -> tuple[list[str], str]:
        if action.tool == "cli":
            return cli_argv(args), "cavedossier " + _join(args)
        tools = tools_dir()
        if tools is None:
            raise ApiError("3N alati nisu pronađeni (nema stages/3N-nacrt/production/"
                           "tools, a CSX_TOOLS nije postavljen).")
        script = tools / action.tool
        if not script.is_file():
            raise ApiError(f"Nema skripte {script}.")
        return script_argv(script, args), f"python $T\\{action.tool} " + _join(args)

    # ── 3N mapping ──────────────────────────────────────────────────
    def mapping_api(self, verb: str, parts: list[str], body: dict | None = None) -> dict:
        """GET mapping-catalog · GET mapping/<broj> · POST mapping/<broj>
        {effective} · POST mapping/<broj>/reset (gui/mapping.py)."""
        tools = tools_dir()
        if tools is None:
            raise ApiError("3N alati nisu pronađeni (nema stages/3N-nacrt/production/"
                           "tools, a CSX_TOOLS nije postavljen).")
        try:
            if parts[0] == "mapping-catalog":
                return mapping.catalog(tools)
            broj = _int(parts[1])
            if verb == "GET":
                return mapping.view(self.ws, broj, tools)
            if len(parts) == 3 and parts[2] == "reset":
                return mapping.reset(self.ws, broj, tools)
            return mapping.save(self.ws, broj, tools, (body or {}).get("effective"))
        except mapping.MappingError as exc:
            raise ApiError(str(exc)) from exc
        except OSError as exc:
            raise ApiError(f"Mapiranje: {exc}") from exc

    # ── 3N KORAK 3a layout menu ─────────────────────────────────────
    def layouts(self, query: dict) -> dict:
        """GET layouts?broj=&path= — the sheets KORAK 3a would offer (gui/layouts.py)."""
        broj = _int(query.get("broj"))
        path = str(query.get("path", ""))
        if path not in self.ws.candidate_files(broj, "postp"):
            raise ApiError("Nije _postp datoteka ovog objekta.", HTTPStatus.NOT_FOUND)
        tools = tools_dir()
        if tools is None:
            raise ApiError("3N alati nisu pronađeni (nema stages/3N-nacrt/production/"
                           "tools, a CSX_TOOLS nije postavljen).")
        try:
            return layouts.menu(tools, Path(path))
        except layouts.LayoutError as exc:
            raise ApiError(str(exc)) from exc

    # ── photos ──────────────────────────────────────────────────────
    PHOTO_KINDS = {"photo", "photo_processed", "queued"}

    def thumb(self, query: dict) -> tuple[bytes, str]:
        item = self.ws.cave_file(_int(query.get("broj")), str(query.get("path", "")),
                                 self.PHOTO_KINDS | {"karta"})
        if item is None:
            raise ApiError("Nije fotografija ovog objekta.", HTTPStatus.NOT_FOUND)
        cache = None
        try:
            cache = workspace("runs", "gui", "thumbs")
        except Exception:  # noqa: BLE001
            pass
        return media.thumbnail(Path(item["path"]), cache, _int(query.get("w", "240")))

    def delete(self, body: dict) -> dict:
        """Photos only, only the current cave's, always recoverable (media.recycle)."""
        if not body.get("confirmed"):
            raise ApiError("Potrebna potvrda brisanja.", HTTPStatus.CONFLICT)
        item = self.ws.cave_file(_int(body.get("broj")), str(body.get("path", "")),
                                 self.PHOTO_KINDS)
        if item is None:
            raise ApiError("Briše se samo fotografija iz mape ovog objekta.",
                           HTTPStatus.FORBIDDEN)
        self.deleter(Path(item["path"]))
        return {"deleted": item["path"]}

    def doc(self, rel: str) -> dict:
        """A Markdown doc from the repo for the in-page viewer (dev only —
        prod has no repo, and says so)."""
        root = repo_root()
        if root is None:
            raise ApiError("Dokumentacija je dostupna samo u razvojnoj kopiji (repo).",
                           HTTPStatus.NOT_FOUND)
        target = (root / rel).resolve()
        if root.resolve() not in target.parents or target.suffix.lower() != ".md":
            raise ApiError("Samo .md datoteke iz repozitorija.", HTTPStatus.FORBIDDEN)
        if not target.is_file():
            raise ApiError(f"Nema {rel}.", HTTPStatus.NOT_FOUND)
        return {"path": target.relative_to(root.resolve()).as_posix(),
                "abs": str(target), "text": target.read_text(encoding="utf-8")}

    def dossier(self, broj: int) -> dict:
        s = self.ws.settings
        if s is None:
            raise ApiError("Postavke nisu učitane.")
        try:
            from cave_dossier.dossier import view_for_serial
        except ImportError as exc:
            raise ApiError(f"Dosje još nije dostupan na stranici ({exc}).") from exc
        view = view_for_serial(s, broj)
        if view is None:
            raise ApiError(f"Nijedan SB red nema Redni broj {broj}.", HTTPStatus.NOT_FOUND)
        return view

    def open(self, body: dict) -> dict:
        what = body.get("what")
        target: Path | None = None
        app: Path | None = None
        reveal = bool(body.get("reveal"))
        if what == "sb":
            live = self.ws.summary().get("sb", {}).get("live")
            target = Path(live) if live else None
        elif what == "sb-reading":
            s = self.ws.settings
            target = s.sb_workbook_path if s else None
        elif what == "drive":
            target = self.ws.drive_dir(str(body.get("key")))
        elif what == "drive-root":
            target = self.ws.drive_root
        elif what == "workspace":
            target = workspace(str(body.get("key")))
            target.mkdir(parents=True, exist_ok=True)
        elif what == "readme":
            root = repo_root()
            target = (root / str(body.get("path"))) if root else None
        elif what in ("path", "csurvey"):
            target = Path(str(body.get("path") or ""))
            if what == "csurvey":
                app = csurvey_exe(self.ws.drive_root)
                if app is None:
                    raise ApiError("cSurvey nije pronađen (C:\\csurvey64 ili CSURVEY_DIR u .env).")
        else:
            raise ApiError("Nepoznato što otvoriti.")
        if target is None:
            raise ApiError("Putanja nije podešena (provjeri LOCAL_DRIVE_ROOT u .env).")
        if not self.ws.is_allowed(target):
            raise ApiError("Putanja je izvan Drivea i radnog prostora.", HTTPStatus.FORBIDDEN)
        if not target.exists():
            raise ApiError(f"Ne postoji: {target}", HTTPStatus.NOT_FOUND)
        self.opener(target, app=app, reveal=reveal)
        return {"opened": str(target)}


# ── HTTP ────────────────────────────────────────────────────────────


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CaveDossierGUI/0.1"

        def log_message(self, fmt, *args):  # quiet console; jobs have their own logs
            pass

        # -- plumbing --
        def _send(self, status: int, body: bytes, ctype: str) -> None:
            try:
                self.send_response(status)
                self.send_header("Content-Type", f"{ctype}; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                # The browser left mid-reply (reload, closed tab); nobody to answer.
                self.close_connection = True

        def _json(self, data, status: int = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json")

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ApiError("Neispravan JSON.") from exc
            return data if isinstance(data, dict) else {}

        def _authorized(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Token", ""), app.token)

        # -- verbs --
        def do_GET(self):  # noqa: N802
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text(encoding="utf-8")
                html = html.replace("__TOKEN__", app.token)
                return self._send(HTTPStatus.OK, html.encode("utf-8"), "text/html")
            if url.path.startswith("/static/"):
                name = url.path.removeprefix("/static/")
                path = (STATIC / name).resolve()
                if STATIC.resolve() not in path.parents or not path.is_file():
                    return self._json({"error": "nema"}, HTTPStatus.NOT_FOUND)
                ctype = _CONTENT_TYPES.get(path.suffix, "application/octet-stream")
                return self._send(HTTPStatus.OK, path.read_bytes(), ctype)
            if url.path == "/api/thumb":
                # An <img> cannot send a header, so this one GET takes the
                # token as a query parameter. It only ever serves the
                # current cave's photos (App.thumb).
                query = {k: v[-1] for k, v in parse_qs(url.query).items()}
                if not secrets.compare_digest(query.get("t", ""), app.token):
                    return self._json({"error": "Nedostaje token."}, HTTPStatus.FORBIDDEN)
                try:
                    data, ctype = app.thumb(query)
                except ApiError as exc:
                    return self._json({"error": str(exc)}, exc.status)
                except OSError as exc:
                    return self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "private, max-age=300")
                self.end_headers()
                self.wfile.write(data)
                return None
            if url.path.startswith("/api/"):
                return self._api("GET", url)
            return self._json({"error": "nema"}, HTTPStatus.NOT_FOUND)

        def do_POST(self):  # noqa: N802
            url = urlparse(self.path)
            if url.path.startswith("/api/"):
                return self._api("POST", url)
            return self._json({"error": "nema"}, HTTPStatus.NOT_FOUND)

        def _api(self, verb: str, url) -> None:
            if not self._authorized():
                return self._json({"error": "Nedostaje token."}, HTTPStatus.FORBIDDEN)
            query = {k: v[-1] for k, v in parse_qs(url.query).items()}
            parts = [p for p in url.path.split("/") if p][1:]  # drop "api"
            try:
                data = self._route(verb, parts, query)
            except ApiError as exc:
                return self._json({"error": str(exc)}, exc.status)
            except Exception as exc:  # noqa: BLE001 — the page shows it, the server lives on
                return self._json({"error": f"{type(exc).__name__}: {exc}"},
                                  HTTPStatus.INTERNAL_SERVER_ERROR)
            return self._json(data)

        def _route(self, verb: str, parts: list[str], query: dict):
            head = parts[0] if parts else ""
            if verb == "GET":
                if head == "state":
                    return app.ws.summary()
                if head == "catalog":
                    return catalog.catalog_json()
                if head == "caves":
                    force = query.get("refresh") == "1"
                    caves, unprefixed = app.ws.caves(force=force)
                    queue = app.ws.queue(force=force)
                    return {"caves": [c.to_json() for c in caves], "unprefixed": unprefixed,
                            "queue": {str(k): len(v) for k, v in queue.items()}}
                if head == "cave" and len(parts) == 2:
                    return app.ws.cave_view(_int(parts[1]))
                if head == "sb-index":
                    return app.ws.sb_index()
                if head == "doc":
                    return app.doc(str(query.get("path", "")))
                if head == "dossier" and len(parts) == 2:
                    return app.dossier(_int(parts[1]))
                if head == "files":
                    return {"files": app.ws.candidate_files(_int(query.get("broj")),
                                                            query.get("kind", ""))}
                if head == "layouts":
                    return app.layouts(query)
                if head == "mapping-catalog" or (head == "mapping" and len(parts) == 2):
                    return app.mapping_api("GET", parts)
                if head == "societies":
                    from cave_dossier.core import societies
                    return societies.registry().to_json()
                if head == "jobs":
                    return {"jobs": [j.to_json(since=10**9) for j in app.jobs.list()]}
                if head == "job" and len(parts) == 2:
                    job = _job(parts[1])
                    return job.to_json(since=_int(query.get("since", "0")))
            if verb == "POST":
                body = self._body()
                if head == "run":
                    return app.run(body)
                if head == "recipe":
                    return app.recipe(body)
                if head == "open":
                    return app.open(body)
                if head == "delete":
                    try:
                        return app.delete(body)
                    except OSError as exc:
                        raise ApiError(str(exc)) from exc
                if head == "mapping" and len(parts) in (2, 3):
                    return app.mapping_api("POST", parts, body)
                if head == "refresh":
                    app.ws.refresh()
                    return {"ok": True}
                if head == "job" and len(parts) == 3:
                    job = _job(parts[1])
                    if parts[2] == "input":
                        if not job.send(str(body.get("line", ""))):
                            raise ApiError("Program više ne čeka unos.")
                        return {"ok": True}
                    if parts[2] == "kill":
                        job.kill()
                        return {"ok": True}
            raise ApiError("Nepoznat zahtjev.", HTTPStatus.NOT_FOUND)

    def _job(raw: str):
        job = app.jobs.get(_int(raw))
        if job is None:
            raise ApiError("Nema tog posla.", HTTPStatus.NOT_FOUND)
        return job

    return Handler


def serve(port: int = DEFAULT_PORT, open_browser: bool = True) -> int:
    app = App()
    server = None
    for candidate in range(port, port + 20):
        try:
            server = _Server(("127.0.0.1", candidate), make_handler(app))
            break
        except OSError:
            continue
    if server is None:
        print(f"ERROR: nijedan port od {port} do {port + 19} nije slobodan.", file=sys.stderr)
        return 99
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Nadzorna ploča: {url}")
    print("Zaustavi s Ctrl+C.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZaustavljeno.")
    finally:
        server.server_close()
    return 0


# ── helpers ─────────────────────────────────────────────────────────


def _open_with_os(target: Path, app: Path | None = None, reveal: bool = False) -> None:
    if app is not None:
        # cSurvey lowercases a bare filename argument (cCommandLineParameters.vb:142)
        # and Drive's .shortcut-targets-by-id\<ID>\… paths stop resolving once the
        # ID is lowercased; the value of filename=… keeps its case.
        subprocess.Popen([str(app), f"filename={target}"], close_fds=True)
        return
    if os.name == "nt":
        if reveal:
            subprocess.Popen(["explorer", f"/select,{target}"])
        else:
            os.startfile(str(target))  # noqa: S606 — the whole point: open in its app
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(target.parent if reveal else target)])


def _join(args: list[str]) -> str:
    """How the terminal would spell it — PowerShell-friendly double quotes."""
    return " ".join(f'"{a}"' if (" " in a or not a) else a for a in args)


def _int(raw) -> int:
    try:
        return int(str(raw))
    except (TypeError, ValueError) as exc:
        raise ApiError(f"Očekujem broj, a ne '{raw}'.") from exc


def _int_or_none(raw) -> int | None:
    return None if raw in (None, "") else _int(raw)


def _safe_root() -> Path:
    try:
        return workspace_root()
    except Exception:  # noqa: BLE001
        return Path.cwd()


__all__ = ["App", "make_handler", "serve", "DEFAULT_PORT"]
