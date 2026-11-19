"""
Tests für den ThumbnailLoadWorker (AGENTS.md Abschnitt 12).

Prüft, dass Thumbnails asynchron und ohne GUI-Blockierung geladen
und als PNG-Bytes zurückgeliefert werden.
"""

import os
import tempfile
import unittest

from PyQt6.QtCore import QCoreApplication, QThreadPool, QEventLoop

from src.workers.thumbnail_load_worker import ThumbnailLoadWorker


def _make_test_image(path, size=(400, 300)):
	"""Erzeugt ein einfaches PNG-Testbild."""
	from PIL import Image
	img = Image.new("RGB", size, color=(120, 200, 90))
	img.save(path, format="PNG")


class ThumbnailLoadWorkerTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.app = QCoreApplication.instance() or QCoreApplication([])

	def _run_worker(self, worker):
		"""Führt den Worker im globalen ThreadPool aus und wartet auf Ergebnis."""
		results = []
		errors = []
		loop = QEventLoop()
		worker.signals.result.connect(lambda data: results.append(data) or loop.quit())
		worker.signals.error.connect(lambda e: errors.append(e) or loop.quit())
		QThreadPool.globalInstance().start(worker)
		loop.exec()
		return results, errors

	def test_valid_image_returns_bytes(self):
		tmpdir = tempfile.mkdtemp(prefix="thumb_test_")
		img_path = os.path.join(tmpdir, "test.png")
		_make_test_image(img_path)

		worker = ThumbnailLoadWorker(img_path)
		results, errors = self._run_worker(worker)

		self.assertEqual(errors, [])
		self.assertEqual(len(results), 1)
		data = results[0]
		self.assertIsNotNone(data)
		self.assertIsInstance(data, bytes)
		self.assertGreater(len(data), 0)

	def test_nonexistent_file_returns_none(self):
		missing = os.path.join(tempfile.gettempdir(), "does_not_exist_12345.png")
		worker = ThumbnailLoadWorker(missing)
		results, errors = self._run_worker(worker)
		self.assertEqual(errors, [])
		self.assertEqual(len(results), 1)
		self.assertIsNone(results[0])

	def test_empty_path_returns_none(self):
		worker = ThumbnailLoadWorker(None)
		results, errors = self._run_worker(worker)
		self.assertEqual(errors, [])
		self.assertEqual(len(results), 1)
		self.assertIsNone(results[0])

	def test_none_path_returns_none(self):
		worker = ThumbnailLoadWorker("")
		results, errors = self._run_worker(worker)
		self.assertEqual(errors, [])
		self.assertEqual(len(results), 1)
		self.assertIsNone(results[0])


if __name__ == "__main__":
	unittest.main()