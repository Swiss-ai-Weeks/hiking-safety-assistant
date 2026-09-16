"""What a stop is like underfoot, as far as a hazard rule cares.

A rule never reads a `Route` directly. It reads one `StopTerrain`: how high the stop is and how
hard the ground either side of it is. The ground is taken from the legs that touch the stop, and
`Leg.stop_ids` lists return stops as well as outbound ones, so the descent past a col is graded
like the ascent to it — which is the point: the same wet slab is the same slab on the way down.
"""

from dataclasses import dataclass

from ..domain import GeoPoint
from ..models import Grade, Route
from ..routing.timing import GRADE_ORDER

# From T3 the SAC scale describes exposed ground: sure-footedness required, a slip has consequences.
EXPOSED_FROM: Grade = "T3"


def at_least(grade: Grade, floor: Grade) -> bool:
    return GRADE_ORDER.index(grade) >= GRADE_ORDER.index(floor)


@dataclass(frozen=True, slots=True)
class StopTerrain:
    stop_id: str
    waypoint_id: str
    # Official place name of the waypoint, for `HazardDef.place`.
    name: str
    point: GeoPoint
    # The hardest leg touching the stop.
    grade: Grade
    cables: bool

    @property
    def exposed(self) -> bool:
        return self.cables or at_least(self.grade, EXPOSED_FROM)


def terrain_for(route: Route) -> list[StopTerrain]:
    """One entry per timeline stop, in walking order."""
    waypoints = {waypoint.id: waypoint for waypoint in route.waypoints}
    terrain = []
    for stop in route.stops:
        waypoint = waypoints[stop.waypoint_id]
        touching = [leg for leg in route.legs if stop.id in leg.stop_ids]
        # A stop no leg claims is graded as the route: the conservative reading, not the kind one.
        grade = max((leg.grade for leg in touching), key=GRADE_ORDER.index, default=route.grade)
        terrain.append(
            StopTerrain(
                stop_id=stop.id,
                waypoint_id=stop.waypoint_id,
                name=waypoint.name,
                point=GeoPoint(*waypoint.lat_lng, float(waypoint.elevation_m)),
                grade=grade,
                cables=any(leg.cables for leg in touching),
            )
        )
    return terrain
