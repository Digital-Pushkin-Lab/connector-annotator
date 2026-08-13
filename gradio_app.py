#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gradio interface for highlighting Russian linker words in text.

Original features:
  * greedy longest-first matching against nested_linkers.json
  * atoms of a matched linker are highlighted as nested spans

Expanded features:
  * modify/delete existing highlights
  * add manual highlights by exact character positions or by phrase
  * export the resulting markup as an XML document
"""

import json
import re
import uuid
import xml.dom.minidom
from datetime import datetime
from typing import Dict, List, Set, Tuple
from xml.etree import ElementTree as ET
import os

# Remove ALL_PROXY and all_proxy BEFORE anything else
os.environ.pop("ALL_PROXY", None)
os.environ.pop("all_proxy", None)

# Also clear the others to be safe
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("https_proxy", None)
os.environ.pop("FTP_PROXY", None)
os.environ.pop("ftp_proxy", None)

# Keep no_proxy/NO_PROXY for localhost bypass
# os.environ["NO_PROXY"] = "localhost,127.0.0.0/8,::1"

import gradio as gr

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
.scrollable-table {
    max-height: 400px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 0.5rem;
    background: #ffffff;
}
"""

JSON_PATH = os.path.join(os.path.dirname(__file__), "nested_linkers.json")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_linker_data(path: str):
    """
    Load nested_linkers.json and return:
      - cont_by_first:    first_word -> [(dict_form, [words])]
      - disc_by_first:    first_word -> [(dict_form, [[words], ...])]
      - atom_map:         dict_form -> set of atom dict_forms
      - semfield1_map:    dict_form -> list of primary-meaning alternatives
      - semfield2_map:    dict_form -> list of obligatory accompanying meanings
      - pragmatics_map:   dict_form -> list of obligatory pragmatic meanings
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cont_by_first: Dict[str, List[Tuple[str, List[str]]]] = {}
    disc_by_first: Dict[str, List[Tuple[str, List[List[str]]]]] = {}
    atom_map: Dict[str, Set[str]] = {}
    semfield1_map: Dict[str, List[str]] = {}
    semfield2_map: Dict[str, List[str]] = {}
    pragmatics_map: Dict[str, List[str]] = {}
    all_semfield1: Set[str] = set()
    all_semfield2: Set[str] = set()
    all_pragmatics: Set[str] = set()

    for key, value in data.items():
        atoms = value.get("atoms") or []
        if atoms:
            atom_map[key] = set(atoms)

        semfield1 = value.get("semfield1") or []
        if semfield1:
            semfield1_map[key] = list(semfield1)
            all_semfield1.update(semfield1)

        semfield2 = value.get("semfield2") or []
        if semfield2:
            semfield2_map[key] = list(semfield2)
            all_semfield2.update(semfield2)

        pragmatics = value.get("pragmatics") or []
        if pragmatics:
            pragmatics_map[key] = list(pragmatics)
            all_pragmatics.update(pragmatics)

        if "..." in key:
            raw_parts = [p.strip() for p in key.split("...")]
            word_parts = [p.split() for p in raw_parts if p.strip()]
            if word_parts and word_parts[0]:
                fw = word_parts[0][0].lower()
                disc_by_first.setdefault(fw, []).append((key, word_parts))
        else:
            words = key.split()
            if words:
                fw = words[0].lower()
                cont_by_first.setdefault(fw, []).append((key, words))

    return (
        cont_by_first,
        disc_by_first,
        atom_map,
        semfield1_map,
        semfield2_map,
        pragmatics_map,
        sorted(all_semfield1),
        sorted(all_semfield2),
        sorted(all_pragmatics),
    )


(
    CONT_BY_FIRST,
    DISC_BY_FIRST,
    ATOM_MAP,
    SEMFIELD1_MAP,
    SEMFIELD2_MAP,
    PRAGMATICS_MAP,
    _RAW_SEMFIELD1_CHOICES,
    _RAW_SEMFIELD2_CHOICES,
    _RAW_PRAGMATICS_CHOICES,
) = load_linker_data(JSON_PATH)

NO_SEMFIELD = "не выбрано"
SEMFIELD1_CHOICES = [NO_SEMFIELD] + _RAW_SEMFIELD1_CHOICES
SEMFIELD2_CHOICES = [NO_SEMFIELD] + _RAW_SEMFIELD2_CHOICES
PRAGMATICS_CHOICES = [NO_SEMFIELD] + _RAW_PRAGMATICS_CHOICES

# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z]+|[^А-Яа-яЁёA-Za-z]+")


def tokenize(text: str) -> List[Tuple[str, int, int, bool]]:
    """Split text into (token, start, end, is_word)."""
    tokens = []
    for m in WORD_RE.finditer(text):
        tok = m.group()
        tokens.append((tok, m.start(), m.end(), tok[0].isalpha()))
    return tokens


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

Match = Tuple[int, int, List[Tuple[int, int]], str]


def find_all_matches(text: str) -> List[Match]:
    """
    Find every occurrence of every linker in *text*.
    Returns [(total_start, total_end, spans, dict_form)]
    where spans is a list of (start, end) segments.
    """
    tokens = tokenize(text)
    words = [(t[0], t[1], t[2]) for t in tokens if t[3]]
    matches: List[Match] = []
    seen_spans: Dict[Tuple[Tuple[int, int], ...], str] = {}

    def add_match(total_s, total_e, spans, key):
        span_key = tuple(spans)
        if span_key not in seen_spans:
            seen_spans[span_key] = key
            matches.append((total_s, total_e, spans, key))
        else:
            if len(key) < len(seen_spans[span_key]):
                seen_spans[span_key] = key
                for idx, (ts, te, sp, k) in enumerate(matches):
                    if tuple(sp) == span_key:
                        matches[idx] = (total_s, total_e, spans, key)
                        break

    # ---- continuous linkers ----
    for i, (w, ws, we) in enumerate(words):
        for key, word_list in CONT_BY_FIRST.get(w.lower(), []):
            if len(word_list) > len(words) - i:
                continue
            ok = True
            for j, lw in enumerate(word_list):
                if words[i + j][0].lower() != lw.lower():
                    ok = False
                    break
            if not ok:
                continue
            s = words[i][1]
            e = words[i + len(word_list) - 1][2]
            add_match(s, e, [(s, e)], key)

    # ---- discontinuous linkers ----
    for i, (w, ws, we) in enumerate(words):
        for key, parts in DISC_BY_FIRST.get(w.lower(), []):
            first_part = parts[0]
            if len(first_part) > len(words) - i:
                continue

            ok = True
            for j, lw in enumerate(first_part):
                if words[i + j][0].lower() != lw.lower():
                    ok = False
                    break
            if not ok:
                continue

            spans = [(words[i][1], words[i + len(first_part) - 1][2])]
            cur = i + len(first_part)
            all_found = True

            for part_words in parts[1:]:
                found = False
                for k in range(cur, len(words) - len(part_words) + 1):
                    ok2 = True
                    for j, lw in enumerate(part_words):
                        if words[k + j][0].lower() != lw.lower():
                            ok2 = False
                            break
                    if ok2:
                        spans.append((words[k][1], words[k + len(part_words) - 1][2]))
                        cur = k + len(part_words)
                        found = True
                        break
                if not found:
                    all_found = False
                    break

            if all_found:
                total_s = spans[0][0]
                total_e = spans[-1][1]
                add_match(total_s, total_e, spans, key)

    return matches


# ---------------------------------------------------------------------------
# Greedy resolution (recursive, atom-aware)
# ---------------------------------------------------------------------------

def greedy_resolve(matches: List[Match]) -> List[Tuple[int, int, str]]:
    """
    Given a list of matches, greedily select the longest non-overlapping
    matches as primaries.  Matches fully contained inside a primary are
    kept ONLY if they are listed as atoms of that primary in the JSON.
    The same logic is applied recursively to the kept atoms.
    Returns a flat list of (start, end, dict_form) ready for HTML.
    """
    if not matches:
        return []

    matches = sorted(matches, key=lambda m: (m[1] - m[0], m[0]), reverse=True)

    primary = matches[0]
    total_s, total_e, spans, key = primary

    result = [(s, e, key) for s, e in spans]

    allowed_atoms = ATOM_MAP.get(key, set())

    contained: List[Match] = []
    non_overlapping: List[Match] = []

    for m in matches[1:]:
        ms, me, mspans, mkey = m
        if ms >= total_s and me <= total_e:
            if mkey in allowed_atoms:
                contained.append(m)
        elif me <= total_s or ms >= total_e:
            non_overlapping.append(m)

    result.extend(greedy_resolve(contained))
    result.extend(greedy_resolve(non_overlapping))
    return result


# ---------------------------------------------------------------------------
# Highlight state
# ---------------------------------------------------------------------------

Highlight = Dict[str, object]


def make_highlight(
    start: int,
    end: int,
    label: str,
    source: str,
    semfield1: List[str] = None,
    semfield2: List[str] = None,
    pragmatics: List[str] = None,
) -> Highlight:
    return {
        "id": str(uuid.uuid4())[:8],
        "start": start,
        "end": end,
        "label": label,
        "source": source,
        "semfield1": list(semfield1) if semfield1 else [],
        "semfield2": list(semfield2) if semfield2 else [],
        "pragmatics": list(pragmatics) if pragmatics else [],
    }


def deduplicate_flat(flat: List[Tuple[int, int, str]]) -> List[Tuple[int, int, str]]:
    """
    Remove exact (start, end) duplicates from a flat list of highlights.
    If two highlights occupy the same span, keep the one with the shorter
    dictionary/label form.
    """
    seen: Dict[Tuple[int, int], str] = {}
    order: List[Tuple[int, int]] = []
    for s, e, key in flat:
        pos = (s, e)
        if pos not in seen:
            seen[pos] = key
            order.append(pos)
        elif len(key) < len(seen[pos]):
            seen[pos] = key
    return [(s, e, seen[(s, e)]) for s, e in order]


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


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_html(text: str, highlights: List[Highlight]) -> str:
    """Turn flat properly-nested highlights into HTML."""
    if not text:
        return '<div class="linker-container"></div>'

    if not highlights:
        return f'<div class="linker-container">{escape_html(text)}</div>'

    events = []
    for h in highlights:
        source_cls = " manual" if h.get("source") == "manual" else ""
        events.append((h["start"], True, h["end"], h["label"], source_cls))
        events.append((h["end"], False, h["start"], h["label"], source_cls))

    events.sort(key=lambda ev: (ev[0], 0 if not ev[1] else 1, -ev[2]))

    parts = []
    pos = 0
    stack = []

    for idx, is_open, other, label, source_cls in events:
        parts.append(escape_html(text[pos:idx]))
        if is_open:
            parts.append(f'<span class="linker{source_cls}" title="{escape_html(label)}">')
            stack.append((idx, other, label))
        else:
            if stack and stack[-1][0] == other and stack[-1][1] == idx:
                stack.pop()
            else:
                for si in range(len(stack) - 1, -1, -1):
                    if stack[si][0] == other and stack[si][1] == idx:
                        while len(stack) > si + 1:
                            parts.append("</span>")
                            stack.pop()
                        stack.pop()
                        break
            parts.append("</span>")
        pos = idx

    parts.append(escape_html(text[pos:]))
    return f'<div class="linker-container">{"".join(parts)}</div>'


# ---------------------------------------------------------------------------
# Tree conversion (for XML export)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# XML export
# ---------------------------------------------------------------------------

def build_xml(text: str, highlights: List[Highlight]) -> str:
    """Serialize the markup to a pretty-printed XML string."""
    root = ET.Element("linker-annotation")

    meta = ET.SubElement(root, "metadata")
    ET.SubElement(meta, "created").text = datetime.now().isoformat()
    ET.SubElement(meta, "generator").text = "gradio_app.py"

    text_el = ET.SubElement(root, "text")
    text_el.text = text

    spans_el = ET.SubElement(root, "spans")
    tree = build_tree(highlights)

    def add_span(node: Highlight, parent: ET.Element) -> None:
        el = ET.SubElement(parent, "span")
        el.set("id", str(node["id"]))
        el.set("start", str(node["start"]))
        el.set("end", str(node["end"]))
        el.set("label", str(node["label"]))
        el.set("semfield1", _alternatives_str(node.get("semfield1", [])))
        el.set("semfield2", _set_str(node.get("semfield2", [])))
        el.set("pragmatics", _set_str(node.get("pragmatics", [])))
        el.set("source", str(node["source"]))
        surface = text[node["start"]:node["end"]]
        el.set("surface", surface)
        for child in node.get("children", []):
            add_span(child, el)

    for root_node in tree:
        add_span(root_node, spans_el)

    rough = ET.tostring(root, encoding="unicode")
    reparsed = xml.dom.minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")


def save_xml(text: str, highlights: List[Highlight]) -> Tuple[str, str]:
    """Write the XML to a timestamped file and return its path."""
    if not text:
        return "", "Нет текста для сохранения."
    xml_str = build_xml(text, highlights)
    filename = f"linker_annotation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    return path, f"Сохранено: {filename}"


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def choice_str(h: Highlight, text: str) -> str:
    preview = text[h["start"]:h["end"]].replace("\n", " ")[:30]
    return f"{h['id']}: [{h['start']}-{h['end']}] \"{h['label']}\" ({preview})"


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


def highlights_to_table(highlights: List[Highlight], text: str) -> str:
    """Render highlights as a Markdown table string."""
    if not highlights:
        return "_Разметка отсутствует_"
    rows = []
    rows.append(
        "| id | start | end | название коннектора | основное значение | "
        "сопроводительное значение | прагматическая установка | source | текст |"
    )
    rows.append("|---|---|---|---|---|---|---|---|---|")
    for h in sorted(highlights, key=lambda x: (x["start"], -x["end"])):
        surface = text[h["start"]:h["end"]].replace("|", "\\|").replace("\n", " ")
        rows.append(
            f"| {h['id']} | {h['start']} | {h['end']} | {h['label']} | "
            f"{_alternatives_display_value(h.get('semfield1', []))} | "
            f"{_set_display_value(h.get('semfield2', []))} | "
            f"{_set_display_value(h.get('pragmatics', []))} | {h['source']} | {surface} |"
        )
    return "\n".join(rows)


def compute_stats(highlights: List[Highlight]) -> str:
    """Return Markdown with connector statistics, broken down separately by
    semfield1 (primary meaning), semfield2 (accompanying meaning) and
    pragmatics."""
    if not highlights:
        return "_Нет данных для статистики_"

    tree = build_tree(highlights)
    roots = tree

    def count_atoms(node: Highlight) -> int:
        children = node.get("children", [])
        return len(children) + sum(count_atoms(child) for child in children)

    total_connectors = len(roots)
    total_atoms = sum(count_atoms(root) for root in roots)

    breakdowns = [
        ("semfield1", "По основному значению (semfield1)"),
        ("semfield2", "По сопроводительному значению (semfield2)"),
        ("pragmatics", "По прагматической установке"),
    ]

    lines = [f"**Всего коннекторов:** {total_connectors} (атомов: {total_atoms})"]
    for field, title in breakdowns:
        group_counts: Dict[str, int] = {}
        group_atoms: Dict[str, int] = {}
        for root in roots:
            root_atom_count = count_atoms(root)
            for sf in root.get(field, []):
                group_counts[sf] = group_counts.get(sf, 0) + 1
                group_atoms[sf] = group_atoms.get(sf, 0) + root_atom_count
        if group_counts:
            lines.append("")
            lines.append(f"**{title}:**")
            for sf in sorted(group_counts.keys()):
                lines.append(f"- {sf}: {group_counts[sf]} (атомов: {group_atoms.get(sf, 0)})")
    return "\n".join(lines)


def render_state(text: str, highlights: List[Highlight], selected_id: str = ""):
    """Return updated HTML, table, dropdown, and stats for a given state."""
    html = build_html(text, highlights)
    table = highlights_to_table(highlights, text)
    stats = compute_stats(highlights)
    choices = [choice_str(h, text) for h in sorted(highlights, key=lambda x: (x["start"], -x["end"]))]
    selected_value = ""
    if selected_id:
        for h in highlights:
            if h["id"] == selected_id:
                selected_value = choice_str(h, text)
                break
    return html, table, gr.update(choices=choices, value=selected_value), stats


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def analyze_text(text: str):
    if not text or not text.strip():
        return (
            '<div class="linker-container">Введите текст для анализа…</div>',
            "_Разметка отсутствует_",
            gr.update(choices=[], value=""),
            "_Нет данных для статистики_",
            text,
            [],
            "",
        )
    matches = find_all_matches(text)
    flat = greedy_resolve(matches)
    flat = deduplicate_flat(flat)
    highlights = [
        make_highlight(
            s, e, key, "auto",
            SEMFIELD1_MAP.get(key, []),
            SEMFIELD2_MAP.get(key, []),
            PRAGMATICS_MAP.get(key, []),
        )
        for s, e, key in flat
    ]
    html, table, dropdown, stats = render_state(text, highlights)
    return html, table, dropdown, stats, text, highlights, f"Найдено разметок: {len(highlights)}"


def add_by_position(
    text: str, highlights: List[Highlight], start, end, label: str,
    semfield1: str, semfield2: str, pragmatics: str,
):
    if not text:
        return (*render_state(text, highlights), highlights, "Введите текст.")
    try:
        start = int(start)
        end = int(end)
    except (TypeError, ValueError):
        return (*render_state(text, highlights), highlights, "Некорректные позиции.")

    if not (0 <= start < end <= len(text)):
        return (*render_state(text, highlights), highlights, "Позиции выходят за границы текста.")
    if not label or not str(label).strip():
        return (*render_state(text, highlights), highlights, "Укажите название коннектора.")

    new_hl = make_highlight(
        start, end, str(label).strip(), "manual",
        _normalize_alternatives(semfield1), _normalize_set(semfield2), _normalize_set(pragmatics),
    )
    new_highlights = highlights + [new_hl]
    ok, msg = validate_highlights(new_highlights)
    if not ok:
        return (*render_state(text, highlights), highlights, msg)

    html, table, dropdown, stats = render_state(text, new_highlights, selected_id=new_hl["id"])
    return html, table, dropdown, stats, new_highlights, "Разметка добавлена."


def add_by_phrase(
    text: str, highlights: List[Highlight], phrase: str, label: str,
    semfield1: str, semfield2: str, pragmatics: str,
):
    if not text:
        return (*render_state(text, highlights), highlights, "Введите текст.")
    if not phrase or not phrase.strip():
        return (*render_state(text, highlights), highlights, "Введите фразу.")
    if not label or not str(label).strip():
        return (*render_state(text, highlights), highlights, "Укажите название коннектора.")

    positions = find_phrase_positions(text, phrase.strip())
    if not positions:
        return (*render_state(text, highlights), highlights, "Фраза не найдена.")

    semfield1_list = _normalize_alternatives(semfield1)
    semfield2_list = _normalize_set(semfield2)
    pragmatics_list = _normalize_set(pragmatics)
    new_highlights = list(highlights)
    added_ids = []
    label_clean = str(label).strip()
    for s, e in positions:
        new_hl = make_highlight(s, e, label_clean, "manual", semfield1_list, semfield2_list, pragmatics_list)
        test = new_highlights + [new_hl]
        ok, _ = validate_highlights(test)
        if ok:
            new_highlights.append(new_hl)
            added_ids.append(new_hl["id"])

    if not added_ids:
        return (*render_state(text, highlights), highlights, "Не удалось добавить ни одной разметки (возможны пересечения).")

    selected_id = added_ids[-1]
    html, table, dropdown, stats = render_state(text, new_highlights, selected_id=selected_id)
    return html, table, dropdown, stats, new_highlights, f"Добавлено разметок: {len(added_ids)}."


def _selected_id_from_choice(choice: str) -> str:
    if not choice:
        return ""
    return choice.split(":", 1)[0]


def on_select_highlight(text: str, highlights: List[Highlight], choice: str):
    hid = _selected_id_from_choice(choice)
    if not hid:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    for h in highlights:
        if h["id"] == hid:
            semfield1_value = _alternatives_display_value(h.get("semfield1", []))
            semfield2_value = _set_display_value(h.get("semfield2", []))
            pragmatics_value = _set_display_value(h.get("pragmatics", []))
            return h["start"], h["end"], h["label"], semfield1_value, semfield2_value, pragmatics_value
    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()


def update_highlight(
    text: str, highlights: List[Highlight], choice: str, start, end, label: str,
    semfield1: str, semfield2: str, pragmatics: str,
):
    hid = _selected_id_from_choice(choice)
    if not hid:
        return (*render_state(text, highlights), highlights, "Выберите разметку для изменения.")

    try:
        start = int(start)
        end = int(end)
    except (TypeError, ValueError):
        return (*render_state(text, highlights), highlights, "Некорректные позиции.")

    if not (0 <= start < end <= len(text)):
        return (*render_state(text, highlights), highlights, "Позиции выходят за границы текста.")

    semfield1_list = _normalize_alternatives(semfield1)
    semfield2_list = _normalize_set(semfield2)
    pragmatics_list = _normalize_set(pragmatics)

    new_highlights = []
    found = False
    for h in highlights:
        if h["id"] == hid:
            new_h = dict(h)
            new_h["start"] = start
            new_h["end"] = end
            new_h["label"] = str(label).strip() if label and str(label).strip() else h["label"]
            new_h["semfield1"] = semfield1_list
            new_h["semfield2"] = semfield2_list
            new_h["pragmatics"] = pragmatics_list
            new_highlights.append(new_h)
            found = True
        else:
            new_highlights.append(dict(h))

    if not found:
        return (*render_state(text, highlights), highlights, "Разметка не найдена.")

    ok, msg = validate_highlights(new_highlights)
    if not ok:
        return (*render_state(text, highlights), highlights, msg)

    html, table, dropdown, stats = render_state(text, new_highlights, selected_id=hid)
    return html, table, dropdown, stats, new_highlights, "Разметка изменена."


def delete_highlight(text: str, highlights: List[Highlight], choice: str):
    hid = _selected_id_from_choice(choice)
    if not hid:
        return (*render_state(text, highlights), highlights, "Выберите разметку для удаления.")
    new_highlights = [h for h in highlights if h["id"] != hid]
    if len(new_highlights) == len(highlights):
        return (*render_state(text, highlights), highlights, "Разметка не найдена.")
    html, table, dropdown, stats = render_state(text, new_highlights)
    return html, table, dropdown, stats, new_highlights, "Разметка удалена."


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def main():
    with gr.Blocks(css=CSS, title="Аннотатор коннекторов") as demo:
        gr.Markdown("# Аннотатор коннекторов")
        gr.Markdown(
            "Вставьте текст на русском языке и нажмите **Анализировать**. "
            "Найденные коннекторы будут подсвечены оранжевым, ручная разметка — синим. "
            "Наведите курсор на фрагмент, чтобы увидеть название коннектора."
        )

        state_text = gr.State("")
        state_highlights = gr.State([])

        with gr.Row():
            with gr.Column(scale=1):
                input_box = gr.Textbox(
                    label="Исходный текст",
                    placeholder="Введите текст здесь…",
                    lines=10,
                )
                analyze_btn = gr.Button("Анализировать", variant="primary")

                gr.Markdown("### Добавить разметку")
                with gr.Tabs():
                    with gr.TabItem("По позициям"):
                        add_start = gr.Number(label="Начало (символ)", precision=0, minimum=0)
                        add_end = gr.Number(label="Конец (символ)", precision=0, minimum=0)
                        add_label_pos = gr.Textbox(label="Название коннектора", placeholder="например, если… то")
                        add_semfield1_pos = gr.Dropdown(
                            label="Основное значение (semfield1)",
                            info="Альтернативы через «;» — можно оставить одну или несколько.",
                            choices=SEMFIELD1_CHOICES,
                            value=NO_SEMFIELD,
                            allow_custom_value=True,
                        )
                        add_semfield2_pos = gr.Dropdown(
                            label="Сопроводительное значение (облигаторное)",
                            info="Набор через «,» — сопровождает основное значение.",
                            choices=SEMFIELD2_CHOICES,
                            value=NO_SEMFIELD,
                            allow_custom_value=True,
                        )
                        add_pragmatics_pos = gr.Dropdown(
                            label="Прагматическая установка (облигаторная)",
                            info="Набор через «,».",
                            choices=PRAGMATICS_CHOICES,
                            value=NO_SEMFIELD,
                            allow_custom_value=True,
                        )
                        add_pos_btn = gr.Button("Добавить разметку")

                    with gr.TabItem("По фразе"):
                        add_phrase = gr.Textbox(label="Фраза", placeholder="Введите точную фразу из текста")
                        add_label_phrase = gr.Textbox(label="Название коннектора", placeholder="например, если… то")
                        add_semfield1_phrase = gr.Dropdown(
                            label="Основное значение (semfield1)",
                            info="Альтернативы через «;» — можно оставить одну или несколько.",
                            choices=SEMFIELD1_CHOICES,
                            value=NO_SEMFIELD,
                            allow_custom_value=True,
                        )
                        add_semfield2_phrase = gr.Dropdown(
                            label="Сопроводительное значение (облигаторное)",
                            info="Набор через «,» — сопровождает основное значение.",
                            choices=SEMFIELD2_CHOICES,
                            value=NO_SEMFIELD,
                            allow_custom_value=True,
                        )
                        add_pragmatics_phrase = gr.Dropdown(
                            label="Прагматическая установка (облигаторная)",
                            info="Набор через «,».",
                            choices=PRAGMATICS_CHOICES,
                            value=NO_SEMFIELD,
                            allow_custom_value=True,
                        )
                        add_phrase_btn = gr.Button("Найти и добавить")

                gr.Markdown("### Изменить или удалить")
                hl_select = gr.Dropdown(label="Выбранная разметка", choices=[])
                edit_start = gr.Number(label="Начало", precision=0, minimum=0)
                edit_end = gr.Number(label="Конец", precision=0, minimum=0)
                edit_label = gr.Textbox(label="Название коннектора")
                edit_semfield1 = gr.Dropdown(
                    label="Основное значение (semfield1)",
                    info="Альтернативы через «;» — можно оставить одну или несколько.",
                    choices=SEMFIELD1_CHOICES,
                    value=NO_SEMFIELD,
                    allow_custom_value=True,
                )
                edit_semfield2 = gr.Dropdown(
                    label="Сопроводительное значение (облигаторное)",
                    info="Набор через «,» — сопровождает основное значение. Можно править вручную.",
                    choices=SEMFIELD2_CHOICES,
                    value=NO_SEMFIELD,
                    allow_custom_value=True,
                )
                edit_pragmatics = gr.Dropdown(
                    label="Прагматическая установка (облигаторная)",
                    info="Набор через «,». Можно править вручную.",
                    choices=PRAGMATICS_CHOICES,
                    value=NO_SEMFIELD,
                    allow_custom_value=True,
                )
                with gr.Row():
                    update_btn = gr.Button("Изменить границы / название / значения")
                    delete_btn = gr.Button("Удалить разметку", variant="stop")

                save_btn = gr.Button("Сохранить разметку как XML", variant="secondary")

                gr.Examples(
                    examples=[
                        ["Не оставь меня ни мертвым, ни раненым."],
                        ["До тех пор, пока не выработается привычка."],
                        ["А в то же время он не хотел уходить."],
                        ["Если ты придёшь, то я буду рад, а если нет — тоже хорошо."],
                    ],
                    inputs=input_box,
                    label="Примеры",
                )

            with gr.Column(scale=1):
                output_html = gr.HTML(label="Размеченный текст")
                output_table = gr.Markdown(label="Текущая разметка", elem_classes="scrollable-table")
                output_stats = gr.Markdown(label="Статистика")
                output_file = gr.File(label="XML-файл")
                msg_box = gr.Textbox(label="Сообщения", interactive=False)

        # ---- wire events ----
        analyze_btn.click(
            fn=analyze_text,
            inputs=input_box,
            outputs=[output_html, output_table, hl_select, output_stats, state_text, state_highlights, msg_box],
        )

        add_pos_btn.click(
            fn=add_by_position,
            inputs=[
                state_text, state_highlights, add_start, add_end, add_label_pos,
                add_semfield1_pos, add_semfield2_pos, add_pragmatics_pos,
            ],
            outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
        )

        add_phrase_btn.click(
            fn=add_by_phrase,
            inputs=[
                state_text, state_highlights, add_phrase, add_label_phrase,
                add_semfield1_phrase, add_semfield2_phrase, add_pragmatics_phrase,
            ],
            outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
        )

        hl_select.change(
            fn=on_select_highlight,
            inputs=[state_text, state_highlights, hl_select],
            outputs=[edit_start, edit_end, edit_label, edit_semfield1, edit_semfield2, edit_pragmatics],
        )

        update_btn.click(
            fn=update_highlight,
            inputs=[
                state_text, state_highlights, hl_select, edit_start, edit_end, edit_label,
                edit_semfield1, edit_semfield2, edit_pragmatics,
            ],
            outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
        )

        delete_btn.click(
            fn=delete_highlight,
            inputs=[state_text, state_highlights, hl_select],
            outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
        )

        save_btn.click(
            fn=save_xml,
            inputs=[state_text, state_highlights],
            outputs=[output_file, msg_box],
        )

    demo.launch(share=True)


if __name__ == "__main__":
    main()
