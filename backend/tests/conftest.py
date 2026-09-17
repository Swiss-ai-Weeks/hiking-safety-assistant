"""Offline by default. `pytest --record` is the only thing here that touches the network."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"

# A deployed checkout has a `backend/.env` (live mode, a model endpoint). The suite asserts on the
# defaults, so it must not see it. Explicit environment variables still apply, as `--record` needs.
Settings.model_config["env_file"] = None


def pytest_addoption(parser):
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Re-record fixtures from the live sources. Needs egress; plain pytest never does.",
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def recording(request) -> bool:
    return bool(request.config.getoption("--record"))


def load_fixture(name: str) -> Any:
    """A recorded response body, replayed offline."""
    path = FIXTURES / f"{name}.json"
    if not path.is_file():
        raise AssertionError(f"missing fixture {path.name}; record it with `pytest --record`")
    return json.loads(path.read_text(encoding="utf-8"))


def save_fixture(name: str, body: Any) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    (FIXTURES / f"{name}.json").write_text(text, encoding="utf-8")


def replay(name: str, *, status: int = 200) -> httpx.MockTransport:
    """A transport that answers every request with a recorded body."""
    body = load_fixture(name)
    return httpx.MockTransport(lambda _request: httpx.Response(status, json=body))


def replay_by_url(routes: dict[str, str]) -> httpx.MockTransport:
    """Replay several recorded services at once, chosen by what is in the URL.

    A route request fans out to swissALTI3D, Overpass and swissnames3d, and `replay` answers every
    request with the same body. Keys are matched against the full URL, so "profile.json" and
    "overpass" are enough to tell the three apart.
    """
    bodies = {fragment: load_fixture(name) for fragment, name in routes.items()}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for fragment, body in bodies.items():
            if fragment in url:
                return httpx.Response(200, json=body)
        raise AssertionError(f"no fixture for {url}; add one to `replay_by_url`")

    return httpx.MockTransport(handler)


def responses(*staged: httpx.Response) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """A transport that returns `staged` in order, then repeats the last. Records what it saw."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return staged[min(len(seen) - 1, len(staged) - 1)]

    return httpx.MockTransport(handler), seen


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Test settings: cache in a tmp dir, no backoff, so nothing sleeps or persists."""
    return Settings(
        source_mode="demo",
        cache_dir=tmp_path / "cache",
        http_backoff_s=0.0,
        http_attempts=3,
    )
