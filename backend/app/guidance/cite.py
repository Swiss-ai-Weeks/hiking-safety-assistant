"""Which passages ground a hazard: the ones about its kind, on the ground where it is worst."""

from ..hazards.intervals import peak
from ..hazards.rules import RANK
from ..hazards.terrain import StopTerrain, terrain_for
from ..models import HazardDef, HazardKind, Route
from .corpus import Passage
from .retrieve import search

# What each kind is about, in the words the passages use. The tags do most of the work; these
# order the tagged passages among themselves.
KIND_QUERY: dict[HazardKind, str] = {
    "gusts": "wind strong gusts exposed ridge balance",
    "showers": "rain wet rock slippery descent dry terrain",
    "thunder": "thunderstorm lightning storm ridge summit shelter",
    "cold": "cold wind chill fingers grip",
    "snow": "snow firn ice freezing snowfields",
    "visibility": "cloud visibility path markings orientation",
    "daylight": "time pace late tired back",
}

CITATIONS_PER_HAZARD = 2


def worst_stop(hazard: HazardDef) -> str | None:
    """The stop the hazard is named after, chosen as `hazards/engine.py` chooses it."""
    if not hazard.stops:
        return None
    return min(hazard.stops, key=lambda stop_id: (-RANK[peak(hazard.stops[stop_id])], hazard.stops[stop_id][0].from_))


def terrain_at(route: Route, hazard: HazardDef) -> StopTerrain | None:
    stop_id = worst_stop(hazard)
    return next((t for t in terrain_for(route) if t.stop_id == stop_id), None)


def citations_for(route: Route, hazard: HazardDef, k: int = CITATIONS_PER_HAZARD) -> list[Passage]:
    terrain = terrain_at(route, hazard)
    grade = terrain.grade if terrain else route.grade
    query = KIND_QUERY[hazard.kind]
    if terrain and terrain.cables:
        query += " cables"
    return search(query, kind=hazard.kind, grade=grade, k=k)
