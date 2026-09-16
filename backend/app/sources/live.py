"""Placeholders for the live sources later phases own.

Each one fails when called, naming the phase that implements it. Failing per source rather than
at startup is what let Phases 1 and 2 land separately; the hazard engine is the one left.
"""

from ..models import AssessmentData, Route, Scenario
from .base import SourceUnavailable


class NotImplementedAssessor:
    phase = "Phase 3"

    async def assess(self, route: Route, scenario: Scenario) -> AssessmentData:
        raise SourceUnavailable("hazards", f"the hazard engine is not implemented yet ({self.phase})")
