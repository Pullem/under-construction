import os
import traceback
import subprocess
import logging
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
from pymediainfo import MediaInfo
import exiftool

from src.utils.logging_config import set_log_context, clear_log_context
from src.utils.errors import AppError, ErrorCode, ErrorSeverity, db_error, file_error, analysis_error, external_tool_error, worker_error


logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
	result = pyqtSignal(dict)
	finished = pyqtSignal()
	error = pyqtSignal(str)


class DbWorkerSignals(QObject):
	result = pyqtSignal(object)
	error = pyqtSignal(str)


class DbWorker(QRunnable):
	"""Generic database worker for running DB queries off the GUI thread."""

	def __init__(self, model, query_func, *args, **kwargs):
		super().__init__()
		self.model = model
		self.query_func = query_func
		self.args = args
		self.kwargs = kwargs
		self.signals = DbWorkerSignals()

	def run(self):
		try:
			result = self.query_func(self.model, *self.args, **self.kwargs)
			self.signals.result.emit(result)
		except Exception as e:
			err = AppError.from_exception(e, code=ErrorCode.DB_QUERY,
										  context={"query_func": self.query_func.__name__ if hasattr(self.query_func, '__name__') else "unknown"})
			self.signals.error.emit(err.to_json())
			logger.exception("Database query failed")


class ScanWorkerSignals(QObject):
	result = pyqtSignal(list)
	error = pyqtSignal(str)


class ScanWorker(QRunnable):
	"""Worker for scanning filesystem directories."""

	def __init__(self, folder, extensions=None):
		super().__init__()
		self.folder = folder
		self.extensions = extensions or ('.mp4', '.mov', '.jpg', '.png', '.avi', '.mkv', '.webm', '.mts', '.jpeg', '.bmp', '.tiff', '.webp')
		self.signals = ScanWorkerSignals()

	def run(self):
		try:
			if not os.path.exists(self.folder):
				err = file_error("Ordner nicht gefunden", filepath=self.folder)
				self.signals.error.emit(err.to_json())
				return

			files = []
			for entry in os.scandir(self.folder):
				if entry.is_file() and entry.name.lower().endswith(self.extensions):
					files.append(entry.name)

			self.signals.result.emit(files)
		except Exception as e:
			err = AppError.from_exception(e, code=ErrorCode.FILE_NOT_FOUND,
										  context={"folder": self.folder})
			self.signals.error.emit(err.to_json())
			logger.exception("Scan failed for folder: %s", self.folder)


class PostProcessWorkerSignals(QObject):
	result = pyqtSignal(dict)
	error = pyqtSignal(str)


class PostProcessWorker(QRunnable):
	"""Worker for post-processing ffmpeg output (hash, MediaInfo, ExifTool)."""

	def __init__(self, model, filepath):
		super().__init__()
		self.model = model
		self.filepath = filepath
		self.signals = PostProcessWorkerSignals()

	def run(self):
		try:
			hash_val = self.model.calculate_hash(str(self.filepath))
			mi_data = {}
			exif_data = {}
			try:
				mi = MediaInfo.parse(str(self.filepath))
				mi_data = {t.track_type: t.to_data() for t in mi.tracks}
			except Exception:
				logger.debug("MediaInfo parse failed for %s", self.filepath)
			BASE_DIR = Path(__file__).resolve().parent.parent.parent
			exif_path = str(BASE_DIR / "exiftool.exe")
			if not os.path.exists(exif_path):
				exif_path = str(BASE_DIR / "exiftool_files" / "exiftool.pl")
			try:
				with exiftool.ExifToolHelper(executable=exif_path) as et:
					meta = et.get_metadata(str(self.filepath))
					if meta:
						exif_data = meta[0]
			except Exception:
				logger.debug("ExifTool failed for %s", self.filepath)
			self.signals.result.emit({
				"hash": hash_val,
				"metadata": mi_data,
				"exif": exif_data,
				"filepath": str(self.filepath)
			})
		except Exception as e:
			err = worker_error("Post-process failed", worker_type="PostProcessWorker", exc=e)
			self.signals.error.emit(err.to_json())
			logger.exception("Post-process failed for %s", self.filepath)


