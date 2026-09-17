"""Answering a hiker's questions about one route on one day, with a language model that decides nothing.

Pure, like `narration/`: the briefing the model reads, the prompt, and the guard its answer must pass.
The one piece that calls out is `sources/asker.py`.
"""

from .briefing import Briefing, build_briefing
from .guard import fill, violations
from .prompt import ASK_PROMPT_VERSION, build_correction, build_messages, parse_answer

__all__ = [
    "ASK_PROMPT_VERSION",
    "Briefing",
    "build_briefing",
    "build_correction",
    "build_messages",
    "fill",
    "parse_answer",
    "violations",
]
