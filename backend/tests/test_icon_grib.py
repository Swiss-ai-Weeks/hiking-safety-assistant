"""ICON GRIB2: STAC parsing against recorded searches, the arithmetic, and the source end to end.

The end-to-end tests run the real source — run discovery, per-variable search, download, nearest
cell, cache — with a fake decoder standing in for eccodes, so they need neither the network nor
the GRIB toolchain. The one test that decodes a real message skips without eccodes.
"""

import json
from datetime import UTC, date, datetime, timedelta

import httpx
import numpy as np
import pytest
from conftest import load_fixture, save_fixture

from app.domain import GeoPoint
from app.errors import SourceUnavailable
from app.sources.http import CachedHttpClient
from app.sources.icon_grib import (
    GRIB_VARIABLES,
    Grid,
    IconGribSource,
    assemble,
    horizon_iso,
    hourly_precip,
    message_search,
    nearest_cell,
    parse_constants_href,
    parse_href,
    parse_runs,
    run_search,
)
from app.sources.weather_common import ICON_CH1, ICON_CH2, SWISS_TIME, model_for, target_time

pytestmark = pytest.mark.anyio

RUNS = "stac_icon_ch1_runs"
MESSAGE = "stac_icon_ch1_message_t2m"
COLLECTION = "stac_icon_ch1_collection"
HOHTURLI = GeoPoint(46.4888, 7.7717, 2778)


async def test_record_stac_fixtures(settings, recording):
    """`pytest --record` refreshes the three STAC fixtures. Plain pytest skips."""
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    async with CachedHttpClient(settings) as client:
        http = client._connection()
        search = f"{settings.stac_base_url}/search"
        runs = (await http.post(search, json=run_search(ICON_CH1))).raise_for_status().json()
        newest = parse_runs(runs)[0]
        message = (await http.post(search, json=message_search(ICON_CH1, newest, "T_2M", 3))).raise_for_status()
        collection = await http.get(f"{settings.stac_base_url}/collections/{ICON_CH1.stac_collection}")
    save_fixture(RUNS, runs)
    save_fixture(MESSAGE, json.loads(message.text, strict=False))
    save_fixture(COLLECTION, json.loads(collection.raise_for_status().text, strict=False))


# --- STAC ------------------------------------------------------------------------------------


def test_runs_parse_newest_first():
    runs = parse_runs(load_fixture(RUNS))

    assert len(runs) >= 4, "a day of CH1 runs is eight"
    assert runs == sorted(runs, reverse=True)
    assert all(run.tzinfo is not None and run.hour % 3 == 0 for run in runs)


def test_a_message_search_yields_one_grib_href():
    href = parse_href(load_fixture(MESSAGE))

    assert href is not None
    assert "t_2m-ctrl.grib2" in href


def test_an_unpublished_step_is_none_not_an_error():
    assert parse_href({"type": "FeatureCollection", "features": []}) is None


def test_the_collection_lists_its_grid_constants():
    assert "horizontal_constants_icon-ch1-eps.grib2" in parse_constants_href(load_fixture(COLLECTION), ICON_CH1)

    with pytest.raises(SourceUnavailable, match="horizontal_constants"):
        parse_constants_href({"assets": {}}, ICON_CH1)


def test_horizons_are_spelled_the_way_stac_filters_them():
    assert horizon_iso(0) == "P0DT00H00M00S"
    assert horizon_iso(3) == "P0DT03H00M00S"
    assert horizon_iso(27) == "P1DT03H00M00S"


def test_a_message_search_asks_for_the_control_run():
    body = message_search(ICON_CH1, datetime(2026, 9, 16, 12, tzinfo=UTC), "VMAX_10M", 5)

    assert body["forecast:reference_datetime"] == "2026-09-16T12:00:00Z"
    assert body["forecast:perturbed"] is False
    assert body["forecast:horizon"] == "P0DT05H00M00S"


# --- Time and model choice -------------------------------------------------------------------


