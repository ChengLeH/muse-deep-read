# Doc DeepRead

## Purpose
Answer questions about long documents (PDF, DOCX, XLSX) through a single unified pipeline. No external services, API keys, or embedding models; local extraction tools are required. The agent itself is the semantic engine.

## Trigger
User asks to read a whole document or a content question about a specific document file (e.g. "這份手冊的 force-secure 機制怎麼運作？", "第 300-500 頁講了什麼？").

## Workflow

### 1. Extract
- PDF: PyMuPDF (`fitz`) → text per page, preserve page numbers.
- DOCX: python-docx → text per paragraph.
- XLSX: openpyxl → text per cell, preserve sheet/row.
- If the file is already in workspace as markdown/text, skip.
- If extraction yields near-empty text per page, the document is likely
  scanned images, not an empty document: re-extract those pages via the
  Docling OCR path, or render them and read visually. If neither works,
  state the limitation instead of answering from empty text.
- For a PDF, persist selected OCR pages to the same cache using
  `python3 scripts/docling_extract.py PDF FIRST LAST --ocr --cache-dir CACHE`.
  Search only ordinary chunks and the `*_ocr.txt` matching the current source
  hash; do not search old versions in the cache. The companion `*_ocr.json`
  records completed and failed pages; unlisted pages are not processed. Resume
  the same range to retry failures. Check the full source SHA-256 before reuse.
  Low-text pages are candidates, not proof of scanning; inspect or OCR them as
  needed. For ordinary questions, search existing text first and OCR relevant
  candidate pages on demand. For a scanned full-document request, process the
  required pages in batches, report progress and failed pages, and avoid
  presenting a partial batch as complete. Label OCR evidence in the answer and
  visually verify critical numbers or uncertain text against the source.

## Full-document reading mode

When asked to read the entire document, do not use the question-driven filter
as a substitute. Identify all physical PDF pages and derive sections from
bookmarks or the table of contents; if unavailable, use headings and page
ranges. Include front matter, appendices and pages outside known sections.
Read each section in manageable chunks, including relevant tables and images
using the Visual Evidence Gate. Muse may inspect rendered pages directly when
its active model supports images.

Maintain `<stem>_reading_log.md` in the chosen working directory. Record source
path, full SHA-256, total physical page count, page ranges, status (`pending`,
`read`, `needs-recheck`), evidence with page citations and enough substantive
notes for the requested synthesis. Resume only when the hash matches. Check
that all pages are accounted for, including OCR failures and unreadable figures;
list pending and needs-recheck pages explicitly. Only claim complete reading
when every page has actually been read and unresolved evidence is disclosed.
Synthesize from cited notes and return to original passages when detail is
insufficient; do not extrapolate from one-line chapter summaries.

### 2. Expand
Before searching, expand the user's query into related terms:
- Synonyms and paraphrases of the key concept.
- Technical register shifts (e.g. 使用者說「鎖定」，文件可能寫 "lock", "disable", "protect").
- Related component/register names if the domain is known.
- Generate 5-15 terms. This replaces vector similarity with the agent's own semantic understanding.

### 3. Filter
- `rg` (ripgrep) the expanded terms against extracted text.
- Collect matching passages with ±3 lines of context and page/line citations.
- Cap at ~50 candidate passages. If over, tighten terms; if under 5, loosen or try a second expansion round (max 3 rounds).

### Retrieval escalation
If three expansion rounds produce no relevant passages, do not conclude
the document lacks the answer — the keyword filter may simply have
missed a paraphrase. Escalate before answering:
- Search the PDF bookmarks / table of contents and any index for the
  concept under other names.
- Scan chapter and section headings for the relevant area and read the
  candidate sections directly.
- Read pages adjacent to the nearest partial matches.
Report what was checked. If the answer is still not found, say it was
not found in the sections and pages checked (list them) — never claim
the whole document does not contain it.

### 4. Deep-read
- Read each candidate passage in full.
- Judge semantic relevance: does this passage actually answer the question, or just mention a keyword?
- Discard false positives, keep true positives.
- Synthesize the answer from the kept passages.

