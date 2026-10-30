"""
Tests für die Bild-Thumbnails des VSThumbnailWorker (AGENTS.md Abschnitt 12).

Reproduzierbare Testdaten: synthetische Bilder mit fest definierten Pixelwerten.
Regressionstest: PNG im Palettenmodus (P) musste als JPEG gespeichert werden
können ("cannot write mode P as JPEG").
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src.workers.vs_thumbnail_worker import VSThumbnailWorker


def _write_palette_png(path, width=320, height=200):
	"""PNG im Palettenmodus (P) erzeugen."""
	img = Image.new("P", (width, height))
	img.putpalette([i % 256 for i in range(768)])  # 256 Graustufen-Farbeinträge
	img.save(path, "PNG")


def _write_rgba_png(path, width=320, height=200):
	"""PNG mit Alpha-Kanal erzeugen."""
	img = Image.new("RGBA", (width, height), (200, 30, 30, 128))
	img.save(path, "PNG")


class PhotoThumbnailTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.tmp_path = Path(self._tmp.name)
		self.thumb_dir = self.tmp_path / "thumbs"
		self.worker = VSThumbnailWorker(None, [], self.thumb_dir)

	def _process(self, img_path):
		f = {"file_name": Path(img_path).name, "file_path": str(img_path)}
		self.worker._process_file(f)
		return f

	def _assert_valid_thumbnail(self, f):
		self.assertEqual(len(f["_thumbnails"]), 1)
		thumb_path = Path(f["_thumbnails"][0]["path"])
		self.assertTrue(thumb_path.exists())
		with Image.open(thumb_path) as thumb:
			self.assertEqual(thumb.format, "JPEG")
			self.assertLessEqual(thumb.width, VSThumbnailWorker.THUMBNAIL_WIDTH)
			self.assertLessEqual(thumb.height, VSThumbnailWorker.THUMBNAIL_WIDTH)
		return thumb_path

	def test_palette_png_yields_jpeg_thumbnail(self):
		"""PNG im P-Modus muss als JPEG-thumbnail speicherbar sein."""
		src = self.tmp_path / "palette.png"
		_write_palette_png(src)
		f = self._process(src)
		self._assert_valid_thumbnail(f)

	def test_rgba_png_yields_jpeg_thumbnail(self):
		"""PNG mit Alpha-Kanal muss als JPEG-thumbnail speicherbar sein."""
		src = self.tmp_path / "alpha.png"
		_write_rgba_png(src)
		f = self._process(src)
		self._assert_valid_thumbnail(f)

	def test_rgb_jpeg_yields_thumbnail(self):
		"""Normaler RGB-JPEG-Direktweg."""
		src = self.tmp_path / "normal.jpg"
		Image.new("RGB", (640, 480), (10, 120, 200)).save(src, "JPEG")
		f = self._process(src)
		self._assert_valid_thumbnail(f)

	def test_large_image_scaled_to_thumbnail_width(self):
		"""Breite Bilder werden auf THUMBNAIL_WIDTH skaliert."""
		src = self.tmp_path / "large.png"
		Image.new("RGB", (1000, 400), (5, 5, 5)).save(src, "PNG")
		f = self._process(src)
		thumb_path = self._assert_valid_thumbnail(f)
		with Image.open(thumb_path) as thumb:
			self.assertEqual(thumb.width, VSThumbnailWorker.THUMBNAIL_WIDTH)

	def test_opencv_fallback_when_pil_fails(self):
		"""Fällt PIL aus, erzeugt der OpenCV-Fallback (cv2.imread) das Thumbnail."""
		src = self.tmp_path / "fallback.png"
		_write_palette_png(src)
		with mock.patch("PIL.Image.open", side_effect=RuntimeError("simulierter PIL-Fehler")):
			f = self._process(src)
		self._assert_valid_thumbnail(f)

	def test_unreadable_file_yields_no_thumbnails(self):
		"""Unlesbare Datei wird kontrolliert ohne Thumbnail abgeschlossen."""
		src = self.tmp_path / "broken.png"
		src.write_bytes(b"not an image")
		f = self._process(src)
		self.assertEqual(f["_thumbnails"], [])
		self.assertEqual(f["_duration_sec"], 0)


if __name__ == "__main__":
	unittest.main()
