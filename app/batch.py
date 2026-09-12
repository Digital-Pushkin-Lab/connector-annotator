"""Batch folder processing: run the same analysis pipeline used for a
single text over every .txt/.docx/.doc file in an uploaded folder and
produce one XML per file. Anything else in the folder is skipped. Yields
progress after each file so the UI console/progress bar update live, and
bundles all results into one ZIP for a single "download all".

Stopping is cooperative (a flag checked between files), not Gradio's
built-in `cancels=`: in this Gradio version, cancelling a generator event
that owns an open SSE stream can crash that connection ("404: Session not
found" mid-stream) once the browser reconnects. Polling a flag avoids that
code path entirely and, as a bonus, lets a stopped run still finish
cleanly -- log a proper message and zip whatever was already processed."""

import os
import tempfile
import threading
import zipfile
from typing import List, Optional, Tuple

from .callbacks import build_highlights
from .file_io import DOC_SUPPORT, read_doc_file, read_docx_file, read_text_file
from .xml_io import build_xml

SUPPORTED_EXTENSIONS = (".txt", ".docx", ".doc")

BATCH_UPLOAD_LABEL = (
    "Загрузите папку с файлами (.txt, .docx"
    + (", .doc" if DOC_SUPPORT else "")
    + ") — остальные форматы будут пропущены"
    + ("" if DOC_SUPPORT else "; .doc не поддерживается на этом сервере (нет catdoc)")
)

# Points at the currently running process_folder()'s own Event (or None
# when idle). A fresh Event per run -- rather than clearing one shared
# Event at the top of process_folder -- avoids a race where a stop click
# lands between "clear" and the loop's first check and gets wiped out.
# Single global (not per-session): this app runs as one local, single-user
# instance, so per-session tracking would be needless complexity.
_current_stop_event: Optional[threading.Event] = None


def request_stop() -> None:
    """Wired to the confirmed "Остановить" click. The running
    `process_folder` generator notices this before its next file and stops
    itself gracefully. A no-op if nothing is running."""
    if _current_stop_event is not None:
        _current_stop_event.set()


def _read_any(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return read_text_file(path)
    if ext == ".docx":
        return read_docx_file(path)
    if ext == ".doc":
        return read_doc_file(path)
    raise ValueError(f"Неподдерживаемый формат: {ext}")


def _unique_output_path(out_dir: str, stem: str) -> str:
    """Avoid collisions when two input files share a stem (e.g. report.txt
    and report.docx would both want report.xml)."""
    candidate = os.path.join(out_dir, f"{stem}.xml")
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(out_dir, f"{stem}_{n}.xml")
        n += 1
    return candidate


def _build_zip(out_dir: str, output_files: List[str]) -> str:
    zip_path = os.path.join(out_dir, "results.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in output_files:
            zf.write(path, arcname=os.path.basename(path))
    return zip_path


def _progress_html(done: int, total: int, label: str) -> str:
    pct = int(done / total * 100) if total else 0
    return (
        f'<div class="progress-outer"><div class="progress-inner" style="width:{pct}%;"></div></div>'
        f'<div class="progress-label">{label}: {done}/{total} ({pct}%)</div>'
    )


def process_folder(file_paths: List[str]):
    """Generator: yields (log_text, output_files, zip_path, progress_html)
    after every file, so the console and progress bar update live even on
    a large folder. `zip_path` stays None until everything is done (or the
    run is stopped)."""
    global _current_stop_event
    stop_event = threading.Event()
    _current_stop_event = stop_event

    if not file_paths:
        yield "Папка не выбрана или пуста.", [], None, _progress_html(0, 0, "Нет файлов")
        return

    out_dir = tempfile.mkdtemp(prefix="linker_batch_")
    log_lines: List[str] = []
    output_files: List[str] = []
    processed = skipped = failed = 0
    total = len(file_paths)
    stopped = False

    def emit(done: int, label: str = "Обработка") -> Tuple[str, List[str], Optional[str], str]:
        return "\n".join(log_lines), list(output_files), None, _progress_html(done, total, label)

    log_lines.append(f"Найдено файлов: {total}.")
    yield emit(0)

    for i, path in enumerate(sorted(file_paths, key=lambda p: os.path.basename(p).lower()), start=1):
        if stop_event.is_set():
            stopped = True
            log_lines.append("⏹ Остановлено пользователем.")
            yield emit(i - 1, "Остановлено")
            break

        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()

        if ext not in SUPPORTED_EXTENSIONS:
            skipped += 1
            log_lines.append(f"— Пропущено: {name} (не .txt/.docx/.doc)")
            yield emit(i)
            continue

        if ext == ".doc" and not DOC_SUPPORT:
            skipped += 1
            log_lines.append(f"— Пропущено: {name} (.doc не поддерживается на этом сервере)")
            yield emit(i)
            continue

        try:
            text = _read_any(path)
            highlights = build_highlights(text)
            xml_str = build_xml(text, highlights)
            out_path = _unique_output_path(out_dir, os.path.splitext(name)[0])
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(xml_str)
            output_files.append(out_path)
            processed += 1
            log_lines.append(f"✓ Обработано: {name} ({len(highlights)} размет., {len(text)} симв.)")
        except Exception as e:
            failed += 1
            log_lines.append(f"✗ Ошибка: {name}: {e}")
        yield emit(i)

    if not stopped:
        log_lines.append(f"Готово. Обработано: {processed}, пропущено: {skipped}, ошибок: {failed}.")
    zip_path = _build_zip(out_dir, output_files) if output_files else None
    final_label = "Остановлено" if stopped else "Готово"
    yield "\n".join(log_lines), list(output_files), zip_path, _progress_html(
        processed + skipped + failed, total, final_label
    )
