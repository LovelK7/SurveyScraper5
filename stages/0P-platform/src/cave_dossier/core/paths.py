"""Where the workspace is — the one anchor every runtime path hangs off.

Replaces the old ``FEATURE_ROOT = Path(__file__).resolve().parents[3]``, which
was depth-sensitive: it silently repointed every default path the moment the
package moved, and it conflated three different roots into one.

Three roots, told apart:

* **workspace** — mutable state and per-machine config: ``config.yaml``,
  ``.env``, ``data/``, ``runs/``, ``sb-sync/``.  In dev that is the repo root;
  in prod it is the extracted bundle at ``%LOCALAPPDATA%\CaveDossier\v<X>``.
  Both carry the ``.cavedossier-workspace`` marker, so ONE rule finds both.
* **package assets** — runtime inputs that belong to their code (the OSZ
  template, ``selectors.yaml``, ``pristupi.yaml``).  These do NOT come from
  here: each module resolves its own as ``Path(__file__).parent / ...``, which
  works identically under an editable install, a wheel and the prod bundle,
  and means the asset travels with its subpackage.
* **repo** — dev-only, for reaching sibling checkouts (``../crospeleo-automation``).
  Returns ``None`` in prod, where there is no repo; callers must fail soft.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

WORKSPACE_ENV = "CAVEDOSSIER_WORKSPACE"
WORKSPACE_MARKER = ".cavedossier-workspace"
REPO_MARKERS = ("pipeline.yaml", ".git")


class WorkspaceNotFound(RuntimeError):
    """No workspace root could be located; the message names where we looked."""


def _walk_up_for(start: Path, name: str) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / name).exists():
            return candidate
    return None


@lru_cache(maxsize=1)
def workspace_root() -> Path:
    """The workspace root, in dev and in an extracted prod bundle alike.

    Resolution order — explicit override, then the package's own location,
    then the caller's cwd:

    1. ``$CAVEDOSSIER_WORKSPACE`` (tests and any future multi-workspace use)
    2. walk up from this file for ``.cavedossier-workspace``
    3. walk up from ``Path.cwd()`` for the same marker

    Raises ``WorkspaceNotFound`` naming every directory searched, rather than
    silently resolving to something wrong the way a ``parents[N]`` count did.
    """
    override = os.environ.get(WORKSPACE_ENV)
    if override:
        root = Path(override).expanduser().resolve()
        if not (root / WORKSPACE_MARKER).exists():
            raise WorkspaceNotFound(
                f"{WORKSPACE_ENV}={root} does not contain {WORKSPACE_MARKER}.\n"
                f"  Point it at the directory holding config.yaml and .env, or unset it."
            )
        return root

    here = Path(__file__).resolve()
    found = _walk_up_for(here.parent, WORKSPACE_MARKER)
    if found is not None:
        return found

    found = _walk_up_for(Path.cwd().resolve(), WORKSPACE_MARKER)
    if found is not None:
        return found

    searched = [str(here.parent), *(str(p) for p in here.parents)][:6]
    raise WorkspaceNotFound(
        f"No {WORKSPACE_MARKER} found above the package or the current directory.\n"
        f"  Looked upward from: {here.parent}\n"
        f"  and from:           {Path.cwd()}\n"
        f"  First few checked:  {', '.join(searched)}\n"
        f"  In a clone this file sits at the repo root; in a prod install it is\n"
        f"  written into %LOCALAPPDATA%\CaveDossier\v<X> by the bundle."
    )


def workspace(*parts: str) -> Path:
    """A path under the workspace root, e.g. ``workspace('data', 'geo')``."""
    return workspace_root().joinpath(*parts)


@lru_cache(maxsize=1)
def repo_root() -> Path | None:
    """The git repo root in dev, or ``None`` in a prod install.

    Only for reaching sibling checkouts. Never use it for anything a prod
    machine needs — there is no repo there, and this returns ``None``.
    """
    here = Path(__file__).resolve()
    for marker in REPO_MARKERS:
        found = _walk_up_for(here.parent, marker)
        if found is not None:
            return found
    return None
