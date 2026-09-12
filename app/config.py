"""Static configuration: CSS, file paths, and the lookup tables loaded from
linker_extraction/data/linkers.csv (semfields, pragmatics, category names)."""

import os

import pandas as pd

# gradio_app/ (the project root: contains linker_extraction/, requirements.txt, …)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

CSS = """
.linker-container {
    font-size: 1.15rem;
    line-height: 1.8;
    padding: 1rem;
    background: #fafafa;
    border-radius: 8px;
    white-space: pre-wrap;
    font-family: Georgia, "Times New Roman", serif;
}
.linker {
    background-color: rgba(230, 160, 100, 0.35);
    border: 1px solid rgba(180, 120, 60, 0.5);
    border-radius: 3px;
    padding: 1px 2px;
    cursor: help;
    transition: background-color 0.15s ease;
}
.linker:hover {
    background-color: rgba(230, 160, 100, 0.65);
}
.linker .linker {
    background-color: rgba(200, 110, 60, 0.45);
    border-color: rgba(150, 80, 40, 0.6);
}
.linker .linker:hover {
    background-color: rgba(200, 110, 60, 0.75);
}
.linker .linker .linker {
    background-color: rgba(170, 80, 40, 0.55);
    border-color: rgba(120, 50, 30, 0.7);
}
.linker .linker .linker:hover {
    background-color: rgba(170, 80, 40, 0.85);
}
.manual {
    background-color: rgba(100, 160, 230, 0.35) !important;
    border-color: rgba(60, 120, 180, 0.5) !important;
}
.manual:hover {
    background-color: rgba(100, 160, 230, 0.65) !important;
}
.intro {
    background-color: rgba(120, 170, 90, 0.35) !important;
    border-color: rgba(80, 130, 50, 0.5) !important;
}
.intro:hover {
    background-color: rgba(120, 170, 90, 0.65) !important;
}
.scrollable-table {
    max-height: 400px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 0.5rem;
    background: #ffffff;
}
.progress-outer {
    background: #e8e8e8;
    border-radius: 6px;
    height: 14px;
    overflow: hidden;
}
.progress-inner {
    background: rgba(230, 160, 100, 0.9);
    height: 100%;
    transition: width 0.2s ease;
}
.progress-label {
    font-size: 0.85rem;
    color: #666;
    margin-top: 2px;
}
"""

LINKERS_CSV = os.path.join(PROJECT_ROOT, "linker_extraction", "data", "linkers.csv")
INTRO_CSV = os.path.join(PROJECT_ROOT, "linker_extraction", "data", "intro_words.csv")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_linker_data(path: str):
    """
    Load linker_extraction/data/linkers.csv and return, keyed by the
    `linker` column (the same surface-string convention -- "..." for
    discontinuous connectors -- that `matching.pattern_surface` reconstructs
    for linker_extraction's matches):
      - semfield1_map:    linker -> list of primary-meaning alternatives (';'-separated in the CSV)
      - semfield2_map:    linker -> list of obligatory accompanying meanings (','-separated)
      - pragmatics_map:   linker -> list of obligatory pragmatic meanings (','-separated)
    """
    df = pd.read_csv(path, keep_default_na=False)

    semfield1_map: dict[str, list[str]] = {}
    semfield2_map: dict[str, list[str]] = {}
    pragmatics_map: dict[str, list[str]] = {}
    all_semfield1: set[str] = set()
    all_semfield2: set[str] = set()
    all_pragmatics: set[str] = set()

    for row in df.itertuples(index=False):
        key = str(row.linker).strip()
        if not key:
            continue

        semfield1 = [p.strip() for p in str(row.semfield1).split(";") if p.strip()]
        if semfield1:
            semfield1_map[key] = semfield1
            all_semfield1.update(semfield1)

        semfield2 = [p.strip() for p in str(row.semfield2).split(",") if p.strip()]
        if semfield2:
            semfield2_map[key] = semfield2
            all_semfield2.update(semfield2)

        pragmatics = [p.strip() for p in str(row.pragmatics).split(",") if p.strip()]
        if pragmatics:
            pragmatics_map[key] = pragmatics
            all_pragmatics.update(pragmatics)

    return (
        semfield1_map,
        semfield2_map,
        pragmatics_map,
        sorted(all_semfield1),
        sorted(all_semfield2),
        sorted(all_pragmatics),
    )


(
    SEMFIELD1_MAP,
    SEMFIELD2_MAP,
    PRAGMATICS_MAP,
    _RAW_SEMFIELD1_CHOICES,
    _RAW_SEMFIELD2_CHOICES,
    _RAW_PRAGMATICS_CHOICES,
) = load_linker_data(LINKERS_CSV)

NO_SEMFIELD = "не выбрано"
SEMFIELD1_CHOICES = [NO_SEMFIELD] + _RAW_SEMFIELD1_CHOICES
SEMFIELD2_CHOICES = [NO_SEMFIELD] + _RAW_SEMFIELD2_CHOICES
PRAGMATICS_CHOICES = [NO_SEMFIELD] + _RAW_PRAGMATICS_CHOICES

CATEGORY_DISPLAY = {"linker": "линкер", "intro": "вводное слово"}
CATEGORY_FROM_DISPLAY = {v: k for k, v in CATEGORY_DISPLAY.items()}
CATEGORY_CHOICES = [NO_SEMFIELD] + list(CATEGORY_DISPLAY.values())


def _category_display(category: str) -> str:
    return CATEGORY_DISPLAY.get(category, NO_SEMFIELD)


def _category_from_display(display: str) -> str:
    return CATEGORY_FROM_DISPLAY.get(display, "")
