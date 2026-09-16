"""ICON over Open-Meteo, against a recorded forecast, ensemble and run metadata at Hohtürli."""

from datetime import date, timedelta

import httpx
import pytest
from conftest import load_fixture, replay_by_url, save_fixture

from app.domain import GeoPoint
from app.errors import SourceUnavailable
from app.sources.http import CachedHttpClient
from app.sources.openmeteo import OpenMeteoIconSource, parse_ensemble, parse_forecast, parse_meta
from app.sources.weather_common import ICON_CH1, local_today

pytestmark = pytest.mark.anyio

HOHTURLI = GeoPoint(46.4888, 7.7717, 2778)
FORECAST = "openmeteo_ch1_hohturli"
ENSEMBLE = "openmeteo_ensemble_ch1_hohturli"
META = "openmeteo_meta_ch1"
FIXTURES = {"meta.json": META, "ensemble-api": ENSEMBLE, "/forecast": FORECAST}
ELEVEN = 11 * 60


def fixture_day() -> date:
    """The day the fixture was recorded for. Tests ask for that day, so they never go stale."""
    return date.fromisoformat(load_fixture(FORECAST)["hourly"]["time"][0][:10])


def source_with(settings, transport: httpx.BaseTransport) -> OpenMeteoIconSource:
    return OpenMeteoIconSource(settings, CachedHttpClient(settings, transport=transport))


async def test_record_openmeteo_fixtures(settings, recording):
    """`pytest --record` refreshes all three fixtures, for tomorrow. Plain pytest skips."""
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    day = local_today() + timedelta(days=1)
    async with CachedHttpClient(settings) as client:
        source = OpenMeteoIconSource(settings, client)
        http = client._connection()
        meta = (await http.get(source.meta_url(ICON_CH1))).raise_for_status().json()
        forecast = (
            await http.get(
                f"{settings.open_meteo_base_url}/forecast", params=source.forecast_params(ICON_CH1, HOHTURLI, day)
            )
        ).raise_for_status().json()
        ensemble = (
            await http.get(
                f"{settings.open_meteo_ensemble_url}/ensemble",
                params=source.ensemble_params(ICON_CH1, HOHTURLI, day),
            )
        ).raise_for_status().json()
    assert parse_forecast(forecast, day, ELEVEN, "x").temp_c is not None, "live forecast carried no temperature"
    assert parse_ensemble(ensemble, day, ELEVEN)["gust_kmh_p90"] is not None, "live ensemble carried no members"
    save_fixture(META, meta)
    save_fixture(FORECAST, forecast)
    save_fixture(ENSEMBLE, ensemble)


async def test_forecast_parses_fixture(settings):
    source = source_with(settings, replay_by_url(FIXTURES))

    forecast = await source.forecast_at(HOHTURLI, ELEVEN, fixture_day())

    assert forecast.model_run.startswith("ICON-CH1 ")
    assert forecast.hour == ELEVEN
    # September at 2 778 m: somewhere between a hard frost and a warm afternoon.
    assert -15 < forecast.temp_c < 20
    assert forecast.dewpoint_c <= forecast.temp_c + 0.5
    assert 0 <= forecast.wind_kmh <= forecast.gust_kmh
    assert forecast.precip_mm >= 0
    assert 1000 < forecast.freezing_level_m < 6000


async def test_ensemble_spread_brackets_the_control_run(settings):
    source = source_with(settings, replay_by_url(FIXTURES))

    forecast = await source.forecast_at(HOHTURLI, ELEVEN, fixture_day())

    assert forecast.has_spread
    assert forecast.gust_kmh_p10 <= forecast.gust_kmh_p90
    assert forecast.precip_mm_p10 <= forecast.precip_mm_p90
    assert 0 <= forecast.thunder_probability <= 1


async def test_a_minute_inside_the_hour_reads_that_hour(settings):
    source = source_with(settings, replay_by_url(FIXTURES))

    at_eleven = await source.forecast_at(HOHTURLI, ELEVEN, fixture_day())
    at_eleven_forty = await source.forecast_at(HOHTURLI, ELEVEN + 40, fixture_day())

    assert at_eleven == at_eleven_forty


