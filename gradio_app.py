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
import sys
import uuid
import xml.dom.minidom
from datetime import datetime
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "linker_extraction"))

import stanza  # noqa: E402
from extract import load_patterns  # noqa: E402
from pipeline import extract_spans, parse_sentences  # noqa: E402
from rules import build_default_checker  # noqa: E402

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
"""

JSON_PATH = os.path.join(os.path.dirname(__file__), "nested_linkers.json")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_linker_data(path: str):
    """
    Load nested_linkers.json and return, keyed by dict_form (the same
    surface-string convention -- "..." for discontinuous connectors -- used
    by linker_extraction's matches):
      - semfield1_map:    dict_form -> list of primary-meaning alternatives
      - semfield2_map:    dict_form -> list of obligatory accompanying meanings
      - pragmatics_map:   dict_form -> list of obligatory pragmatic meanings
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    semfield1_map: dict[str, list[str]] = {}
    semfield2_map: dict[str, list[str]] = {}
    pragmatics_map: dict[str, list[str]] = {}
    all_semfield1: set[str] = set()
    all_semfield2: set[str] = set()
    all_pragmatics: set[str] = set()

    for key, value in data.items():
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
) = load_linker_data(JSON_PATH)

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


# ---------------------------------------------------------------------------
# linker_extraction engine (stanza dependency parsing + rule-based scoring)
# ---------------------------------------------------------------------------

LINKERS_CSV = os.path.join(os.path.dirname(__file__), "linker_extraction", "data", "linkers.csv")
INTRO_CSV = os.path.join(os.path.dirname(__file__), "linker_extraction", "data", "intro_words.csv")

print("Loading stanza pipeline (tokenize,pos,lemma,depparse)...", file=sys.stderr)
NLP = stanza.Pipeline("ru", processors="tokenize,pos,lemma,depparse")
CHECKER = build_default_checker()
PATTERNS_BY_TYPE = load_patterns("both", LINKERS_CSV, INTRO_CSV)


def dedupe_spans(spans: list[dict]) -> list[dict]:
    """Collapse exact-duplicate (start, end) matches -- e.g. a word that
    matches both the linker and intro-word lists -- keeping whichever has
    the higher scored probability."""
    best: dict[tuple[int, int], dict] = {}
    order: list[tuple[int, int]] = []
    for sp in spans:
        pos = (sp["start"], sp["end"])
        if pos not in best:
            best[pos] = sp
            order.append(pos)
        elif sp["probability"] > best[pos]["probability"]:
            best[pos] = sp
    return [best[pos] for pos in order]


# ---------------------------------------------------------------------------
# Highlight state
# ---------------------------------------------------------------------------

Highlight = dict[str, object]


def make_highlight(
    start: int,
    end: int,
    label: str,
    source: str,
    semfield1: list[str] = None,
    semfield2: list[str] = None,
    pragmatics: list[str] = None,
    category: str = "",
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
        "category": category or "",
    }


def validate_highlights(highlights: list[Highlight]) -> tuple[bool, str]:
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


def find_phrase_positions(text: str, phrase: str) -> list[tuple[int, int]]:
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


def build_html(text: str, highlights: list[Highlight]) -> str:
    """Turn flat properly-nested highlights into HTML."""
    if not text:
        return '<div class="linker-container"></div>'

    if not highlights:
        return f'<div class="linker-container">{escape_html(text)}</div>'

    events = []
    for h in highlights:
        if h.get("source") == "manual":
            variant_cls = " manual"
        elif h.get("category") == "intro":
            variant_cls = " intro"
        else:
            variant_cls = ""
        events.append((h["start"], True, h["end"], h["label"], variant_cls))
        events.append((h["end"], False, h["start"], h["label"], variant_cls))

    events.sort(key=lambda ev: (ev[0], 0 if not ev[1] else 1, -ev[2]))

    parts = []
    pos = 0
    stack = []

    for idx, is_open, other, label, variant_cls in events:
        parts.append(escape_html(text[pos:idx]))
        if is_open:
            parts.append(f'<span class="linker{variant_cls}" title="{escape_html(label)}">')
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

