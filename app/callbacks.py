"""Gradio event-handler callbacks: run analysis, and add/select/edit/delete
highlights in response to UI actions."""

import gradio as gr

from .config import PRAGMATICS_MAP, SEMFIELD1_MAP, SEMFIELD2_MAP, _category_display, _category_from_display
from .engine import CHECKER, NLP, PATTERNS_BY_TYPE, dedupe_spans, extract_spans, parse_sentences
from .highlights import (
    Highlight,
    _alternatives_display_value,
    _normalize_alternatives,
    _normalize_set,
    _selected_id_from_choice,
    _set_display_value,
    find_phrase_positions,
    make_highlight,
    validate_highlights,
)
from .render import render_state


def build_highlights(text: str) -> list[Highlight]:
    """Run the linker_extraction analysis pipeline over `text` and return
    the resulting highlights. Shared by the single-text UI flow and the
    batch-folder flow (app.batch) so both stay in sync."""
    parsed_sentences, _word_count = parse_sentences(text, NLP)
    spans = extract_spans(parsed_sentences, CHECKER, PATTERNS_BY_TYPE)
    spans = dedupe_spans(spans)
    return [
        make_highlight(
            sp["start"], sp["end"], sp["surface"], "auto",
            SEMFIELD1_MAP.get(sp["surface"], []),
            SEMFIELD2_MAP.get(sp["surface"], []),
            PRAGMATICS_MAP.get(sp["surface"], []),
            category=sp["type"],
            # все части одного (в т.ч. разрывного) коннектора, например
            # "если" и "то" из "если...то", получают общий group_id
            group_id=sp.get("group_id"),
        )
        for sp in spans
    ]


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
    highlights = build_highlights(text)
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
