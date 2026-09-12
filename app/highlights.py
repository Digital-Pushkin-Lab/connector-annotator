"""The highlight data model: creation, validation, phrase search, the
flat-list <-> containment-tree conversion (used for stats/XML export), and
the small string helpers shared by the table/XML/UI-choice renderers."""

import uuid
from typing import Dict, List, Tuple

from .config import NO_SEMFIELD

Highlight = Dict[str, object]


def make_highlight(
    start: int,
    end: int,
    label: str,
    source: str,
    semfield1: List[str] = None,
    semfield2: List[str] = None,
    pragmatics: List[str] = None,
    category: str = "",
    group_id: str = None,
) -> Highlight:
    """`id` uniquely addresses this single span (used internally to select/
    edit/delete one highlight, even a lone part of a discontinuous linker).
    `group_id` is shared by every part of the same linker occurrence (e.g.
    "если" и "то" from "если...то") so exports can show them as one
    connector; it defaults to `id` for standalone highlights."""
    hl_id = str(uuid.uuid4())[:8]
    return {
        "id": hl_id,
        "group_id": group_id or hl_id,
        "start": start,
        "end": end,
        "label": label,
        "source": source,
        "semfield1": list(semfield1) if semfield1 else [],
        "semfield2": list(semfield2) if semfield2 else [],
        "pragmatics": list(pragmatics) if pragmatics else [],
        "category": category or "",
    }


def validate_highlights(highlights: List[Highlight]) -> Tuple[bool, str]:
    """
    Ensure highlights are either nested or disjoint.
    Exact duplicates and partial overlaps are rejected.
    """
    for i, h1 in enumerate(highlights):
        if h1["start"] >= h1["end"]:
            return False, f"Некорректные границы: начало ({h1['start']}) должно быть меньше конца ({h1['end']})."
        for j in range(i + 1, len(highlights)):
            h2 = highlights[j]
            if h1["start"] == h2["start"] and h1["end"] == h2["end"]:
                return False, "Дубликат: два одинаковых фрагмента."
            if h1["start"] < h2["end"] and h2["start"] < h1["end"]:
                c1 = h1["start"] <= h2["start"] and h1["end"] >= h2["end"]
                c2 = h2["start"] <= h1["start"] and h2["end"] >= h1["end"]
                if not c1 and not c2:
                    return False, (
                        f"Частичное пересечение: "
                        f"[{h1['start']}-{h1['end']}] и [{h2['start']}-{h2['end']}]. "
                        f"Разметка должна быть либо вложенной, либо непересекающейся."
                    )
    return True, ""


def find_phrase_positions(text: str, phrase: str) -> List[Tuple[int, int]]:
    """Return all case-insensitive occurrences of *phrase* in *text*."""
    if not phrase:
        return []
    positions = []
    start = 0
    lower_phrase = phrase.lower()
    lower_text = text.lower()
    while True:
        idx = lower_text.find(lower_phrase, start)
        if idx == -1:
            break
        positions.append((idx, idx + len(phrase)))
        start = idx + 1
    return positions


def build_tree(highlights: List[Highlight]) -> List[Highlight]:
    """
    Convert a flat list of highlights into a nested tree structure
    based on span containment.  Highlights must already be valid
    (nested or disjoint).
    """
    sorted_hl = sorted(highlights, key=lambda h: (h["start"], -h["end"]))
    roots: List[Highlight] = []
    stack: List[Highlight] = []

    for h in sorted_hl:
        node: Highlight = {**h, "children": []}
        while stack and stack[-1]["end"] <= node["start"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots


def _normalize_alternatives(raw: str) -> List[str]:
    """Convert a raw semfield1 field value into a list of alternatives (';'-separated)."""
    if not raw or str(raw).strip() == NO_SEMFIELD:
        return []
    return [sf.strip() for sf in str(raw).split(";") if sf.strip() and sf.strip() != NO_SEMFIELD]


def _normalize_set(raw: str) -> List[str]:
    """Convert a raw semfield2/pragmatics field value into a list (','-separated set)."""
    if not raw or str(raw).strip() == NO_SEMFIELD:
        return []
    return [sf.strip() for sf in str(raw).split(",") if sf.strip() and sf.strip() != NO_SEMFIELD]


def _alternatives_str(values: List[str]) -> str:
    return "; ".join(values) if values else ""


def _set_str(values: List[str]) -> str:
    return ", ".join(values) if values else ""


def _alternatives_display_value(values: List[str]) -> str:
    return "; ".join(values) if values else NO_SEMFIELD


def _set_display_value(values: List[str]) -> str:
    return ", ".join(values) if values else NO_SEMFIELD


def choice_str(h: Highlight, text: str) -> str:
    preview = text[h["start"]:h["end"]].replace("\n", " ")[:30]
    return f"{h['id']}: [{h['start']}-{h['end']}] \"{h['label']}\" ({preview})"


def _selected_id_from_choice(choice: str) -> str:
    if not choice:
        return ""
    return choice.split(":", 1)[0]