class AnalysisWorker(QRunnable):
	def __init__(self, model, filepath, case_id=None):
		super().__init__()
		self.model = model
		self.filepath = filepath
		self.case_id = case_id
		self.signals = WorkerSignals()

	def run(self):
		filename = os.path.basename(self.filepath)
		set_log_context(case_id=self.case_id, file=filename, operation="analysis")
		try:
			logger.info("Starting analysis for %s", filename)

			logger.info("Calculating hash (CPU intensive)")
			file_hash = self.model.calculate_hash(self.filepath)
			logger.info("Hash calculated: %s...", file_hash[:10])

			logger.info("Parsing MediaInfo")
			mi = MediaInfo.parse(self.filepath)
			mi_data = {track.track_type: track.to_data() for track in mi.tracks}

			try:
				result = subprocess.run(
					["mediainfo", f"--Inform=General;%Recorded_Location%", self.filepath],
					capture_output=True, text=True, timeout=10
				)
				loc = result.stdout.strip()
				if loc and "General" not in loc:
					if "General" in mi_data:
						mi_data["General"]["Recorded_Location"] = loc
					else:
						mi_data["General"] = {"Recorded_Location": loc}
					logger.info("Recorded_Location: %s", loc)
			except Exception as e:
				logger.warning("Recorded_Location CLI failed: %s", e)

			try:
				result = subprocess.run(
					["mediainfo", f"--Inform=General;%File_Creation_Date_Local%", self.filepath],
					capture_output=True, text=True, timeout=10
				)
				fcd = result.stdout.strip()
				if fcd and "General" not in fcd:
					if "General" not in mi_data:
						mi_data["General"] = {}
					mi_data["General"]["file_creation_date_local"] = fcd
					logger.info("file_creation_date_local: %s", fcd)
			except Exception as e:
				logger.warning("file_creation_date_local CLI failed: %s", e)

			logger.info("MediaInfo parsing completed")

			logger.info("Starting ExifTool extraction")
			exif_data = {}

			BASE_DIR = Path(__file__).resolve().parent.parent.parent
			exif_path = str(BASE_DIR / "exiftool.exe")
			if not os.path.exists(exif_path):
				exif_path = str(BASE_DIR / "exiftool_files" / "exiftool.pl")

			try:
				with exiftool.ExifToolHelper(executable=exif_path) as et:
					logger.debug("ExifTool process started")
					metadata = et.get_metadata(self.filepath)
					if metadata:
						exif_data = metadata[0]
					gps_parts = []
					for tag in ("GPSLatitude", "GPSLongitude", "Composite:GPSLatitude", "Composite:GPSLongitude"):
						val = exif_data.get(tag)
						if val:
							gps_parts.append(str(val).strip())
					if gps_parts:
						if "General" not in mi_data:
							mi_data["General"] = {}
						mi_data["General"]["EXIF GPS"] = " ".join(gps_parts)
					logger.info("ExifTool completed (%d tags)", len(exif_data))
			except Exception as e:
				logger.warning("ExifTool problem: %s", e)
				logger.debug("ExifTool path used: %s", exif_path)

			logger.info("Generating thumbnail")
			thumb_path = self.model.get_thumbnail(self.filepath)
			logger.info("Thumbnail generated: %s", thumb_path)

			logger.info("Saving to database")
			self.model.save_to_db(
				self.filepath, filename, file_hash, mi_data, exif_data
			)
			logger.info("Database entry successful")

			result_payload = {
				"file_name": filename,
				"file_hash": file_hash,
				"mi": mi_data,
				"exif": exif_data,
				"thumb": thumb_path
			}
			self.signals.result.emit(result_payload)
			self.signals.finished.emit()

		except Exception as e:
			err = AppError.from_exception(e, code=ErrorCode.ANALYSIS_FAILED,
										  context={"filepath": self.filepath, "filename": filename})
			self.signals.error.emit(err.to_json())
			logger.exception("Critical error during analysis of %s", filename)
		finally:
			clear_log_context()