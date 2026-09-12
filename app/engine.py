"""linker_extraction engine setup: stanza dependency parsing + rule-based
scoring + compiled linker/intro patterns. Heavy, one-time initialization
that runs when this module is first imported."""

import os
import sys

from .config import INTRO_CSV, LINKERS_CSV, PROJECT_ROOT

sys.path.insert(0, os.path.join(PROJECT_ROOT, "linker_extraction"))

import stanza  # noqa: E402
from extract import load_patterns  # noqa: E402
from pipeline import dedupe_spans, extract_spans, parse_sentences  # noqa: E402
from rules import build_default_checker  # noqa: E402

print("Loading stanza pipeline (tokenize,pos,lemma,depparse)...", file=sys.stderr)
NLP = stanza.Pipeline("ru", processors="tokenize,pos,lemma,depparse")
CHECKER = build_default_checker()
PATTERNS_BY_TYPE = load_patterns("both", LINKERS_CSV, INTRO_CSV)

# `dedupe_spans`, `extract_spans`, `parse_sentences` are re-exported here
# (single source: linker_extraction.pipeline) for callbacks.py to use.
__all__ = [
    "NLP", "CHECKER", "PATTERNS_BY_TYPE",
    "dedupe_spans", "extract_spans", "parse_sentences",
]
