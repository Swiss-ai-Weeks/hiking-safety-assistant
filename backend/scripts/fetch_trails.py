"""Download the swissTLM3D Wanderwege GeoPackage: the official Swiss hiking network.

Deliberately *not* routed through `CachedHttpClient`. That layer caches parsed JSON bodies keyed
by model run and coordinate; a 190 MB binary that changes a few times a year has nothing in
common with it. This is a one-off, streamed to disk, resolved through the STAC API so the URL
and the checksum come from swisstopo rather than from a constant in this file.

    uv run --directory backend python -m scripts.fetch_trails [--force]
"""

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

import httpx

from app.config import get_settings

COLLECTION = "ch.swisstopo.swisstlm3d-wanderwege"
ITEM = "swisstlm3d-wanderwege"
ASSET_SUFFIX = ".gpkg.zip"

# STAC publishes a multihash: 0x12 = sha256, 0x20 = 32 bytes, then the digest.
MULTIHASH_SHA256_PREFIX = "1220"


def asset_url_and_checksum(stac_base_url: str) -> tuple[str, str | None]:
    """Ask STAC where the GeoPackage is, rather than hardcoding a URL that will move."""
    url = f"{stac_base_url}/collections/{COLLECTION}/items/{ITEM}"
    item = httpx.get(url, timeout=30.0, follow_redirects=True).raise_for_status().json()

    for name, asset in item.get("assets", {}).items():
        if not name.endswith(ASSET_SUFFIX):
            continue
        checksum = asset.get("file:checksum", "")
        expected = None
        if checksum.lower().startswith(MULTIHASH_SHA256_PREFIX):
            expected = checksum[len(MULTIHASH_SHA256_PREFIX) :].lower()
        return asset["href"], expected

    raise SystemExit(f"no {ASSET_SUFFIX} asset in {url}")


def download(url: str, dest: Path) -> str:
    """Stream to a temporary file, return the sha256. Renamed only once it is whole."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    digest = hashlib.sha256()
    written = 0

    with httpx.stream("GET", url, timeout=60.0, follow_redirects=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        with tmp.open("wb") as out:
            for chunk in response.iter_bytes(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                if total:
                    print(f"\r  {written / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", file=sys.stderr)
    print(file=sys.stderr)

    tmp.replace(dest)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if the file is already there")
    args = parser.parse_args()

    settings = get_settings()
    dest = settings.trails_db.parent / f"{ITEM}{ASSET_SUFFIX}"

    if dest.exists() and not args.force:
        print(f"{dest} already exists ({dest.stat().st_size / 1e6:,.0f} MB); --force to replace it")
        return 0

    url, expected = asset_url_and_checksum(settings.stac_base_url)
    print(f"downloading {url}")
    actual = download(url, dest)

    if expected and actual != expected:
        # Truncated or corrupted: importing it would fail obscurely much later.
        dest.unlink(missing_ok=True)
        raise SystemExit(f"checksum mismatch: expected {expected}, got {actual}")
    if not zipfile.is_zipfile(dest):
        dest.unlink(missing_ok=True)
        raise SystemExit(f"{dest} is not a zip archive")

    print(f"{dest} ({dest.stat().st_size / 1e6:,.0f} MB), checksum {'verified' if expected else 'not published'}")
    print("next: uv run --directory backend python -m scripts.import_trails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
