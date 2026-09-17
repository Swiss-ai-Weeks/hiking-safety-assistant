"""A small curated corpus of alpine safety guidance, and retrieval over it.

What the hazard copy is grounded in: SAC grade definitions, Suisse Rando and SAC safety advice,
MeteoSwiss and federal warning semantics. Every passage is a short paraphrase in our own words with
the page it paraphrases, so a citation always points at something a hiker can read in full.

Pure, like `hazards/` and `routing/`: the corpus ships with the package and nothing here fetches.
"""

from .cite import citations_for
from .corpus import Passage, load_corpus
from .retrieve import search

__all__ = ["Passage", "citations_for", "load_corpus", "search"]
