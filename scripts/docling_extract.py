#!/usr/bin/env python3
"""Extract selected PDF pages with Docling; optionally persist searchable OCR.

Usage: docling_extract.py PDF FIRST LAST [--ocr] [--cache-dir DIRECTORY]
Without --cache-dir the original Markdown-to-stdout behavior is preserved.
With --ocr and --cache-dir, completed pages are saved and can be resumed.
"""
import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


def sha256_of(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.deepread-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def build_converter(use_ocr):
    from docling.document_converter import DocumentConverter
    if not use_ocr:
        return DocumentConverter()
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import PdfFormatOption
    pipeline = PdfPipelineOptions()
    pipeline.do_ocr = True
    pipeline.ocr_options = RapidOcrOptions()
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)})


def publish_cache(state, state_path, text_path):
    # State is the source of truth; regenerate searchable output after interruptions.
    atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    parts = [f'\n===== {state["stem"]} PDFpage {page} [OCR] =====\n{record["text"]}\n'
             for page, record in sorted(state['pages'].items(), key=lambda item: int(item[0]))
             if record['status'] == 'complete']
    atomic_write(text_path, ''.join(parts))


def converted_text(result, require_text=True):
    status = getattr(result, 'status', None)
    if status is None or getattr(status, 'name', str(status)).upper() != 'SUCCESS':
        raise RuntimeError(f'Docling conversion status: {status}')
    text = result.document.export_to_markdown()
    if require_text and not text.strip():
        raise ValueError('No text returned; page requires inspection')
    return text


def backfill(pdf, first, last, cache_dir, converter):
    digest = sha256_of(pdf)
    stem = pdf.stem.lower().replace('-', '_')
    base = f'{stem}_{digest[:8]}_ocr'
    cache_dir.mkdir(parents=True, exist_ok=True)
    with (cache_dir / (base + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if sha256_of(pdf) != digest:
            raise RuntimeError('Source PDF changed while waiting for the cache lock; retry')
        return _backfill_locked(pdf, first, last, cache_dir, converter, digest, stem, base)


def _backfill_locked(pdf, first, last, cache_dir, converter, digest, stem, base):
    state_path, text_path = cache_dir / (base + '.json'), cache_dir / (base + '.txt')
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('sha256') != digest or state.get('stem') != stem:
            raise ValueError('OCR cache identity mismatch; choose another cache directory')
    else:
        state = {'sha256': digest, 'source_path': str(pdf.resolve()), 'stem': stem, 'pages': {}}
    publish_cache(state, state_path, text_path)
    failed = []
    for page in range(first, last + 1):
        if state['pages'].get(str(page), {}).get('status') == 'complete':
            continue
        try:
            result = converter.convert(str(pdf), page_range=(page, page))
            text = converted_text(result)
            if sha256_of(pdf) != digest:
                raise RuntimeError('Source PDF changed during OCR; retry using the current source')
            state['pages'][str(page)] = {'status': 'complete', 'text': text}
        except Exception as exc:
            if sha256_of(pdf) != digest:
                raise RuntimeError('Source PDF changed during OCR; no result saved for this page') from exc
            state['pages'][str(page)] = {'status': 'failed', 'error': str(exc)}
            failed.append(page)
        publish_cache(state, state_path, text_path)
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('first', type=int)
    parser.add_argument('last', type=int)
    parser.add_argument('--ocr', action='store_true')
    parser.add_argument('--cache-dir', type=Path)
    args = parser.parse_args()
    if args.first < 1 or args.last < args.first:
        parser.error('page range must satisfy 1 <= first <= last')
    if args.cache_dir and not args.ocr:
        parser.error('--cache-dir requires --ocr')
    if args.cache_dir:
        import fitz
        with fitz.open(args.pdf) as document:
            if args.last > document.page_count:
                parser.error(f'last page exceeds PDF page count ({document.page_count})')
    converter = build_converter(args.ocr)
    if args.cache_dir:
        failed = backfill(args.pdf, args.first, args.last, args.cache_dir, converter)
        print(f'OCR cache: {args.cache_dir}; failed pages: {failed}')
        if failed:
            sys.exit(1)
    else:
        for page in range(args.first, args.last + 1):
            result = converter.convert(str(args.pdf), page_range=(page, page))
            print(f'\n===== PAGE {page} (Docling) =====')
            print(converted_text(result, require_text=args.ocr))


if __name__ == '__main__':
    main()
