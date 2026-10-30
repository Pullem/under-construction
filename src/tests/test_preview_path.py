"""
Tests für die Metadaten-Vorschau des Presenters (AGENTS.md Abschnitt 12).

_find_preview_path bestimmt, welchen Pfad set_thumbnail() für die
Vorschau oben im Metadaten-Tab anzeigt: Bilder direkt, Videos über das
vom VSThumbnailWorker erzeugte Thumbnail.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.presenter.file_ops import FileOpsMixin


class _StubPresenter(FileOpsMixin):
	def __init__(self, case_path):
		self.model = SimpleNamespace(current_case_path=case_path)


class FindPreviewPathTest(unittest.TestCase):
	def setUp(self):
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.case_path = Path(self._tmp.name)
		(self.case_path / "thumbnails").mkdir()
		self.presenter = _StubPresenter(self.case_path)

	def _make_worker_thumbnail(self, file_path):
		"""Thumbnail im Namensmuster des VSThumbnailWorker anlegen."""
		f_hash = hashlib.sha256(file_path.encode()).hexdigest()[:12]
		thumb = self.case_path / "thumbnails" / f"{f_hash}_t0.jpg"
		thumb.write_bytes(b"thumb")
		return thumb

	def test_image_returns_original_path(self):
		p = r"D:\evidence\photo.png"
		self.assertEqual(self.presenter._find_preview_path(p), p)

	def test_video_returns_worker_thumbnail(self):
		video = r"D:\evidence\clip.mp4"
		thumb = self._make_worker_thumbnail(video)
		self.assertEqual(self.presenter._find_preview_path(video), str(thumb))

	def test_video_without_thumbnail_returns_none(self):
		self.assertIsNone(
			self.presenter._find_preview_path(r"D:\evidence\missing.mp4"))

	def test_legacy_thumb_fallback(self):
		"""Thumbnail im alten MediaMixin-Muster (<stem>_thumb.jpg) wird gefunden."""
		video = r"D:\evidence\legacy.mp4"
		legacy = self.case_path / "thumbnails" / "legacy_thumb.jpg"
		legacy.write_bytes(b"thumb")
		self.assertEqual(self.presenter._find_preview_path(video), str(legacy))

	def test_empty_path_returns_none(self):
		self.assertIsNone(self.presenter._find_preview_path(None))
		self.assertIsNone(self.presenter._find_preview_path(""))


if __name__ == "__main__":
	unittest.main()
