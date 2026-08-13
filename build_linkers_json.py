#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build nested_linkers.json from Коннекторы_правка.xlsx.

Rerun this script whenever the spreadsheet changes:

    python3 build_linkers_json.py

Source sheets:
  * "Исходные" - original connector list with revised characteristics
  * "Доп"      - new connectors added during the revision

Columns: Союз | POS | other_POS | semfield1 | semfield2 | ПУ | Atoms
  * POS / other_POS are dropped entirely (unreliable, not used downstream).
  * A row is dropped if its "Союз" cell is prefixed with "DEL" or filled
    orange (FFFFC000) - these were marked for removal by the reviewer.
  * semfield1: ';'-separated alternatives (a connector's primary meaning
    may be ambiguous between two or more readings).
  * semfield2 / ПУ (pragmatics): ','-separated sets that always accompany
    whatever semfield1 reading is chosen.
  * Atoms: ','-separated list of component connector keys that may be
    technically highlighted inside this connector.
  * Duplicate connector keys (same spelling appearing more than once,
    across or within sheets) are merged by unioning their semfield1 /
    semfield2 / pragmatics / atoms lists (order preserved, deduplicated).
  * "…" (ellipsis, U+2026) in a connector key is normalized to the
    three-dot "..." marker the app uses to detect discontinuous
    connectors (e.g. "а как... тут и").
"""

import json
import os

import openpyxl

XLSX_PATH = os.path.join(os.path.dirname(__file__), "Коннекторы_правка.xlsx")
JSON_PATH = os.path.join(os.path.dirname(__file__), "nested_linkers.json")

SHEETS = ["Исходные", "Доп"]
DEL_FILL_RGB = "FFFFC000"


def is_deleted(cell) -> bool:
    value = cell.value
    if value and str(value).strip().upper().startswith("DEL"):
        return True
    fill = cell.fill
    if fill and fill.fgColor and fill.fgColor.rgb == DEL_FILL_RGB:
        return True
    return False


def split_alternatives(raw) -> list:
    if not raw or not str(raw).strip():
        return []
    return [p.strip() for p in str(raw).split(";") if p.strip()]


def split_set(raw) -> list:
    if not raw or not str(raw).strip():
        return []
    return [p.strip() for p in str(raw).split(",") if p.strip()]


def merge_unique(existing: list, new: list) -> list:
    for item in new:
        if item not in existing:
            existing.append(item)
    return existing


def normalize_key(raw: str) -> str:
    return str(raw).strip().replace("…", "...")


def build_connectors() -> dict:
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    connectors = {}

    for sheet_name in SHEETS:
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2):
            key_cell = row[0]
            if key_cell.value is None or not str(key_cell.value).strip():
                continue
            if is_deleted(key_cell):
                continue

            key = normalize_key(key_cell.value)
            semfield1 = split_alternatives(row[3].value)
            semfield2 = split_set(row[4].value)
            pragmatics = split_set(row[5].value)
            atoms = split_set(row[6].value)

            if key not in connectors:
                connectors[key] = {
                    "semfield1": list(semfield1),
                    "semfield2": list(semfield2),
                    "pragmatics": list(pragmatics),
                    "atoms": list(atoms),
                }
            else:
                entry = connectors[key]
                merge_unique(entry["semfield1"], semfield1)
                merge_unique(entry["semfield2"], semfield2)
                merge_unique(entry["pragmatics"], pragmatics)
                merge_unique(entry["atoms"], atoms)

    return dict(sorted(connectors.items(), key=lambda kv: kv[0]))


def main():
    connectors = build_connectors()
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(connectors, f, ensure_ascii=False, indent=2, sort_keys=False)
    print(f"Wrote {len(connectors)} connectors to {JSON_PATH}")


if __name__ == "__main__":
    main()
