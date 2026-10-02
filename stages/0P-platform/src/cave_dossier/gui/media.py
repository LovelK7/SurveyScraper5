"""Photos on the page: thumbnails, and deleting a photo the recoverable way.

Thumbnails are cut with Pillow when it is installed (the `photos` extra) and
cached under ``runs/gui/thumbs`` by path + size + mtime, so a Drive-streamed
original is read once. Without Pillow the original bytes are served: slower,
but the gallery still works.

Deleting never destroys the file outright. On Windows it goes through the shell
with "allow undo", which sends a local file to the Recycle Bin. On the Google
Drive folder the shell has no Recycle Bin, and Drive for desktop moves the
deleted file to the Drive trash instead (recoverable for 30 days). Either way
the user can get it back.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

THUMB_SIZES = (240, 480)


def thumbnail(source: Path, cache_dir: Path | None, width: int) -> tuple[bytes, str]:
    """(bytes, content type) of a ``width``-pixel preview of ``source``."""
    width = min(THUMB_SIZES, key=lambda size: abs(size - width))
    stat = source.stat()
    key = hashlib.sha1(f"{source}|{stat.st_size}|{stat.st_mtime}|{width}".encode()).hexdigest()
    cached = cache_dir / f"{key}.jpg" if cache_dir else None
    if cached is not None and cached.is_file():
        return cached.read_bytes(), "image/jpeg"
    try:
        from io import BytesIO

        from PIL import Image, ImageOps

        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((width, width * 2))
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            buffer = BytesIO()
            image.save(buffer, "JPEG", quality=82)
        data = buffer.getvalue()
    except Exception:  # noqa: BLE001 — no Pillow / HEIC / odd file: serve the original
        suffix = source.suffix.lower()
        ctype = "image/png" if suffix == ".png" else "image/jpeg"
        return source.read_bytes(), ctype
    if cached is not None:
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        except OSError:
            pass
    return data, "image/jpeg"


def recycle(path: Path) -> None:
    """Delete ``path`` so that it can be restored; raises OSError on failure."""
    if os.name != "nt":
        raise OSError("Brisanje s mogućnošću povratka podržano je samo na Windowsu.")
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND), ("wFunc", ctypes.c_uint),
            ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 0x4, 0x10, 0x40, 0x400
    op = SHFILEOPSTRUCTW(
        hwnd=None, wFunc=FO_DELETE, pFrom=str(path) + "\0", pTo=None,
        fFlags=FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI,
    )
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if result != 0 or op.fAnyOperationsAborted or path.exists():
        raise OSError(f"Brisanje nije uspjelo (kod {result}).")
