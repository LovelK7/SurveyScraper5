"""The society archive on Drive — reading what is filed there.

Today: `Izjava za katastar` filename semantics. Next (rest of M2): the intake
that resolves a cave's nacrt, zapisnik, photos and izjave from the archive dirs
and fills `Source.ARCHIVE` on the dossier.
"""

from cave_dossier.archive.izjave import Izjava, covers, is_izjava_file, parse_izjava

__all__ = ["Izjava", "covers", "is_izjava_file", "parse_izjava"]
