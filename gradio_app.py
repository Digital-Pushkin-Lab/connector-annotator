#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gradio interface for highlighting Russian linker words in text.

This branch is optimized for Google Colab (Python 3.9+ / Colab's Python
3.12.13): the `app` package uses PEP 585 built-in generics (list[str],
dict[str, int], ...) instead of typing.List/Dict. See README.md for
install/launch instructions on Colab.

Original features:
  * detection via linker_extraction (stanza dependency parsing +
    rule-based scoring); semfields/pragmatics looked up from
    linker_extraction/data/linkers.csv, keyed by matched surface form
  * atoms of a matched linker are highlighted as nested spans

Expanded features:
  * modify/delete existing highlights
  * add manual highlights by exact character positions or by phrase
  * export the resulting markup as an XML document
  * load text from .txt/.docx/.doc, or restore markup from a saved .xml
  * batch-process a whole folder of files into one XML per file

Implementation lives in the `app` package (config/engine/highlights/render/
xml_io/file_io/callbacks/batch/ui); this file is just the launch entry point.
"""

from app.ui import main

if __name__ == "__main__":
    main()
