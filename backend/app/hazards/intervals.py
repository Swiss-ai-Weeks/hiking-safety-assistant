"""Hourly severities as the intervals the frontend looks an arrival time up in."""

from collections.abc import Iterable

from ..models import Minutes, Severity, SeverityInterval, Window
from .rules import RANK


def merge(rows: Iterable[tuple[Minutes, Minutes, Severity]]) -> list[SeverityInterval]:
    """Adjacent rows of equal severity joined, and "none" left out: absence already means none."""
    merged: list[SeverityInterval] = []
    for start, end, severity in sorted(rows):
        if severity == "none" or end <= start:
            continue
        last = merged[-1] if merged else None
        if last is not None and last.severity == severity and last.to == start:
            merged[-1] = SeverityInterval(from_=last.from_, to=end, severity=severity)
        else:
            merged.append(SeverityInterval(from_=start, to=end, severity=severity))
    return merged


def severity_at(intervals: list[SeverityInterval], minute: float) -> Severity:
    for interval in intervals:
        if interval.from_ <= minute < interval.to:
            return interval.severity
    return "none"


def peak(intervals: list[SeverityInterval]) -> Severity:
    return max((interval.severity for interval in intervals), key=RANK.__getitem__, default="none")


def window_of(stops: dict[str, list[SeverityInterval]]) -> Window:
    """Where the hazard is at its worst: the span of its high intervals, or of all of them."""
    every = [interval for intervals in stops.values() for interval in intervals]
    worst = [interval for interval in every if interval.severity == "high"] or every
    return Window(from_=min(i.from_ for i in worst), to=max(i.to for i in worst))
