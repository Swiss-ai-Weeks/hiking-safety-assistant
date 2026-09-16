"""MeteoSwiss warnings from the app feed, against a recorded postcode lookup and plzDetail."""

import httpx
import pytest
from conftest import load_fixture, replay_by_url, save_fixture

from app.domain import GeoPoint
from app.errors import SourceUnavailable
from app.sources.http import CachedHttpClient
from app.sources.warnings_app import (
    IDENTIFY_PATH,
    AppWarningSource,
    parse_plz,
    parse_warnings,
)

pytestmark = pytest.mark.anyio

OESCHINENSEE = GeoPoint(46.49836, 7.72667)
IDENTIFY = "geoadmin_identify_plz_oeschinensee"
PLZ_DETAIL = "meteoswiss_app_plz_371800"
FIXTURES = {"MapServer/identify": IDENTIFY, "plzDetail": PLZ_DETAIL}


@pytest.fixture
def enabled(settings):
    return settings.model_copy(update={"meteoswiss_app_warnings": True})


def source_with(settings, transport: httpx.BaseTransport) -> AppWarningSource:
    return AppWarningSource(settings, CachedHttpClient(settings, transport=transport))


async def test_record_warning_fixtures(enabled, recording):
    """`pytest --record` refreshes both fixtures. Plain pytest skips."""
    if not recording:
        pytest.skip("offline: run `pytest --record` to refresh the fixture")
    async with CachedHttpClient(enabled) as client:
        http = client._connection()
        identify = (
            await http.get(
                enabled.geoadmin_base_url + IDENTIFY_PATH, params=AppWarningSource.identify_params(OESCHINENSEE)
            )
        ).raise_for_status().json()
        plz = parse_plz(identify)
        assert plz == 3718, f"Oeschinensee should be in Kandersteg's postcode, got {plz}"
        detail = (
            await http.get(f"{enabled.meteoswiss_app_url}/plzDetail", params=AppWarningSource.plz_params(plz))
        ).raise_for_status().json()
    parse_warnings(detail)
    save_fixture(IDENTIFY, identify)
    save_fixture(PLZ_DETAIL, detail)


async def test_warnings_parse_fixture(enabled):
    source = source_with(enabled, replay_by_url(FIXTURES))

    warnings = await source.warnings_for([OESCHINENSEE])

    # Whatever MeteoSwiss had issued when this was recorded; the shape is what is under test.
    assert warnings == parse_warnings(load_fixture(PLZ_DETAIL))
    assert all(not warning.official for warning in warnings), "the app feed is never official data"


async def test_the_route_is_mapped_to_its_postcode(enabled):
    seen: list[httpx.Request] = []
    inner = replay_by_url(FIXTURES)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return inner.handle_request(request)

    await source_with(enabled, httpx.MockTransport(handler)).warnings_for([OESCHINENSEE])

    detail = next(r for r in seen if "plzDetail" in str(r.url))
    assert detail.url.params["plz"] == "371800"
    identify = next(r for r in seen if "identify" in str(r.url))
    assert identify.url.params["sr"] == "2056", "identify silently returns nothing for WGS84"


async def test_off_by_default_is_a_gap_not_an_all_clear(settings):
    source = source_with(settings, replay_by_url(FIXTURES))

    with pytest.raises(SourceUnavailable, match="METEOSWISS_APP_WARNINGS"):
        await source.warnings_for([OESCHINENSEE])


async def test_a_warning_shared_by_neighbouring_postcodes_is_reported_once(enabled):
    warning = {"warnType": 0, "warnLevel": 3, "regionId": 305, "validFrom": 1789553146000, "text": "Wind"}
    postcodes = iter([3718, 3713])

    def handler(request: httpx.Request) -> httpx.Response:
        if "identify" in str(request.url):
            return httpx.Response(200, json={"results": [{"attributes": {"plz": next(postcodes)}}]})
        return httpx.Response(200, json={"warnings": [warning]})

    warnings = await source_with(enabled, httpx.MockTransport(handler)).warnings_for(
        [OESCHINENSEE, GeoPoint(46.4888, 7.7717)]
    )

    assert len(warnings) == 1
    assert warnings[0].kind == "wind"
    assert warnings[0].level == 3


async def test_a_route_outside_switzerland_is_unavailable(enabled):
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"results": []}))

    with pytest.raises(SourceUnavailable, match="postcode"):
        await source_with(enabled, transport).warnings_for([GeoPoint(45.0, 7.0)])


def test_an_unknown_warning_type_is_kept_as_other():
    warnings = parse_warnings(
        {"warnings": [{"warnType": 99, "warnLevel": 2, "text": "?", "outlook": True, "validTo": 1789600000000}]}
    )

    assert warnings[0].kind == "other"
    assert warnings[0].outlook
    assert warnings[0].valid_from is None
    assert warnings[0].valid_to.year == 2026


def test_forest_fire_is_type_ten():
    """The one code confirmed against a live response."""
    fire = parse_warnings({"warnings": [{"warnType": 10, "warnLevel": 2}]})

    assert fire[0].kind == "forest-fire"


def test_a_response_without_warnings_is_unavailable():
    with pytest.raises(SourceUnavailable, match="warnings"):
        parse_warnings({"currentWeather": {}})
