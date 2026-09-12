"""Serialize markup to the project's XML schema and parse it back, so a
previously saved annotation file can be exported and later reloaded."""

import os
import uuid
import xml.dom.minidom
from datetime import datetime
from xml.etree import ElementTree as ET

from .config import PROJECT_ROOT
from .highlights import (
    Highlight,
    _alternatives_str,
    _normalize_alternatives,
    _normalize_set,
    _set_str,
    build_tree,
    validate_highlights,
)


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
        el.set("id", str(node.get("group_id", node["id"])))
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
    path = os.path.join(PROJECT_ROOT, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_str)
    return path, f"Сохранено: {filename}"


def parse_xml_annotation(xml_text: str) -> tuple[str, list[Highlight]]:
    """Parse an XML document produced by `build_xml` (or matching its
    schema) back into (text, highlights), so previously saved markup can be
    reloaded and further edited. All parts of one saved connector share the
    `id` attribute the exporter wrote (see `build_xml`); that value becomes
    `group_id`, while each part still gets a fresh internal `id`."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"Некорректный XML: {e}")

    if root.tag != "linker-annotation":
        raise ValueError("Файл не является разметкой коннекторов (нет тега <linker-annotation>).")

    text_el = root.find("text")
    if text_el is None:
        raise ValueError("В файле отсутствует тег <text> с исходным текстом.")
    text = text_el.text or ""

    highlights: list[Highlight] = []

    def walk(container: ET.Element) -> None:
        for span in container.findall("span"):
            try:
                start = int(span.get("start"))
                end = int(span.get("end"))
            except (TypeError, ValueError):
                raise ValueError("Некорректные границы фрагмента в <span>.")
            highlights.append({
                "id": str(uuid.uuid4())[:8],
                "group_id": span.get("id") or str(uuid.uuid4())[:8],
                "start": start,
                "end": end,
                "label": span.get("label", ""),
                "source": span.get("source", "auto"),
                "semfield1": _normalize_alternatives(span.get("semfield1", "")),
                "semfield2": _normalize_set(span.get("semfield2", "")),
                "pragmatics": _normalize_set(span.get("pragmatics", "")),
                "category": span.get("category", ""),
            })
            walk(span)

    spans_el = root.find("spans")
    if spans_el is not None:
        walk(spans_el)

    for h in highlights:
        if not (0 <= h["start"] < h["end"] <= len(text)):
            raise ValueError(f"Разметка выходит за границы текста: [{h['start']}-{h['end']}].")

    ok, msg = validate_highlights(highlights)
    if not ok:
        raise ValueError(f"Разметка в файле некорректна: {msg}")

    return text, highlights
