"""
Tests für den CopyMoveWorker (AGENTS.md Abschnitt 12).

Reproduzierbare Testdaten: synthetisches Bild mit fester RNG-Seed und
eingefügter Kopie-Region (Copy-Move-Szenario).

Regression: cv2 war in _get_sift() nicht definiert (lokal importiertes
cv2 aus run() war dort nicht sichtbar -> NameError).
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import cv2
from PIL import Image
from PyQt6.QtCore import QCoreApplication

from src.workers.copy_move_analysis import CopyMoveWorker


def _write_copy_move_image(path, seed=7):
	"""Testbild: strukturiertes Rauschen, Block A wird nach Position B kopiert."""
	rng = np.random.default_rng(seed)
	base = rng.integers(0, 255, (400, 500), dtype=np.uint8)
	base = cv2.GaussianBlur(base, (0, 0), 2.0)
	base[250:350, 300:450] = base[50:150, 50:200]  # Kopie der Region
	Image.fromarray(base).save(path)


class GetSiftTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.tmp_path = Path(self._tmp.name)

	def test_get_sift_returns_detector(self):
		"""Regression: cv2 muss in _get_sift sichtbar sein (kein NameError)."""
		worker = CopyMoveWorker("dummy.jpg", str(self.tmp_path))
		sift = worker._get_sift(0.04)
		self.assertIsNotNone(sift)

	def test_get_sift_respects_contrast_threshold(self):
		"""Auch mit empfindlicherem Schwellwert funktioniert die Erzeugung."""
		worker = CopyMoveWorker("dummy.jpg", str(self.tmp_path), sensitivity="empfindlich")
		sift = worker._get_sift(worker.params["contrast_threshold"])
		self.assertIsNotNone(sift)


class RunAnalysisTest(unittest.TestCase):
	def setUp(self):
		# QCoreApplication für Signal/Slot-Verarbeitung im Test
		self._app = QCoreApplication.instance() or QCoreApplication([])
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.tmp_path = Path(self._tmp.name)

	def test_run_emits_structured_result(self):
		"""Die komplette Pipeline läuft ohne Fehler und meldet strukturiert."""
		img_path = self.tmp_path / "copy_move.png"
		_write_copy_move_image(img_path)

		worker = CopyMoveWorker(str(img_path), str(self.tmp_path))
		results = []
		worker.signals.result.connect(
			lambda mode, text, payload: results.append((mode, text, payload)))
		worker.run()

		self.assertEqual(len(results), 1)
		mode, text, payload = results[0]
		self.assertEqual(mode, "copymove")
		self.assertIn("SIFT-Features:", text)
		self.assertIn("vis", payload)


if __name__ == "__main__":
	unittest.main()
