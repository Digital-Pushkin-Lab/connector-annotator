"""Turning highlight state into what the UI shows: escaped/nested HTML
markup, the Markdown table, breakdown statistics, and the combined
render_state() bundle used after every edit."""

import gradio as gr

from .config import _category_display
from .highlights import (
    Highlight,
    _alternatives_display_value,
    _set_display_value,
    build_tree,
    choice_str,
)


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
            f"| {h.get('group_id', h['id'])} | {h['start']} | {h['end']} | {h['label']} | "
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
