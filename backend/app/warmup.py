"""Fill the caches for the configured routes once the service is up.

The first person to open the briefing after a restart should not be the one
who waits for seven waypoints × seventeen hours of forecast, the ensemble and a model call. Nothing
here can take the service down: every step logs and carries on.
"""

import asyncio
import fcntl
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import get_args

from .config import Settings
from .models import Lang
from .sources import Sources
from .sources.weather_common import local_today

log = logging.getLogger(__name__)

LOCK_NAME = "warmup.lock"


def claim(cache_dir: Path):
    """An exclusive, non-blocking lock, held for the life of the process, or None if another holds it.

    uvicorn runs several workers over one disk cache; one of them warming is enough.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    handle = (cache_dir / LOCK_NAME).open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


async def warm(sources: Sources, route_ids: list[str], langs: tuple[str, ...] = get_args(Lang)) -> list[str]:
    """Assess and narrate each route for today and tomorrow. Returns one summary line per step."""
    done: list[str] = []
    today = local_today()
    for route_id in route_ids:
        try:
            route = await sources.routes.get_route(route_id)
        except Exception:
            log.exception("warm-up: route %s failed", route_id)
            continue
        if route is None:
            log.warning("warm-up: unknown route %s", route_id)
            continue
        for day in (today, today + timedelta(days=1)):
            started = time.monotonic()
            try:
                assessment = await sources.assessor.assess(route, day)
            except Exception:
                log.exception("warm-up: assessment of %s on %s failed", route_id, day)
                continue
            line = f"{route_id} {day} {assessment.outcome} ({assessment.forecast.model})"
            log.warning("warm-up: assessed %s in %.1f s", line, time.monotonic() - started)
            done.append(line)
            if assessment.outcome == "not_assessable":
                continue
            for lang in langs:
                started = time.monotonic()
                try:
                    narration = await sources.narrator.narrate(route, assessment, lang)
                except Exception:
                    log.exception("warm-up: narration of %s on %s in %s failed", route_id, day, lang)
                    continue
                phrased = sum(1 for hazard in narration.hazards if hazard.body)
                log.warning(
                    "warm-up: narrated %s %s %s: %d/%d bodies in %.1f s",
                    route_id,
                    day,
                    lang,
                    phrased,
                    len(narration.hazards),
                    time.monotonic() - started,
                )
                done.append(f"{route_id} {day} {lang} {phrased}/{len(narration.hazards)}")
    return done


def start(settings: Settings, sources: Sources) -> asyncio.Task | None:
    """Warm in the background if this worker wins the lock. The task is returned so it can be cancelled."""
    if not settings.warmup_enabled or not settings.warmup_routes:
        return None
    lock = claim(settings.cache_dir)
    if lock is None:
        log.info("warm-up: another worker is warming the cache")
        return None
    task = asyncio.create_task(warm(sources, settings.warmup_routes))
    # Held for the life of the process (the handle must outlive this call): a sibling worker that
    # starts later sees it taken and does not warm again.
    task.lock = lock  # type: ignore[attr-defined]
    return task
