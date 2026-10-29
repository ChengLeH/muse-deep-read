# Deep Read — complete structure

Semantic document retrieval without external services. The agent itself is
the semantic engine: extract text, expand the query, filter candidates with
ripgrep, then deep-read only the surviving passages.

## Layout

| File | What it is |
|---|---|
| `SKILL.md` | The skill itself: the 5-step pipeline (Extract → Expand → Filter → Deep-read → Output), the Visual Evidence Gate for schematic/figure pages, and the token budget rules and full-document coverage log. |
| `skill.yaml` | Skill registration metadata (name, description, availability). |
| `dependencies.txt` | Python + system dependencies with the exact versions in use, plus environment workarounds (TMPDIR, NO_PROXY) for docling. |
| `scripts/extract_pdf_text.py` | Step 1: PyMuPDF full-text extraction into page-marked chunks. |
| `scripts/docling_extract.py` | Re-extract tables or persist resumable OCR pages to searchable cache files. |
| `scripts/render_page.py` | Visual Evidence Gate: render pages (and high-scale crops) to PNG for visual reading. |
| `benchmarks/2026-10-21-extractors.md` | Extractor benchmark: PyMuPDF vs PyMuPDF4LLM vs Docling on three real documents (raw timings, memory, correctness notes). |

PyMuPDF4LLM was evaluated on 2026-10-21 and not adopted — see
`benchmarks/2026-10-21-extractors.md`. The default extractor remains
PyMuPDF, with Docling on demand for specification tables.

## Pipeline in one paragraph

Extract once per document and cache the chunks. For each question: expand
the user's terms into synonyms / part numbers / register names, filter the
chunks with `rg` to a handful of candidate passages, deep-read only those,
and answer with page-level citations plus a References list. If a needed
page is visual (schematic, figure, dense table), render it and read the
image — never infer connectivity from extracted text.

Exported from the VM on 2026-10-21 (skill state after the 2026-10-19
revisions: Visual Evidence Gate + References-list rule).

For scanned pages, run `python3 scripts/docling_extract.py PDF FIRST LAST --ocr --cache-dir CACHE` and search the resulting `*_ocr.txt` alongside text chunks. The companion JSON records per-page status and allows retries. Full-document reading uses the coverage log described in SKILL.md.
