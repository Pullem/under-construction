import os
import traceback
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject


class ThumbnailWorkerSignals(QObject):
	progress = pyqtSignal(int, int)  # current, total
	chunk = pyqtSignal(object)       # media_files mit bisherigen Thumbnails
	result = pyqtSignal(object)      # list of media_files with _thumbnails populated
	error = pyqtSignal(str)


class ThumbnailWorker(QRunnable):
	"""Extract thumbnails for all media files in a case, off the main thread."""

	def __init__(self, model, media_files, thumb_dir):
		super().__init__()
		self.model = model
		self.media_files = media_files
		self.thumb_dir = thumb_dir
		self.signals = ThumbnailWorkerSignals()

	def run(self):
		try:
			total = len(self.media_files)
			chunk_size = 100
			for idx, f in enumerate(self.media_files):
				self._process_file(f)
				self.signals.progress.emit(idx + 1, total)
				if (idx + 1) % chunk_size == 0:
					self.signals.chunk.emit(self.media_files)
			self.signals.result.emit(self.media_files)

		except Exception as e:
			print(f"[ThumbnailWorker] Fehler: {traceback.format_exc()}")
			self.signals.error.emit(str(e))

	def _process_file(self, f):
		fname = f.get("file_name", "")
		meta = f.get("metadata", {})
		fpath = f.get("file_path", "")
		if not fpath or not os.path.exists(fpath):
			f["_thumbnails"] = []
			f["_duration_sec"] = 0
			return

		fname_lower = fname.lower()
		if fname_lower.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".mts")):
			self._extract_video(f, meta, fpath)
		elif fname_lower.endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")):
			self._extract_photo(f, fpath)
		else:
			f["_thumbnails"] = []
			f["_duration_sec"] = 0

	def _extract_video(self, f, meta, fpath):
		general = meta.get("General", {})
		dur_str = general.get("duration", "0")
		try:
			dur = float(dur_str)
		except (ValueError, TypeError):
			dur = 0
		dur_sec = dur / 1000.0
		if dur_sec > 0 and self.thumb_dir:
			if dur_sec <= 60:
				interval = 2
			elif dur_sec <= 300:
				interval = 10
			elif dur_sec <= 3600:
				interval = 30
			else:
				interval = 60
			thumbnails = self.model.extract_thumbnails(fpath, interval, self.thumb_dir)
			f["_thumbnails"] = thumbnails
		else:
			f["_thumbnails"] = []
		f["_duration_sec"] = dur_sec

	def _extract_photo(self, f, fpath):
		thumb_path = self.model.get_thumbnail(fpath)
		if thumb_path and os.path.exists(thumb_path):
			f["_thumbnails"] = [{"time_sec": 0, "path": thumb_path}]
		else:
			f["_thumbnails"] = []
		f["_duration_sec"] = 0