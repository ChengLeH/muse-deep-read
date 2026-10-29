import importlib.util
import json
import multiprocessing
import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('docling_extract', Path(__file__).resolve().parents[1] / 'scripts' / 'docling_extract.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Converter:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.calls = []

    def convert(self, path, page_range):
        page = page_range[0]
        self.calls.append(page)
        if page in self.failures:
            raise RuntimeError('page failed')
        return SimpleNamespace(status=SimpleNamespace(name='SUCCESS'), document=SimpleNamespace(export_to_markdown=lambda: f'unique text page {page}'))


def run_worker(pdf, cache, page, start):
    class SlowConverter(Converter):
        def convert(self, path, page_range):
            time.sleep(0.15)
            return super().convert(path, page_range)
    start.wait()
    mod.backfill(Path(pdf), page, page, Path(cache), SlowConverter())


class CacheTests(unittest.TestCase):
    def test_retry_search_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'Test-Book.pdf'
            pdf.write_bytes(b'fixture')
            cache = root / 'cache'
            converter = Converter({2})
            self.assertEqual(mod.backfill(pdf, 1, 3, cache, converter), [2])
            state_path = next(cache.glob('*_ocr.json'))
            text_path = next(cache.glob('*_ocr.txt'))
            state = json.loads(state_path.read_text())
            self.assertEqual(state['pages']['2']['status'], 'failed')
            self.assertIn('PDFpage 1 [OCR]', text_path.read_text())
            self.assertNotIn('unique text page 2', text_path.read_text())
            converter = Converter()
            self.assertEqual(mod.backfill(pdf, 1, 3, cache, converter), [])
            self.assertEqual(converter.calls, [2])
            text = text_path.read_text()
            self.assertIn('unique text page 2', text)
            self.assertEqual(text.count('PDFpage 2 [OCR]'), 1)
            text_path.unlink()
            mod.backfill(pdf, 1, 3, cache, converter)
            self.assertEqual(text_path.read_text(), text)

    def test_concurrent_processes_do_not_lose_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'book.pdf'
            pdf.write_bytes(b'fixture')
            ctx = multiprocessing.get_context('fork')
            start = ctx.Event()
            processes = [ctx.Process(target=run_worker, args=(str(pdf), str(root / 'cache'), page, start)) for page in (1, 2)]
            for process in processes:
                process.start()
            start.set()
            for process in processes:
                process.join(10)
                self.assertEqual(process.exitcode, 0)
            state = json.loads(next((root / 'cache').glob('*_ocr.json')).read_text())
            self.assertEqual(set(state['pages']), {'1', '2'})
            text = next((root / 'cache').glob('*_ocr.txt')).read_text()
            self.assertIn('unique text page 1', text)
            self.assertIn('unique text page 2', text)

    def test_changed_document_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'a.pdf'
            pdf.write_bytes(b'one')
            mod.backfill(pdf, 1, 1, root / 'cache', Converter())
            pdf.write_bytes(b'two')
            converter = Converter()
            mod.backfill(pdf, 1, 1, root / 'cache', converter)
            self.assertEqual(converter.calls, [1])
            self.assertEqual(len(list((root / 'cache').glob('*_ocr.txt'))), 2)

    def test_source_change_during_conversion_is_not_cached(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'a.pdf'
            pdf.write_bytes(b'original')
            class ChangingConverter(Converter):
                def convert(self, path, page_range):
                    result = super().convert(path, page_range)
                    pdf.write_bytes(b'changed')
                    return result
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                mod.backfill(pdf, 1, 1, root / 'cache', ChangingConverter())
            self.assertNotIn('unique text', next((root / 'cache').glob('*_ocr.txt')).read_text())

    def test_incomplete_conversion_not_marked_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'a.pdf'
            pdf.write_bytes(b'fixture')
            converter = SimpleNamespace(convert=lambda *a, **k: SimpleNamespace(status=SimpleNamespace(name='PARTIAL_SUCCESS'), document=SimpleNamespace(export_to_markdown=lambda: 'partial')))
            self.assertEqual(mod.backfill(pdf, 1, 1, root / 'cache', converter), [1])
            self.assertNotIn('partial', next((root / 'cache').glob('*_ocr.txt')).read_text())


if __name__ == '__main__':
    unittest.main()
