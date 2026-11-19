"""Worker zum asynchronen Laden und Skalieren eines Thumbnails.

Verhindert das Einfrieren der GUI beim Anklicken großer Bilder
(AGENTS.md Abschnitt 3: keine Bildverarbeitung im GUI-Thread).

Der Worker liefert PNG-Bytes über das Signal. Das QPixmap wird erst
im GUI-Thread (View) erstellt, da QPixmap eine GUI-Klasse ist und
nicht im Worker-Thread instantiiert werden darf.
"""

import io
import logging
from pathlib import Path

from PyQt6.QtCore import QRunnable, QObject, pyqtSignal

from src.utils.errors import AppError, ErrorCode, worker_error

logger = logging.getLogger(__name__)


class ThumbnailLoadWorkerSignals(QObject):
	"""Signale für ThumbnailLoadWorker."""
	result = pyqtSignal(object)  # PNG-Bytes (bytes) oder None
	error = pyqtSignal(str)      # AppError-JSON


class ThumbnailLoadWorker(QRunnable):
	"""Lädt ein Bild, skaliert es und liefert PNG-Bytes über Signale.

	Arbeitet vollständig im Hintergrund-Thread. Keine GUI-Klassen
	(QPixmap, QImage) werden hier verwendet.
	"""

	THUMB_W = 320
	THUMB_H = 180

	def __init__(self, path):
		super().__init__()
		self.path = str(path) if path else None
		self.signals = ThumbnailLoadWorkerSignals()

	def run(self):
		try:
			if not self.path or not Path(self.path).exists():
				self.signals.result.emit(None)
				return

			# Versuch 1: PIL (EXIF-korrekt, plattformunabhängig)
			data = self._try_pil()
			if data is not None:
				self.signals.result.emit(data)
				return

			# Versuch 2: OpenCV (Fallback für Formate, die PIL nicht kann)
			data = self._try_opencv()
			self.signals.result.emit(data)

		except Exception as e:
			err = worker_error(
				"Thumbnail-Laden fehlgeschlagen",
				worker_type="ThumbnailLoadWorker",
				exc=e,
			)
			self.signals.error.emit(err.to_json())
			logger.warning("ThumbnailLoadWorker failed for %s: %s", self.path, e)

	def _try_pil(self):
		"""PIL-basierter Ladeweg (EXIF-Transposition + PNG-Encoding)."""
		try:
			from PIL import Image, ImageOps
		except ImportError:
			logger.debug("PIL nicht verfügbar – Fallback auf OpenCV")
			return None

		try:
			img = Image.open(self.path)
			img = ImageOps.exif_transpose(img) or img
			img.thumbnail((self.THUMB_W, self.THUMB_H))

			if img.mode not in ("RGB", "RGBA", "L"):
				img = img.convert("RGB")

			buf = io.BytesIO()
			img.save(buf, format="PNG")
			return buf.getvalue()
		except Exception as e:
			logger.debug("PIL thumbnail load failed for %s: %s", self.path, e)

		return None

	def _try_opencv(self):
		"""Fallback: OpenCV im Worker-Thread laden, als PNG-Bytes ausgeben."""
		try:
			import cv2
		except ImportError:
			logger.debug("OpenCV nicht verfügbar")
			return None

		try:
			frame = cv2.imread(self.path, cv2.IMREAD_COLOR)
			if frame is None:
				return None

			h, w = frame.shape[:2]
			if w > self.THUMB_W or h > self.THUMB_H:
				scale = min(self.THUMB_W / w, self.THUMB_H / h)
				new_w = max(1, int(w * scale))
				new_h = max(1, int(h * scale))
				frame = cv2.resize(
					frame,
					(new_w, new_h),
					interpolation=cv2.INTER_AREA)

			ok, buf = cv2.imencode(".png", frame)
			if ok:
				return buf.tobytes()
		except Exception as e:
			logger.debug("OpenCV thumbnail load failed for %s: %s", self.path, e)

		return None