"""The OpenAPI schema as text, for `pnpm gen:api` and the snapshot test that guards it.

Run as `python -m app.openapi_dump`.
"""

import json
from pathlib import Path
from typing import Any

from .main import create_app

# A dist dir that cannot exist: the dump must not depend on whether the frontend happens to be
# built. (The SPA catch-all is `include_in_schema=False`, but the dump shouldn't rely on that.)
NO_FRONTEND = Path("/nonexistent-frontend-dist")


def openapi_schema() -> dict[str, Any]:
    return create_app(frontend_dist=NO_FRONTEND).openapi()


def openapi_json() -> str:
    return json.dumps(openapi_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    print(openapi_json(), end="")
