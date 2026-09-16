"""The one failure type, in a module that depends on nothing.

It lived in `sources/base.py`, which is where it belongs conceptually — but importing it from the
routing layer pulled in `app.sources.__init__`, and that imports the live sources, which import
the routing layer. A leaf module breaks the cycle without anyone having to think about import
order. `sources.base` re-exports it, so every existing import still reads the same.
"""


class SourceUnavailable(Exception):
    """A source could not answer: unreachable, unparseable, or not implemented yet.

    The single failure type the API maps onto `not_assessable` or a specific gap, so degradation
    is honest rather than silent.
    """

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason
