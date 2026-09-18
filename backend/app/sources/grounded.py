"""Cites the guidance a hazard is grounded in, in its provenance footnote.

A wrapper rather than a change to the engine: the engine's own output (and its cache, and its
tests) stay exactly what they were, and retrieval is cheap enough to run on every response.
"""

from datetime import date

from ..guidance import citations_for
from ..models import AssessmentData, Route
from .base import Assessor


class GroundedAssessor:
    def __init__(self, inner: Assessor) -> None:
        self.inner = inner

    async def assess(self, route: Route, day: date | None = None) -> AssessmentData:
        data = await self.inner.assess(route, day)
        hazards = []
        for hazard in data.hazards:
            cited = citations_for(route, hazard, k=1)
            if cited:
                provenance = f"{hazard.provenance} · {cited[0].cite}"
                hazard = hazard.model_copy(update={"provenance": provenance})
            hazards.append(hazard)
        return data.model_copy(update={"hazards": hazards})

    async def recheck(self, day: date | None = None) -> bool:
        return await self.inner.recheck(day)
