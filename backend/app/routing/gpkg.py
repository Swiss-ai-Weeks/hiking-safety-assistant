"""Reading a GeoPackage with the standard library.

A GeoPackage *is* a SQLite database, so `sqlite3` opens it directly. The only thing standing
between a row and a geometry is a small binary header the spec wraps around otherwise ordinary
WKB. Stripping it here is about sixty lines and buys us out of GDAL entirely — no `fiona`, no
`pyogrio`, no system libraries to install on the VM. Phase 2's eccodes is the toolchain risk this
project can afford; a second one is not.

Spec: <https://www.geopackage.org/spec/#gpb_format>
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from shapely import Geometry, from_wkb

GPKG_MAGIC = b"GP"

# Flag bits 1-3 select the envelope, whose size is what we actually need in order to skip it.
ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def strip_gpkg_header(blob: bytes) -> bytes:
    """The WKB inside a GeoPackage geometry blob."""
    if not blob.startswith(GPKG_MAGIC):
        # Some writers store bare WKB. Accept it rather than failing on a technicality.
        return blob

    flags = blob[3]
    envelope = ENVELOPE_BYTES.get((flags >> 1) & 0b111)
    if envelope is None:
        raise ValueError(f"reserved envelope indicator in GeoPackage header: flags={flags:#04x}")

    # 2 magic + 1 version + 1 flags + 4 srs_id, then the envelope.
    return blob[8 + envelope :]


def geometry_columns(db: sqlite3.Connection) -> dict[str, str]:
    """Table name -> geometry column, from the registry every GeoPackage is required to carry."""
    rows = db.execute("SELECT table_name, column_name FROM gpkg_geometry_columns").fetchall()
    return {table: column for table, column in rows}


def feature_tables(db: sqlite3.Connection) -> list[str]:
    rows = db.execute("SELECT table_name FROM gpkg_contents WHERE data_type = 'features'").fetchall()
    return [table for (table,) in rows]


def read_features(path: Path, table: str, columns: list[str]) -> Iterator[tuple[Geometry, dict]]:
    """Every feature in `table` as (shapely geometry, attributes).

    Streams: the national Wanderwege layer has hundreds of thousands of rows and there is no
    reason to hold them all at once.
    """
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        geom_column = geometry_columns(db).get(table)
        if geom_column is None:
            raise ValueError(f"{table} is not a feature table in {path.name}")

        selected = [geom_column, *columns]
        quoted = ", ".join(f'"{name}"' for name in selected)
        for row in db.execute(f'SELECT {quoted} FROM "{table}"'):  # noqa: S608 - names come from the file itself
            blob = row[0]
            if blob is None:
                continue
            yield from_wkb(strip_gpkg_header(blob)), dict(zip(columns, row[1:], strict=True))
    finally:
        db.close()


def describe(path: Path) -> str:
    """What is actually in this file. The first thing to run against a new download."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        geom_columns = geometry_columns(db)
        lines = []
        for table in feature_tables(db):
            count = db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]  # noqa: S608
            info = db.execute(f'PRAGMA table_info("{table}")').fetchall()
            lines.append(f"{table}: {count:,} rows, geometry in {geom_columns.get(table)!r}")
            for _, name, kind, *_ in info:
                lines.append(f"    {name} ({kind})")
        return "\n".join(lines)
    finally:
        db.close()
