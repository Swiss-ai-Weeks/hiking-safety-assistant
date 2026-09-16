"""Turn the national GeoPackage into the small routable graph the app actually loads.

The download is 390 MB and 409,276 rows covering every path in Switzerland. Parsing that at
startup would be absurd, and holding it in `networkx` would be worse. So the expensive work
happens exactly once, here: clip to a bounding box, snap endpoints so that touching lines share
a node, and write a plain SQLite file of nodes and edges that loads in well under a second.

Two things make this cheap. The GeoPackage ships an R-tree on the geometry column, so the clip
is an indexed lookup rather than a scan. And the geometries are 3D — swisstopo stores the height
on every vertex — so ascent and descent per edge come out of the file itself, with no elevation
service involved. That is what lets Dijkstra weight by *time* rather than by distance.

    uv run --directory backend python -m scripts.import_trails [--bbox E,N,E,N] [--out FILE]
"""

import argparse
import json
import sqlite3
import time
from pathlib import Path

from pyproj import Transformer
from shapely import from_wkb

from app.config import get_settings
from app.routing.gpkg import strip_gpkg_header

TABLE = "tlm_strassen_strasse"
RTREE = f"rtree_{TABLE}_geom"

# Endpoints are snapped to this grid, in LV95 metres, so that two lines drawn to the same
# junction become one graph node. TLM3D is accurate to well under a metre, so this only absorbs
# representation noise; raising it would start merging genuinely distinct junctions.
SNAP_M = 1.0

ATTRIBUTES = ["wanderwege", "objektart", "kunstbaute", "belagsart", "name"]

SCHEMA = """
CREATE TABLE node (
    id INTEGER PRIMARY KEY,
    e REAL NOT NULL, n REAL NOT NULL,
    lat REAL NOT NULL, lng REAL NOT NULL,
    elevation_m REAL
);
CREATE TABLE edge (
    id INTEGER PRIMARY KEY,
    a_node INTEGER NOT NULL REFERENCES node(id),
    b_node INTEGER NOT NULL REFERENCES node(id),
    length_m REAL NOT NULL,
    ascent_m REAL NOT NULL,
    descent_m REAL NOT NULL,
    trail_class TEXT,
    objektart TEXT,
    kunstbaute TEXT,
    name TEXT,
    -- [[lat, lng, elevation_m], ...] in walking order from a_node to b_node.
    geometry TEXT NOT NULL
);
CREATE INDEX edge_a ON edge(a_node);
CREATE INDEX edge_b ON edge(b_node);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def clipped_rows(source: Path, bbox: tuple[float, float, float, float]):
    """Every Wanderwege line whose bounding box meets `bbox`, via the GeoPackage's R-tree."""
    min_e, min_n, max_e, max_n = bbox
    db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        columns = ", ".join(f"s.{name}" for name in ATTRIBUTES)
        query = f"""
            SELECT s.geom, {columns}
            FROM {TABLE} s
            JOIN {RTREE} r ON s.id = r.id
            WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?
        """  # noqa: S608 - every name here is a constant above
        yield from db.execute(query, (min_e, max_e, min_n, max_n))
    finally:
        db.close()


class NodeTable:
    """Snapped endpoints, deduplicated. The whole reason disconnected lines become a network."""

    def __init__(self, transformer: Transformer) -> None:
        self.transformer = transformer
        self.rows: list[tuple[int, float, float, float, float, float | None]] = []
        self._by_cell: dict[tuple[int, int], int] = {}

    def id_for(self, e: float, n: float, elevation: float | None) -> int:
        cell = (round(e / SNAP_M), round(n / SNAP_M))
        existing = self._by_cell.get(cell)
        if existing is not None:
            return existing

        node_id = len(self.rows)
        lng, lat = self.transformer.transform(e, n)
        self.rows.append((node_id, e, n, lat, lng, elevation))
        self._by_cell[cell] = node_id
        return node_id


def climb(coords: list[tuple[float, float, float]]) -> tuple[float, float]:
    """Ascent and descent along a line, from the height on each vertex."""
    ascent = descent = 0.0
    for (_, _, a), (_, _, b) in zip(coords, coords[1:], strict=False):
        rise = b - a
        if rise > 0:
            ascent += rise
        else:
            descent -= rise
    return ascent, descent


def planar_length(coords: list[tuple[float, float, float]]) -> float:
    """Ground distance in metres. LV95 is metric, so this is just Pythagoras, no projection."""
    total = 0.0
    for (ax, ay, _), (bx, by, _) in zip(coords, coords[1:], strict=False):
        total += ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    return total


def build(source: Path, out: Path, bbox: tuple[float, float, float, float]) -> tuple[int, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    # LV95 (EPSG:2056) to WGS84. `always_xy` so the call reads (easting, northing) -> (lng, lat).
    transformer = Transformer.from_crs("EPSG:2056", "EPSG:4326", always_xy=True)
    nodes = NodeTable(transformer)
    edges: list[tuple] = []

    started = time.monotonic()
    for blob, *attributes in clipped_rows(source, bbox):
        if blob is None:
            continue
        line = from_wkb(strip_gpkg_header(blob))
        if not line.has_z or line.geom_type != "LineString":
            continue
        coords: list[tuple[float, float, float]] = list(line.coords)
        if len(coords) < 2:
            continue

        trail_class, objektart, kunstbaute, _belagsart, name = attributes
        a_node = nodes.id_for(coords[0][0], coords[0][1], coords[0][2])
        b_node = nodes.id_for(coords[-1][0], coords[-1][1], coords[-1][2])
        if a_node == b_node:
            # A closed loop with both ends on one node carries no routing information.
            continue

        ascent, descent = climb(coords)
        geometry = []
        for x, y, z in coords:
            lng, lat = transformer.transform(x, y)
            geometry.append([round(lat, 6), round(lng, 6), round(z, 1)])

        edges.append((
            len(edges), a_node, b_node,
            round(planar_length(coords), 1), round(ascent, 1), round(descent, 1),
            trail_class, objektart, kunstbaute, name,
            json.dumps(geometry, separators=(",", ":")),
        ))

    db = sqlite3.connect(out)
    try:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO node VALUES (?, ?, ?, ?, ?, ?)", nodes.rows)
        db.executemany("INSERT INTO edge VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", edges)
        db.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("source", source.name),
                ("bbox", json.dumps(list(bbox))),
                ("snap_m", str(SNAP_M)),
                ("imported_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                ("nodes", str(len(nodes.rows))),
                ("edges", str(len(edges))),
            ],
        )
        db.commit()
    finally:
        db.close()

    print(f"  {len(edges):,} edges, {len(nodes.rows):,} nodes in {time.monotonic() - started:,.1f}s")
    return len(nodes.rows), len(edges)


def parse_bbox(text: str) -> tuple[float, float, float, float]:
    parts = tuple(float(p) for p in text.split(","))
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be min_e,min_n,max_e,max_n in LV95 metres")
    return parts  # type: ignore[return-value]


def main() -> int:
    settings = get_settings()
    data_dir = settings.trails_db.parent

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=data_dir / "SWISSTLM3D_WANDERWEGE.gpkg")
    parser.add_argument("--out", type=Path, default=settings.trails_db)
    parser.add_argument("--bbox", type=parse_bbox, default=settings.trails_bbox)
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(f"{args.source} not found; run `python -m scripts.fetch_trails` first, then unzip it")

    print(f"importing {args.source.name} within {args.bbox}")
    build(args.source, args.out, args.bbox)
    print(f"  -> {args.out} ({args.out.stat().st_size / 1e6:,.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
