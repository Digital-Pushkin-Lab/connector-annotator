"""Turning highlight state into what the UI shows: escaped/nested HTML
markup, the Markdown table, breakdown statistics, and the combined
render_state() bundle used after every edit."""

from typing import Dict, List, Set

import gradio as gr

from . import labels
from .highlights import (
    Highlight,
    _alternatives_display_value,
    _set_display_value,
    build_tree,
    choice_str,
)


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
        variant_cls = " manual" if h.get("source") == "manual" else ""
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


def highlights_to_table(highlights: List[Highlight], text: str) -> str:
    """Render highlights as a Markdown table string."""
    if not highlights:
        return labels.TABLE_EMPTY
    rows = []
    rows.append(
        f"| id | start | end | {labels.TABLE_HEADER_CONNECTOR_NAME} | {labels.SEMFIELD1.table_header} | "
        f"{labels.SEMFIELD2.table_header} | {labels.PRAGMATICS.table_header} | source | {labels.TABLE_HEADER_TEXT} |"
    )
    rows.append("|---|---|---|---|---|---|---|---|---|")
    for h in sorted(highlights, key=lambda x: (x["start"], -x["end"])):
        surface = text[h["start"]:h["end"]].replace("|", "\\|").replace("\n", " ")
        rows.append(
            f"| {h.get('group_id', h['id'])} | {h['start']} | {h['end']} | {h['label']} | "
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
        return labels.STATS_EMPTY

    # Several highlight entries share one group_id when a connector is split
    # into multiple parts (e.g. "если" and "то" from "если...то"); count and
    # break down each such connector once, not once per part.
    seen_groups: Set[str] = set()
    unique_highlights: List[Highlight] = []
    for h in highlights:
        gid = h.get("group_id", h["id"])
        if gid in seen_groups:
            continue
        seen_groups.add(gid)
        unique_highlights.append(h)

    tree = build_tree(unique_highlights)
    roots = tree

    total_connectors = len(roots)

    breakdowns = [
        ("semfield1", labels.SEMFIELD1.stats_heading),
        ("semfield2", labels.SEMFIELD2.stats_heading),
        ("pragmatics", labels.PRAGMATICS.stats_heading),
    ]

    lines = [f"**{labels.STATS_TOTAL}:** {total_connectors}"]

    for field, title in breakdowns:
        group_counts: Dict[str, int] = {}
        for root in roots:
            for sf in root.get(field, []):
                group_counts[sf] = group_counts.get(sf, 0) + 1
        if group_counts:
            lines.append("")
            lines.append(f"**{title}:**")
            for sf in sorted(group_counts.keys()):
                lines.append(f"- {sf}: {group_counts[sf]}")
    return "\n".join(lines)


def render_state(text: str, highlights: List[Highlight], selected_id: str = ""):
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