def test_local_minutes_become_utc_on_either_side_of_a_clock_change():
    assert target_time(11 * 60, date(2026, 9, 17)) == datetime(2026, 9, 17, 9, tzinfo=UTC)
    assert target_time(11 * 60, date(2026, 12, 17)) == datetime(2026, 12, 17, 10, tzinfo=UTC)
    # Floored: 11:40 is the 11:00 forecast.
    assert target_time(11 * 60 + 40, date(2026, 9, 17)) == datetime(2026, 9, 17, 9, tzinfo=UTC)


def test_the_finest_model_that_reaches_is_chosen():
    now = datetime(2026, 9, 16, 17, tzinfo=UTC)

    assert model_for(now + timedelta(hours=20), now) is ICON_CH1
    assert model_for(now - timedelta(hours=5), now) is ICON_CH1
    assert model_for(now + timedelta(hours=60), now) is ICON_CH2
    with pytest.raises(SourceUnavailable, match="horizon"):
        model_for(now + timedelta(days=6), now)


# --- Arithmetic ------------------------------------------------------------------------------


def test_nearest_cell_accounts_for_longitude_shrinking_with_latitude():
    # Cell 0 is 0.010° of latitude away (1.1 km); cell 1 is 0.012° of longitude away, which at
    # 46.5° N is only 0.92 km. Comparing raw degrees would pick the wrong one.
    lats = [46.4988, 46.4888]
    lons = [7.7717, 7.7837]

    assert nearest_cell(lats, lons, 46.4888, 7.7717) == 1


def test_precipitation_is_the_hour_s_share_of_the_accumulation():
    assert hourly_precip(5.5, 3.0) == pytest.approx(2.5)
    assert hourly_precip(3.0, 3.0000001) == 0.0
    assert hourly_precip(3.0, None) is None


def test_assemble_converts_units_and_carries_temperature_to_the_stop():
    forecast = assemble(
        "ICON-CH1 2026-09-16T06:00Z",
        11 * 60 + 20,
        {
            "T_2M": 278.15,  # 5 °C at the model's terrain
            "TD_2M": 273.15,
            "U_10M": 3.0,
            "V_10M": 4.0,
            "VMAX_10M": 15.0,
            "TOT_PREC": 4.0,
            "TOT_PREC_PREV": 3.5,
            "HZEROCL": 3200.0,
        },
        model_elevation_m=2378.0,
        elevation_m=2778.0,
    )

    assert forecast.hour == 11 * 60
    # 400 m higher than the model thinks: 2.6 K colder.
    assert forecast.temp_c == pytest.approx(5 - 2.6)
    assert forecast.wind_kmh == pytest.approx(18.0)
    assert forecast.gust_kmh == pytest.approx(54.0)
    assert forecast.precip_mm == pytest.approx(0.5)
    assert forecast.freezing_level_m == 3200.0
    assert forecast.cloud_base_m is None
    assert forecast.model_elevation_m == 2378.0


# --- The source, end to end ------------------------------------------------------------------


class FakeDecoder:
    """Three cells; the middle one is Hohtürli. Each variable's value there says what it is.

    Values come back as float32, as the real decoder's do, so comparisons need a tolerance.
    """

    VALUES = {
        "t_2m": 275.15,
        "td_2m": 270.15,
        "u_10m": 6.0,
        "v_10m": 8.0,
        "vmax_10m": 20.0,
        "hzerocl": 3100.0,
        "snowlmt": 2900.0,
        # ICON's missing value: no ceiling to report.
        "ceiling": 9999.0,
        "cape_ml": 120.0,
    }

    def __init__(self) -> None:
        self.decoded: list[str] = []

    def values(self, path):
        variable, steps = path.stem.rsplit("-", 1)
        self.decoded.append(path.name)
        # TOT_PREC accumulates 1.5 mm per hour of the run.
        value = 1.5 * int(steps) if variable == "tot_prec" else self.VALUES[variable]
        return np.array([0.0, value, 0.0], dtype=np.float32)

    def grid(self, path):
        return Grid(
            lats=np.array([47.0, 46.4889, 46.0]),
            lons=np.array([8.0, 7.7716, 7.0]),
            surface_m=np.array([500.0, 2778.0, 900.0]),
        )


