"""Idempotent markdown section upserts for EVIDENCE.md / FINDINGS.md.

Replaces the block from a ``## <title>`` heading up to the next ``## `` heading
(or end of file), or appends it if absent. Order-independent, so multiple
writers (validation, forecasting, ...) can each own a section without clobbering
the others.
"""
from __future__ import annotations

import re
from pathlib import Path


def upsert_section(path: Path, title: str, body_md: str, doc_header: str = "") -> None:
    """Insert or replace the ``## {title}`` section in ``path`` with ``body_md``.

    ``body_md`` should be the full section including its ``## {title}`` heading.
    ``doc_header`` (e.g. ``# gridpulse EVIDENCE``) is written once if the file is new.
    """
    body_md = body_md.rstrip() + "\n"
    if not path.exists():
        head = (doc_header.rstrip() + "\n\n") if doc_header else ""
        path.write_text(head + body_md)
        return

    text = path.read_text()
    # Match "## <title>" up to the next "## " at line start, or EOF.
    pattern = re.compile(
        r"^##[ \t]+" + re.escape(title) + r"[ \t]*$.*?(?=^##[ \t]|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    if pattern.search(text):
        new = pattern.sub(body_md.rstrip() + "\n\n", text)
    else:
        new = text.rstrip() + "\n\n" + body_md
    path.write_text(new.rstrip() + "\n")