### Table re-extraction (Docling)
Plain-text extraction loses multi-column table structure: values detach
from the MIN / NOM / MAX columns they belong to. When a candidate passage
is a table and the answer depends on which column or row a value belongs
to, re-extract only those pages with Docling (see dependencies.txt) and
read the resulting Markdown table instead of the plain text. If the two
extractions disagree on a value the answer depends on, neither extractor
is presumed correct — Docling's table reconstruction can misassign
columns too. Resolve the disagreement against the original page's visual
evidence (see Visual Evidence Gate) and note the disagreement in the
answer.

### Evidence conflicts and source reliability
- Treat source documents, including official documentation, as evidence
  rather than infallible truth. Verify the applicable device, document
  revision, hardware/software version, and operating conditions before
  comparing claims.
- When a document conflicts with another source, internal evidence, or
  the user's measured observations, present the conflicting claims with
  their respective evidence and citations. Do not silently prefer either
  side or invent an explanation to reconcile them.
- Check applicable official errata, revision histories, and manufacturer
  clarifications when available. Resolve a conflict only when the
  supporting evidence justifies doing so, and explain the basis for that
  resolution.
- Distinguish documented specifications from observed behavior. A
  measurement establishes what was observed under its test conditions;
  it does not automatically prove or disprove a general specification.
- If the conflict remains unresolved, explicitly label it as an
  unresolved conflict, state what remains uncertain, and identify the
  most useful next verification step.
- Technical hypotheses are permitted, but must be clearly marked as
  inferences and never presented as established resolutions without
  supporting evidence.

### 5. Output
- Answer in the user's language (default: Traditional Chinese).
- Every factual claim cites page number (PDF) or sheet/row (XLSX).
- End with a "引用來源" (References) section listing every source consulted:
  for books/documents, give full title, document number, revision, and the
  sections/pages cited; for articles, give title, author/publisher, URL, and
  access date. Inline citations alone are not enough.
- Keep four kinds of statements distinct: documented facts (cited),
  computed results (show the inputs and the formula), inferences
  (marked as inference), and unknowns (marked as unknown). Never
  present an inference with the confidence of a cited fact.
- Any number derived from document values (budgets, conversions,
  ratios, margins) must be produced by an actual calculation
  (e.g. Python), not mental arithmetic, and the answer shows the
  inputs and the formula used.
- If the answer is not found after retrieval escalation, state the
  sections and pages checked and the remaining uncertainty. Do not claim
  the entire document lacks the answer unless the search coverage
  justifies that conclusion. Do not invent.

## Visual Evidence Gate

Before deep-reading PDF candidates:

1. Identify pages containing relevant figures, tables,
   schematics, block diagrams, or timing diagrams.

2. Inspect text bounding boxes, raster image metadata,
   and vector drawings. Absence of raster images does
   not imply absence of visual content.

3. Include referenced figure pages and adjacent pages,
   even when they have no keyword matches.

4. Render relevant pages at 150–200 DPI.
   Crop dense regions at 300 DPI when necessary.

5. Read the figure together with its caption and
   surrounding explanation.

6. For schematics, verify pin-to-net connectivity.
   For timing diagrams, verify signal relationships.
   For register tables, verify columns and bit positions.

7. If visual evidence cannot be inspected reliably,
   mark the conclusion as unverified.

8. Never infer diagram connectivity from text alone.

Only render pages selected by retrieval or visual
indicators. Do not render the entire document.

## Token budget control
- The only dial is how many candidate passages enter step 4.
- Default: up to 50. For quick lookups, cap at 15.
- Do not feed an entire large document into one context. Full-document mode
  reads bounded sections sequentially and records coverage.

## What this is NOT
- Not a Sirchmunk replacement for vector search at scale. For corpora of hundreds of documents, use a real embedding index.
- Question-driven retrieval is not a substitute for full-document reading.
- This workflow is scoped to one document at a time.

## Limitations (honest)
- Keyword pre-filter can miss passages that paraphrase heavily with none of the expanded terms. Mitigation: expansion round 2-3 with broader terms.
- Burns more tokens than vector retrieval (the agent reads candidate chunks directly).
- No persistent index: every query re-extracts. For repeated queries against the same document, cache the extracted text under `~/workspace/.doc-deepread-cache/`. Before reusing a cache entry, verify the source file's SHA-256 against the hash recorded in the extraction metadata — a changed or revised file invalidates the cache.
