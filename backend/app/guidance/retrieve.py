"""BM25 over the corpus, with the passage tags as a boost.

Eighteen passages do not need embeddings. What they need is to be found by the hazard they are
about: a passage tagged with the hazard's kind and the grade of the ground it is on outranks one
that only shares words with the query. Lexical scoring then orders passages within that, and is
deterministic, so a citation does not change between two requests for the same hazard.
"""

import math
import re
from collections import Counter
from functools import lru_cache

from ..models import Grade, HazardKind
from .corpus import Passage, load_corpus

# The usual BM25 constants.
K1 = 1.5
B = 0.75
# A matching tag is worth more than any plausible lexical score on a corpus this size, and a
# passage about one thing more than a passage that touches on everything: the boost is shared out
# across a passage's tags, on top of a floor every match gets.
KIND_BOOST = 8.0
KIND_SPECIFIC_BOOST = 8.0
GRADE_BOOST = 4.0
GRADE_SPECIFIC_BOOST = 4.0

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOPWORDS = frozenset(
    "a an and are as at be by can for from has in into is it its of on or so that the their them they this to "
    "up was with where which when what who you your le la les de des du et en un une au aux".split()
)


def tokens(text: str) -> list[str]:
    return [word for word in (w.lower() for w in _WORD.findall(text)) if word not in _STOPWORDS]


class _Index:
    def __init__(self, passages: tuple[Passage, ...]) -> None:
        self.passages = passages
        self.docs = [Counter(tokens(f"{p.title} {p.text}")) for p in passages]
        self.lengths = [sum(doc.values()) for doc in self.docs]
        self.avg_length = sum(self.lengths) / max(len(self.lengths), 1)
        frequency = Counter(term for doc in self.docs for term in doc)
        n = len(passages)
        self.idf = {term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in frequency.items()}

    def bm25(self, i: int, query: list[str]) -> float:
        doc, length = self.docs[i], self.lengths[i]
        score = 0.0
        for term in query:
            tf = doc.get(term, 0)
            if tf:
                score += self.idf[term] * tf * (K1 + 1) / (tf + K1 * (1 - B + B * length / self.avg_length))
        return score


@lru_cache
def _index() -> _Index:
    return _Index(load_corpus())


def search(query: str, kind: HazardKind | None = None, grade: Grade | None = None, k: int = 3) -> list[Passage]:
    """The `k` best passages for `query`, preferring those tagged with `kind` and `grade`.

    A passage with no lexical match and no matching tag is never returned: an empty result is more
    honest than a citation that has nothing to do with the question.
    """
    index = _index()
    words = tokens(query)
    scored = []
    for i, passage in enumerate(index.passages):
        score = index.bm25(i, words)
        if kind is not None and kind in passage.kinds:
            score += KIND_BOOST + KIND_SPECIFIC_BOOST / len(passage.kinds)
        if grade is not None and grade in passage.grades:
            score += GRADE_BOOST + GRADE_SPECIFIC_BOOST / len(passage.grades)
        if score > 0:
            scored.append((score, passage.id, passage))
    # Ties break on id, so the order never depends on the file system.
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [passage for _, _, passage in scored[:k]]
