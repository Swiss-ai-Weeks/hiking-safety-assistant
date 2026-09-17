"""The passages in `corpus/`, parsed once.

Each file is a short paraphrase with a header block. The header is deliberately not YAML — four
`key: value` lines and two comma-separated lists do not justify a dependency:

    ---
    title: SAC Mountain and Alpine Hiking Scale — alpine hiking
    cite: SAC hiking scale
    publisher: Swiss Alpine Club SAC
    url: https://…
    kinds: gusts, showers
    grades: T4
    ---
    The passage itself.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..models import Grade, HazardKind

CORPUS_DIR = Path(__file__).parent / "corpus"
REQUIRED = ("title", "cite", "publisher", "url", "kinds", "grades")


@dataclass(frozen=True, slots=True)
class Passage:
    id: str
    title: str
    # The short form a provenance footnote quotes.
    cite: str
    publisher: str
    url: str
    kinds: frozenset[HazardKind]
    grades: frozenset[Grade]
    text: str


def parse_passage(passage_id: str, raw: str) -> Passage:
    _, header, body = raw.split("---\n", 2)
    fields: dict[str, str] = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    missing = [key for key in REQUIRED if not fields.get(key)]
    if missing:
        raise ValueError(f"guidance passage {passage_id} is missing {', '.join(missing)}")

    def items(key: str) -> frozenset:
        return frozenset(item.strip() for item in fields[key].split(",") if item.strip())

    return Passage(
        id=passage_id,
        title=fields["title"],
        cite=fields["cite"],
        publisher=fields["publisher"],
        url=fields["url"],
        kinds=items("kinds"),
        grades=items("grades"),
        # Unwrapped: the files are wrapped for reading, a prompt wants one paragraph.
        text=" ".join(body.split()),
    )


@lru_cache
def load_corpus() -> tuple[Passage, ...]:
    return tuple(
        parse_passage(path.stem, path.read_text(encoding="utf-8")) for path in sorted(CORPUS_DIR.glob("*.md"))
    )
