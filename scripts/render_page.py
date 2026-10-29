#!/usr/bin/env python3
"""Deep Read - Visual Evidence Gate rendering.

Render PDF pages to PNG so figures / schematics / dense tables can be read
visually instead of from extracted text (text extraction destroys net
connectivity and figure layout). Optionally crop a region for
component-level reading.

Resolution is always expressed in DPI. PDF space is 72 points per inch,
so scale = dpi / 72 (200 DPI ~ 2.78x, 300 DPI ~ 4.17x). A bare scale
factor is never used as a proxy for DPI.

Usage:
    python3 render_page.py <pdf_path> <page_number> <out_png> [dpi]
    python3 render_page.py <pdf_path> <page_number> <out_png> <dpi> \
        crop <x0> <y0> <x1> <y1>

Crop coordinates are PDF points (page.rect coordinate space); the crop is
rendered at the same dpi argument. Defaults follow the gate: 150-200 DPI
full page, 300 DPI for dense crops (pass 300 as the dpi argument).
"""
import sys

import fitz  # PyMuPDF


def main() -> None:
    pdf_path = sys.argv[1]
    page_no = int(sys.argv[2])
    out_png = sys.argv[3]
    dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 200

    doc = fitz.open(pdf_path)
    page = doc[page_no - 1]
    scale = dpi / 72.0
    if len(sys.argv) > 5 and sys.argv[5] == "crop":
        x0, y0, x1, y1 = (float(v) for v in sys.argv[6:10])
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale),
                              clip=fitz.Rect(x0, y0, x1, y1))
    else:
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    pix.save(out_png)
    print(f"wrote {out_png} ({pix.width}x{pix.height}) at {dpi} DPI")


if __name__ == "__main__":
    main()