def build_tree(highlights: list[Highlight]) -> list[Highlight]:
    """
    Convert a flat list of highlights into a nested tree structure
    based on span containment.  Highlights must already be valid
    (nested or disjoint).
    """
    sorted_hl = sorted(highlights, key=lambda h: (h["start"], -h["end"]))
    roots: list[Highlight] = []
    stack: list[Highlight] = []

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

def build_xml(text: str, highlights: list[Highlight]) -> str:
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
        el.set("category", str(node.get("category", "")))
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


def save_xml(text: str, highlights: list[Highlight]) -> tuple[str, str]:
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


def _normalize_alternatives(raw: str) -> list[str]:
    """Convert a raw semfield1 field value into a list of alternatives (';'-separated)."""
    if not raw or str(raw).strip() == NO_SEMFIELD:
        return []
    return [sf.strip() for sf in str(raw).split(";") if sf.strip() and sf.strip() != NO_SEMFIELD]


def _normalize_set(raw: str) -> list[str]:
    """Convert a raw semfield2/pragmatics field value into a list (','-separated set)."""
    if not raw or str(raw).strip() == NO_SEMFIELD:
        return []
    return [sf.strip() for sf in str(raw).split(",") if sf.strip() and sf.strip() != NO_SEMFIELD]


def _alternatives_str(values: list[str]) -> str:
    return "; ".join(values) if values else ""


def _set_str(values: list[str]) -> str:
    return ", ".join(values) if values else ""


def _alternatives_display_value(values: list[str]) -> str:
    return "; ".join(values) if values else NO_SEMFIELD


def _set_display_value(values: list[str]) -> str:
    return ", ".join(values) if values else NO_SEMFIELD


def highlights_to_table(highlights: list[Highlight], text: str) -> str:
    """Render highlights as a Markdown table string."""
    if not highlights:
        return "_Разметка отсутствует_"
    rows = []
    rows.append(
        "| id | start | end | название коннектора | тип | основное значение | "
        "сопроводительное значение | прагматическая установка | source | текст |"
    )
    rows.append("|---|---|---|---|---|---|---|---|---|---|")
    for h in sorted(highlights, key=lambda x: (x["start"], -x["end"])):
        surface = text[h["start"]:h["end"]].replace("|", "\\|").replace("\n", " ")
        rows.append(
            f"| {h['id']} | {h['start']} | {h['end']} | {h['label']} | "
            f"{_category_display(h.get('category', ''))} | "
            f"{_alternatives_display_value(h.get('semfield1', []))} | "
            f"{_set_display_value(h.get('semfield2', []))} | "
            f"{_set_display_value(h.get('pragmatics', []))} | {h['source']} | {surface} |"
        )
    return "\n".join(rows)


def compute_stats(highlights: list[Highlight]) -> str:
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

    category_counts: dict[str, int] = {}
    for root in roots:
        category_counts[root.get("category", "")] = category_counts.get(root.get("category", ""), 0) + 1
    if category_counts:
        lines.append("")
        lines.append(
            "**По типу:** "
            + ", ".join(
                f"{_category_display(cat)}: {count}"
                for cat, count in sorted(category_counts.items(), key=lambda kv: _category_display(kv[0]))
            )
        )

    for field, title in breakdowns:
        group_counts: dict[str, int] = {}
        group_atoms: dict[str, int] = {}
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


def render_state(text: str, highlights: list[Highlight], selected_id: str = ""):
    """Return updated HTML, table, dropdown, and stats for a given state."""
    html = build_html(text, highlights)
    table = highlights_to_table(highlights, text)
    stats = compute_stats(highlights)
    choices = [choice_str(h, text) for h in sorted(highlights, key=lambda x: (x["start"], -x["end"]))]
    selected_value = None
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
            gr.update(choices=[], value=None),
            "_Нет данных для статистики_",
            text,
            [],
            "",
        )
    parsed_sentences, _word_count = parse_sentences(text, NLP)
    spans = extract_spans(parsed_sentences, CHECKER, PATTERNS_BY_TYPE)
    spans = dedupe_spans(spans)
    highlights = [
        make_highlight(
            sp["start"], sp["end"], sp["surface"], "auto",
            SEMFIELD1_MAP.get(sp["surface"], []),
            SEMFIELD2_MAP.get(sp["surface"], []),
            PRAGMATICS_MAP.get(sp["surface"], []),
            category=sp["type"],
        )
        for sp in spans
    ]
    html, table, dropdown, stats = render_state(text, highlights)
    return html, table, dropdown, stats, text, highlights, f"Найдено разметок: {len(highlights)}"


