#!/usr/bin/env python3
"""Deep Read - Step 1 (Extract).

Extract the full text of a PDF into chunked plain-text files so the Filter
step (rg) can search them. Each chunk carries explicit page markers so any
hit can be traced back to its PDF page number.

Cache identity: output names carry a short SHA-256 prefix of the source
file, and a JSON sidecar records the source path, full hash, extractor
version and parameters. Same-name PDFs from different folders or
different revisions can no longer overwrite each other, and a cached
extraction can be verified against its source before reuse.

Usage:
    python3 extract_pdf_text.py <pdf_path> <out_dir> [chunk_pages]

Output:
    <out_dir>/<docname>_<hash8>_p<start>-<end>.txt   (one file per chunk)
    <out_dir>/<docname>_<hash8>.meta.json            (cache identity)
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF

# A page with fewer extracted characters than this is reported as a
# low-text candidate (possibly scanned, possibly a figure/schematic or
# sparse page). Per-page, never averaged over the document.
SCANNED_CHARS_PER_PAGE = 50


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    chunk = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    out_dir.mkdir(parents=True, exist_ok=True)

    digest = sha256_of(pdf_path)
    hash8 = digest[:8]

    doc = fitz.open(pdf_path)
    stem = pdf_path.stem.lower().replace("-", "_")
    page_chars: list[int] = []
    for start in range(0, doc.page_count, chunk):
        end = min(start + chunk, doc.page_count)
        out = out_dir / f"{stem}_{hash8}_p{start + 1}-{end}.txt"
        with out.open("w", encoding="utf-8") as fh:
            for pno in range(start, end):
                text = doc[pno].get_text()
                page_chars.append(len(text))
                fh.write(f"\n===== {stem} PDFpage {pno + 1} =====\n")
                fh.write(text)
        print(f"wrote {out} ({end - start} pages)")

    # Per-page low-text detection: a document-wide average would hide a
    # few scanned pages inside a mostly-text document. Low text is only a
    # candidacy signal, never a verdict - figure and schematic pages are
    # legitimately sparse.
    low_text_pages = [pno + 1 for pno, n in enumerate(page_chars)
                      if n < SCANNED_CHARS_PER_PAGE]

    meta = {
        "source_path": str(pdf_path.resolve()),
        "sha256": digest,
        "size_bytes": pdf_path.stat().st_size,
        "page_count": doc.page_count,
        "extractor": f"PyMuPDF {fitz.__version__}",
        "chunk_pages": chunk,
        "low_text_candidate_pages": low_text_pages,
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    meta_path = out_dir / f"{stem}_{hash8}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"wrote {meta_path}")
    print(f"total pages: {doc.page_count}")

    if doc.page_count and len(low_text_pages) == doc.page_count:
        print(
            f"WARNING: every page has < {SCANNED_CHARS_PER_PAGE} chars of "
            "embedded text - this document is likely scanned images. Use "
            "the Docling OCR path (docling_extract.py --ocr) or render "
            "pages and read them visually.",
            file=sys.stderr,
        )
    elif low_text_pages:
        print(
            f"NOTE: low-text candidate page(s): {low_text_pages} "
            f"(< {SCANNED_CHARS_PER_PAGE} chars each). A low character "
            "count can mean a scanned image, a figure/schematic page, or "
            "a genuinely sparse page - inspect these pages visually or "
            "via the OCR path before treating them as empty. They are "
            "candidates, not confirmed scans.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
