import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


def test_defaults_to_demo():
    settings = Settings()

    assert settings.source_mode == "demo"
    # Nothing needs a key today; adding one must stay configuration rather than code.
    assert settings.open_meteo_api_key is None


def test_a_forecast_expires_sooner_than_a_geometry():
    settings = Settings()

    assert settings.cache_ttl_forecast_s < settings.cache_ttl_search_s < settings.cache_ttl_route_s


def test_environment_overrides_and_live_is_selectable(monkeypatch, tmp_path):
    monkeypatch.setenv("SOURCE_MODE", "live")
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("HTTP_ATTEMPTS", "5")
    get_settings.cache_clear()
    try:
        settings = get_settings()

        assert settings.source_mode == "live"
        assert settings.cache_dir == tmp_path
        assert settings.http_attempts == 5
    finally:
        get_settings.cache_clear()


def test_an_unknown_mode_is_rejected():
    with pytest.raises(ValidationError):
        Settings(source_mode="offline")