def add_by_position(
    text: str, highlights: list[Highlight], start, end, label: str,
    semfield1: str, semfield2: str, pragmatics: str, category: str,
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
        category=_category_from_display(category),
    )
    new_highlights = highlights + [new_hl]
    ok, msg = validate_highlights(new_highlights)
    if not ok:
        return (*render_state(text, highlights), highlights, msg)

    html, table, dropdown, stats = render_state(text, new_highlights, selected_id=new_hl["id"])
    return html, table, dropdown, stats, new_highlights, "Разметка добавлена."


def add_by_phrase(
    text: str, highlights: list[Highlight], phrase: str, label: str,
    semfield1: str, semfield2: str, pragmatics: str, category: str,
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
    category_value = _category_from_display(category)
    new_highlights = list(highlights)
    added_ids = []
    label_clean = str(label).strip()
    for s, e in positions:
        new_hl = make_highlight(
            s, e, label_clean, "manual", semfield1_list, semfield2_list, pragmatics_list,
            category=category_value,
        )
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


def on_select_highlight(text: str, highlights: list[Highlight], choice: str):
    hid = _selected_id_from_choice(choice)
    if not hid:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    for h in highlights:
        if h["id"] == hid:
            semfield1_value = _alternatives_display_value(h.get("semfield1", []))
            semfield2_value = _set_display_value(h.get("semfield2", []))
            pragmatics_value = _set_display_value(h.get("pragmatics", []))
            category_value = _category_display(h.get("category", ""))
            return h["start"], h["end"], h["label"], semfield1_value, semfield2_value, pragmatics_value, category_value
    return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()


def update_highlight(
    text: str, highlights: list[Highlight], choice: str, start, end, label: str,
    semfield1: str, semfield2: str, pragmatics: str, category: str,
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
    category_value = _category_from_display(category)

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
            new_h["category"] = category_value
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


def delete_highlight(text: str, highlights: list[Highlight], choice: str):
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
            "Найденные линкеры подсвечены оранжевым, вводные слова — зелёным, "
            "ручная разметка — синим. "
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
                        add_category_pos = gr.Dropdown(
                            label="Тип",
                            choices=CATEGORY_CHOICES,
                            value=NO_SEMFIELD,
                        )
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
                        add_category_phrase = gr.Dropdown(
                            label="Тип",
                            choices=CATEGORY_CHOICES,
                            value=NO_SEMFIELD,
                        )
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
                edit_category = gr.Dropdown(
                    label="Тип",
                    choices=CATEGORY_CHOICES,
                    value=NO_SEMFIELD,
                )
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
                add_semfield1_pos, add_semfield2_pos, add_pragmatics_pos, add_category_pos,
            ],
            outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
        )

        add_phrase_btn.click(
            fn=add_by_phrase,
            inputs=[
                state_text, state_highlights, add_phrase, add_label_phrase,
                add_semfield1_phrase, add_semfield2_phrase, add_pragmatics_phrase, add_category_phrase,
            ],
            outputs=[output_html, output_table, hl_select, output_stats, state_highlights, msg_box],
        )

        hl_select.change(
            fn=on_select_highlight,
            inputs=[state_text, state_highlights, hl_select],
            outputs=[edit_start, edit_end, edit_label, edit_semfield1, edit_semfield2, edit_pragmatics, edit_category],
        )

        update_btn.click(
            fn=update_highlight,
            inputs=[
                state_text, state_highlights, hl_select, edit_start, edit_end, edit_label,
                edit_semfield1, edit_semfield2, edit_pragmatics, edit_category,
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