async def test_every_hour_of_a_stop_is_one_request(settings):
    seen: list[str] = []
    inner = replay_by_url(FIXTURES)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return inner.handle_request(request)

    source = source_with(settings, httpx.MockTransport(handler))
    for hour in range(8, 16):
        await source.forecast_at(HOHTURLI, hour * 60, fixture_day())

    assert sum("/forecast" in url for url in seen) == 1
    assert sum("ensemble-api" in url for url in seen) == 1
    assert sum("meta.json" in url for url in seen) == 1


async def test_the_query_carries_the_stop_elevation_and_the_model(settings):
    seen: list[httpx.Request] = []
    inner = replay_by_url(FIXTURES)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return inner.handle_request(request)

    await source_with(settings, httpx.MockTransport(handler)).forecast_at(HOHTURLI, ELEVEN, fixture_day())

    forecast = next(r for r in seen if "/forecast" in str(r.url))
    assert forecast.url.params["elevation"] == "2778"
    assert forecast.url.params["models"] == "meteoswiss_icon_ch1"
    assert forecast.url.params["timezone"] == "Europe/Zurich"


async def test_a_failed_ensemble_still_returns_the_control_run(settings):
    meta, body = load_fixture(META), load_fixture(FORECAST)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "ensemble-api" in url:
            return httpx.Response(503)
        return httpx.Response(200, json=meta if "meta.json" in url else body)

    forecast = await source_with(settings, httpx.MockTransport(handler)).forecast_at(
        HOHTURLI, ELEVEN, fixture_day()
    )

    assert forecast.temp_c is not None
    assert not forecast.has_spread
    assert forecast.thunder_probability is None


async def test_a_rejected_request_is_unavailable_not_a_crash(settings):
    meta = load_fixture(META)

    def handler(request: httpx.Request) -> httpx.Response:
        if "meta.json" in str(request.url):
            return httpx.Response(200, json=meta)
        return httpx.Response(400, json={"error": True, "reason": "Latitude must be in range"})

    with pytest.raises(SourceUnavailable, match="HTTP 400"):
        await source_with(settings, httpx.MockTransport(handler)).forecast_at(HOHTURLI, ELEVEN, fixture_day())


async def test_latest_run_is_the_initialisation_time(settings):
    run = await source_with(settings, replay_by_url(FIXTURES)).latest_run(fixture_day())

    assert run.model == "ICON-CH1"
    assert run.horizon_h == 33
    assert run.reference_time.hour % 3 == 0, "ICON-CH1 runs every three hours"
    assert run.label == f"ICON-CH1 {run.reference_time:%Y-%m-%dT%H:%M}Z"


def test_an_hour_outside_the_series_is_a_gap():
    with pytest.raises(SourceUnavailable, match="no forecast for"):
        parse_forecast(load_fixture(FORECAST), fixture_day() + timedelta(days=3), ELEVEN, "x")


def test_nulls_stay_unknown_rather_than_zero():
    payload = {"hourly": {"time": ["2026-09-17T11:00"], "temperature_2m": [None], "wind_gusts_10m": [42.0]}}

    forecast = parse_forecast(payload, date(2026, 9, 17), ELEVEN, "x")

    assert forecast.temp_c is None
    assert forecast.gust_kmh == 42.0
    assert forecast.cloud_base_m is None


def test_thunder_probability_counts_members_over_the_cape_threshold():
    hourly = {"time": ["2026-09-17T11:00"], "wind_gusts_10m": [30.0], "cape": [800.0]}
    for member in range(1, 11):
        hourly[f"wind_gusts_10m_member{member:02d}"] = [30.0 + member]
        hourly[f"cape_member{member:02d}"] = [900.0 if member <= 4 else 50.0]

    spread = parse_ensemble({"hourly": hourly}, date(2026, 9, 17), ELEVEN)

    # Control plus members 1-4 are over 500 J/kg: five of eleven.
    assert spread["thunder_probability"] == pytest.approx(5 / 11)
    assert 30 < spread["gust_kmh_p10"] < spread["gust_kmh_p90"] < 41
    assert spread["precip_mm_p90"] is None


def test_metadata_without_a_run_time_is_unavailable():
    with pytest.raises(SourceUnavailable, match="last_run_initialisation_time"):
        parse_meta({"data_end_time": 1}, ICON_CH1)
