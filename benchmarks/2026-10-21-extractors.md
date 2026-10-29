# Extractor benchmark — 2026-10-21

Question: should Deep Read's default Step 1 extractor stay PyMuPDF, move
to PyMuPDF4LLM, or change Docling's role? Decided by measurement on real
documents, not by vendor claims.

## Environment and method

- VM (Linux, CPU only), Python 3.12.3
- PyMuPDF 1.28.2 · PyMuPDF4LLM 1.28.2 (installed for this evaluation
  only) · Docling 2.140.0
- Each (document, extractor) pair ran in a fresh subprocess.
  "wall" = subprocess wall time; "seconds" = in-process extraction
  time; "maxrss" = runner process peak RSS (ru_maxrss).
- Docling converted page-by-page (same as scripts/docling_extract.py);
  its times include model loading.
- Command: `python3 deepread_benchmark/bench.py` (VM workspace;
  raw outputs and summary.json under `deepread_benchmark/outputs/`).

## Test documents

| Case | Document | Pages | Content |
|---|---|---|---|
| dp83826e_tables | DP83826E datasheet (SNLS647I) | 22–24 | Timing diagrams, typical characteristics, detailed description. **Not spec tables** — the page selection missed §7.6, so this case is not evidence for table correctness. |
| f28p65x_adc | TMS320F28P65x datasheet (SPRSP69D) | 180–182 | ADC specification tables |
| controlcard_sch | TMDSCNCD28P65X schematic (SPRR478A) | 4–5 | Schematic sheets (control case) |

## Raw results

| Case | Extractor | seconds | wall (s) | chars | maxrss (MB) |
|---|---|---|---|---|---|
| dp83826e_tables | PyMuPDF | 0.47 | 0.60 | 4,332 | 53.5 |
| dp83826e_tables | PyMuPDF4LLM | 10.69 | 11.22 | 4,959 | 577.3 |
| dp83826e_tables | Docling | 63.94 | 70.69 | 3,632 | 1,795.1 |
| f28p65x_adc | PyMuPDF | 0.60 | 0.73 | 6,224 | 54.2 |
| f28p65x_adc | PyMuPDF4LLM | 7.05 | 7.36 | 7,055 | 418.9 |
| f28p65x_adc | Docling | 80.66 | 84.37 | 9,478 | 1,959.4 |
| controlcard_sch | PyMuPDF | 0.41 | 0.55 | 13,825 | 55.4 |
| controlcard_sch | PyMuPDF4LLM | 9.71 | 10.50 | 14,434 | 461.6 |
| controlcard_sch | Docling | 86.69 | 93.13 | 89 | 2,221.0 |

Ratios (wall basis, recomputed from the raw numbers above):
PyMuPDF4LLM / PyMuPDF = **10.1–19.1×**; Docling / PyMuPDF4LLM =
**6.3–11.5×**. (Two earlier ratio summaries — 12–18×/6–9× and
10.6–18.7× — did not reproduce from the raw data and are withdrawn;
the raw numbers are the record.)

## Correctness observations

Ground truth for the F28P65x probe was established by word-coordinate
row reconstruction on PDF p.181: two "Sample window duration" tables —
AIO 320 / AGPIO 405 (ns), and AIO 320 / AGPIO 320 (ns).

- **Docling**: reproduced both tables exactly (values and row labels);
  cleanest table output of the three.
- **PyMuPDF4LLM**: values correct and placed in table cells, but
  parameter-label text is garbled in places — e.g. "Sample window
  duration (set by ACQPS and PERx.SYSCLK)" came out as fragments like
  "Sl id dti t b ACQPS d" / "ampe wnow uraon (se y an…)". Dropped
  characters in labels break the keyword Filter step's recall.
- **PyMuPDF**: values present but detached from their rows (320 / 405
  as bare lines) — the known limitation the Docling re-extraction
  branch exists to cover.
- **Schematic sheets**: Docling returned 89 chars (pages treated as
  images; no OCR in the standard pipeline). PyMuPDF and PyMuPDF4LLM
  returned ~13.8k / ~14.4k chars of net and component labels.
- Figure pages (DP83826E): PyMuPDF4LLM wraps figure text in
  picture-text blocks with bold captions; Docling emits image
  placeholders plus captions; PyMuPDF inlines figure text
  unstructured.

## Decision

- Default extractor stays **PyMuPDF** (fast, ~54 MB, complete text for
  the Filter step).
- **Docling** stays on-demand for specification tables.
- **PyMuPDF4LLM is not adopted** and is not added to
  dependencies.txt: label garbling hurts Filter recall, at
  10.1–19.1× the time and roughly 8–11× the memory of PyMuPDF.

## Limitations of this benchmark

- One run per combination; no repetitions or medians.
- Docling's times include ~60 s of model loading per subprocess, so
  its ratios shrink for larger page ranges.
- Correctness was judged on the probed rows and pages listed above,
  not exhaustively.