def stac_handler(runs: list[datetime], missing: set[tuple[str, str]] = frozenset()):
    """A STAC API and object store. `missing` holds (run iso, variable) pairs not yet published."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        url = str(request.url)
        if url.endswith("/search"):
            body = json.loads(request.content)
            if "forecast:reference_datetime" not in body:
                features = [
                    {"properties": {"forecast:reference_datetime": f"{run:%Y-%m-%dT%H:%M:%SZ}"}} for run in runs
                ]
                return httpx.Response(200, json={"features": features})
            run, variable = body["forecast:reference_datetime"], body["forecast:variable"]
            if (run, variable) in missing:
                return httpx.Response(200, json={"features": []})
            href = f"https://objects.example/{run}/{variable.lower()}.grib2"
            asset = {"type": "application/grib", "href": href}
            return httpx.Response(200, json={"features": [{"assets": {"a": asset}}]})
        if "/collections/" in url:
            href = "https://objects.example/horizontal_constants_icon-ch1-eps.grib2"
            return httpx.Response(200, json={"assets": {"horizontal_constants_icon-ch1-eps.grib2": {"href": href}}})
        if url.startswith("https://objects.example/"):
            return httpx.Response(200, content=b"GRIB-bytes")
        raise AssertionError(f"unexpected request {url}")

    return httpx.MockTransport(handler), requests


def soon() -> tuple[date, int, datetime]:
    """Six hours from now, as the API would ask for it: well inside ICON-CH1 whenever this runs."""
    local = datetime.now(SWISS_TIME) + timedelta(hours=6)
    return local.date(), local.hour * 60, target_time(local.hour * 60, local.date())


def recent_runs(target: datetime) -> list[datetime]:
    """Two CH1 runs that both reach `target`, three hours apart."""
    newest = (target - timedelta(hours=8)).replace(minute=0, second=0, microsecond=0)
    newest -= timedelta(hours=newest.hour % 3)
    return [newest, newest - timedelta(hours=3)]


class FakeSpread:
    async def ensemble_at(self, point, hour, day):
        return {"gust_kmh_p10": 50.0, "gust_kmh_p90": 90.0, "thunder_probability": 0.2}


async def test_the_source_reads_the_stop_s_cell_from_the_newest_run(settings):
    day, hour, target = soon()
    runs = recent_runs(target)
    transport, _ = stac_handler(runs)
    decoder = FakeDecoder()
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport), decoder=decoder)

    forecast = await source.forecast_at(HOHTURLI, hour, day)

    assert forecast.model_run == f"ICON-CH1 {runs[0]:%Y-%m-%dT%H:%M}Z"
    assert forecast.temp_c == pytest.approx(2.0, abs=1e-4)
    assert forecast.wind_kmh == pytest.approx(36.0, abs=1e-4)
    assert forecast.gust_kmh == pytest.approx(72.0, abs=1e-4)
    assert forecast.precip_mm == pytest.approx(1.5, abs=1e-4)
    assert forecast.snowline_m == 2900.0
    assert forecast.cloud_base_m is None, "9999 is ICON's missing value, not a cloud base"
    assert forecast.model_elevation_m == 2778.0
    assert not forecast.has_spread, "no spread source was given"


async def test_a_run_still_publishing_falls_back_to_the_one_before(settings):
    day, hour, target = soon()
    runs = recent_runs(target)
    transport, _ = stac_handler(runs, missing={(f"{runs[0]:%Y-%m-%dT%H:%M:%SZ}", "CEILING")})
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport), decoder=FakeDecoder())

    forecast = await source.forecast_at(HOHTURLI, hour, day)

    assert forecast.model_run == f"ICON-CH1 {runs[1]:%Y-%m-%dT%H:%M}Z"


async def test_a_second_request_for_the_same_stop_and_hour_downloads_nothing(settings):
    day, hour, target = soon()
    transport, requests = stac_handler(recent_runs(target))
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport), decoder=FakeDecoder())

    await source.forecast_at(HOHTURLI, hour, day)
    before = len(requests)
    await source.forecast_at(HOHTURLI, hour + 30, day)

    assert len(requests) == before


async def test_one_download_per_variable_serves_every_stop(settings):
    day, hour, target = soon()
    transport, requests = stac_handler(recent_runs(target))
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport), decoder=FakeDecoder())

    await source.forecast_at(HOHTURLI, hour, day)
    await source.forecast_at(GeoPoint(46.49, 7.77, 2600), hour, day)

    downloads = [r for r in requests if str(r.url).startswith("https://objects.example/2")]
    # Ten variables, plus the previous hour's precipitation accumulation.
    assert len(downloads) == len(GRIB_VARIABLES) + 1


async def test_spread_is_merged_from_the_ensemble_source(settings):
    day, hour, target = soon()
    transport, _ = stac_handler(recent_runs(target))
    source = IconGribSource(
        settings, CachedHttpClient(settings, transport=transport), spread=FakeSpread(), decoder=FakeDecoder()
    )

    forecast = await source.forecast_at(HOHTURLI, hour, day)

    assert forecast.gust_kmh_p90 == 90.0
    assert forecast.thunder_probability == 0.2
    assert forecast.gust_kmh == pytest.approx(72.0, abs=1e-4), "the control run is still the value"


async def test_superseded_runs_are_deleted_from_disk(settings):
    day, hour, target = soon()
    runs = recent_runs(target)
    stale = settings.grib_dir / "icon-ch1" / "20200101T0000Z"
    stale.mkdir(parents=True)
    (stale / "t_2m-3.grib2").write_bytes(b"old")
    transport, _ = stac_handler(runs)
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport), decoder=FakeDecoder())

    await source.forecast_at(HOHTURLI, hour, day)

    assert not stale.exists()
    assert (settings.grib_dir / "icon-ch1" / "horizontal_constants.grib2").is_file(), "constants are kept"


async def test_latest_run_is_the_newest_stac_lists(settings):
    day, hour, target = soon()
    runs = recent_runs(target)
    transport, _ = stac_handler(runs)
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport), decoder=FakeDecoder())

    run = await source.latest_run(day)

    assert run.reference_time == runs[0]
    assert run.model == "ICON-CH1"


async def test_without_eccodes_the_source_names_the_fallback(settings, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_eccodes(name, *args, **kwargs):
        if name == "eccodes":
            raise ImportError("No module named 'eccodes'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_eccodes)
    day, hour, target = soon()
    transport, _ = stac_handler(recent_runs(target))
    source = IconGribSource(settings, CachedHttpClient(settings, transport=transport))

    with pytest.raises(SourceUnavailable, match="WEATHER_SOURCE=open-meteo"):
        await source.forecast_at(HOHTURLI, hour, day)


async def test_real_eccodes_decodes_a_live_message(settings, recording):
    """The only test that touches eccodes and the real grid. Needs `--record` and `uv sync --group grib`."""
    if not recording:
        pytest.skip("downloads ~40 MB of GRIB: run `pytest --record`")
    pytest.importorskip("eccodes")
    from app.sources.openmeteo import OpenMeteoIconSource

    async with CachedHttpClient(settings) as client:
        source = IconGribSource(settings, client, spread=OpenMeteoIconSource(settings, client))
        local = datetime.now(SWISS_TIME) + timedelta(hours=3)
        forecast = await source.forecast_at(HOHTURLI, local.hour * 60, local.date())

    assert -30 < forecast.temp_c < 30
    assert 0 <= forecast.gust_kmh < 250
    assert forecast.model_elevation_m is None or 1500 < forecast.model_elevation_m < 3500
    assert forecast.has_spread
