"""Loading text/markup from an uploaded file: plain .txt/.docx/.doc fill
the input box (ready for "Анализировать"), while .xml restores previously
saved markup as-is."""

import os
import shutil
import subprocess
from typing import List

import gradio as gr
from docx import Document as DocxDocument

from .highlights import Highlight
from .render import render_state
from .xml_io import parse_xml_annotation


def read_text_file(path: str) -> str:
    """Decode a .txt file, trying UTF-8 first and falling back to the
    legacy Cyrillic encoding (cp1251) common in older Russian text files."""
    with open(path, "rb") as f:
        data = f.read()
    for encoding in ("utf-8-sig", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Не удалось определить кодировку текстового файла.")


def read_docx_file(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)


DOC_SUPPORT = shutil.which("catdoc") is not None

UPLOAD_FILE_TYPES = [".txt", ".docx", ".xml"] + ([".doc"] if DOC_SUPPORT else [])
UPLOAD_LABEL = (
    "Загрузить файл (.txt, .docx, .doc — текст; .xml — готовая разметка)"
    if DOC_SUPPORT else
    "Загрузить файл (.txt, .docx — текст; .xml — готовая разметка). "
    ".doc не поддерживается на этом сервере (нет catdoc) — сохраните как .docx"
)


def read_doc_file(path: str) -> str:
    """Legacy binary .doc via the `catdoc` CLI (python-docx only reads .docx)."""
    try:
        result = subprocess.run(
            ["catdoc", "-w", "-d", "utf-8", path],
            capture_output=True, timeout=30,
        )
    except FileNotFoundError:
        raise ValueError(
            "Не удалось прочитать .doc: утилита catdoc не найдена на сервере. "
            "Сохраните файл в формате .docx и загрузите его снова."
        )
    if result.returncode != 0:
        raise ValueError(
            f"Не удалось прочитать .doc: {result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout.decode("utf-8", "replace")


def load_file(file_path: str, text: str, highlights: List[Highlight]):
    """Handle uploading a file: .txt/.docx/.doc fill the input box with
    plain text (ready for "Анализировать"), .xml restores previously saved
    markup as-is."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".xml":
            with open(file_path, "r", encoding="utf-8") as f:
                xml_text = f.read()
            new_text, new_highlights = parse_xml_annotation(xml_text)
            msg = f"Разметка загружена из XML: {len(new_highlights)} фрагмент(ов)."
        elif ext == ".txt":
            new_text = read_text_file(file_path)
            new_highlights = []
            msg = f"Текст загружен из файла ({len(new_text)} симв.). Нажмите «Анализировать»."
        elif ext == ".docx":
            new_text = read_docx_file(file_path)
            new_highlights = []
            msg = f"Текст загружен из файла ({len(new_text)} симв.). Нажмите «Анализировать»."
        elif ext == ".doc":
            new_text = read_doc_file(file_path)
            new_highlights = []
            msg = f"Текст загружен из файла ({len(new_text)} симв.). Нажмите «Анализировать»."
        else:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                text, highlights, f"Неподдерживаемый формат файла: «{ext}».",
            )
    except ValueError as e:
        return (
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            text, highlights, str(e),
        )
    except Exception as e:
        return (
            gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
            text, highlights, f"Не удалось загрузить файл: {e}",
        )

    html, table, dropdown, stats = render_state(new_text, new_highlights)
    return new_text, html, table, dropdown, stats, new_text, new_highlights, msg
