"""Gradio interface for highlighting Russian linker words in text.
(colab-compatible branch: targets Python 3.9+ / Colab's Python 3.12.13,
uses PEP 585 built-in generics instead of typing.List/Dict/Set/Tuple.)

Package layout:
  * config       -- CSS, file paths, semfield/pragmatics/category lookups
  * engine       -- linker_extraction setup (stanza pipeline, checker, patterns)
  * highlights   -- the highlight data model (create/validate/search/tree)
  * render       -- highlight state -> HTML / table / stats for the UI
  * xml_io       -- XML export and re-import of saved markup
  * file_io      -- loading .txt/.docx/.doc/.xml uploads
  * callbacks    -- Gradio event handlers (analyze/add/edit/delete)
  * batch        -- batch folder processing (multiple files -> multiple XMLs)
  * ui           -- gr.Blocks layout wiring everything together
"""

import os

# Remove ALL_PROXY and all_proxy BEFORE anything else in this package
# imports gradio: gradio pulls in httpx, whose client init raises on an
# unsupported proxy scheme (e.g. a local `socks://` proxy). This must run
# before any submodule below gets a chance to `import gradio`, which is why
# it lives at the top of the package's __init__.
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
