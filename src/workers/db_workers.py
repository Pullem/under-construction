import os
import traceback
import subprocess
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
from pymediainfo import MediaInfo
import exiftool


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
			self.signals.error.emit(str(e))
			traceback.print_exc()


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
				self.signals.error.emit(f"Ordner nicht gefunden: {self.folder}")
				return

			files = []
			for entry in os.scandir(self.folder):
				if entry.is_file() and entry.name.lower().endswith(self.extensions):
					files.append(entry.name)

			self.signals.result.emit(files)
		except Exception as e:
			self.signals.error.emit(str(e))
			traceback.print_exc()


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
					pass
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
					pass
				self.signals.result.emit({
					"hash": hash_val,
					"metadata": mi_data,
					"exif": exif_data,
					"filepath": str(self.filepath)
				})
			except Exception as e:
				self.signals.error.emit(str(e))
				traceback.print_exc()


class AnalysisWorker(QRunnable):
	def __init__(self, model, filepath):
		super().__init__()
		self.model = model
		self.filepath = filepath
		self.signals = WorkerSignals()

	def run(self):
		try:
			filename = os.path.basename(self.filepath)
			print(f"[Worker] Starte Analyse für: {filename}")

			# SCHRITT 1: Hashing
			print(f"[Worker] Berechne Hash (CPU Last!)...")
			file_hash = self.model.calculate_hash(self.filepath)
			print(f"[Worker] Hash fertig: {file_hash[:10]}...")

			# SCHRITT 2: MediaInfo
			print(f"[Worker] MediaInfo Parsing...")
			mi = MediaInfo.parse(self.filepath)
			mi_data = {track.track_type: track.to_data() for track in mi.tracks}
			# GPS-Koordinaten aus CLI nachziehen (Recorded_Location fehlt oft in pymediainfo)
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
					print(f"[Worker] Recorded_Location: {loc}")
			except Exception as e:
				print(f"[Worker] Recorded_Location CLI fehlgeschlagen: {e}")
			# Erstellungsdatum aus CLI nachziehen
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
					print(f"[Worker] file_creation_date_local: {fcd}")
			except Exception as e:
				print(f"[Worker] file_creation_date_local CLI fehlgeschlagen: {e}")
			print(f"[Worker] MediaInfo fertig.")

			# SCHRITT 3: ExifTool
			print(f"[Worker] ExifTool Deep Dive (Expliziter Pfad-Check)...")
			exif_data = {}

			BASE_DIR = Path(__file__).resolve().parent.parent.parent
			exif_path = str(BASE_DIR / "exiftool.exe")
			if not os.path.exists(exif_path):
				exif_path = str(BASE_DIR / "exiftool_files" / "exiftool.pl")

			try:
				with exiftool.ExifToolHelper(executable=exif_path) as et:
					print(f"[Worker] ExifTool Prozess gestartet...")
					metadata = et.get_metadata(self.filepath)
					if metadata:
						exif_data = metadata[0]
					# GPS aus EXIF in die General-Metadaten übernehmen
					gps_parts = []
					for tag in ("GPSLatitude", "GPSLongitude", "Composite:GPSLatitude", "Composite:GPSLongitude"):
						val = exif_data.get(tag)
						if val:
							gps_parts.append(str(val).strip())
					if gps_parts:
						if "General" not in mi_data:
							mi_data["General"] = {}
						mi_data["General"]["EXIF GPS"] = " ".join(gps_parts)
					print(f"[Worker] ExifTool fertig ({len(exif_data)} Tags).")
			except Exception as e:
				print(f"[Worker] ⚠️ ExifTool Problem: {e}")
				print(f"[Worker] Genutzter Pfad: {exif_path}")

			# SCHRITT 4: Thumbnail (GPU/OpenCV)
			print(f"[Worker] Generiere Thumbnail...")
			thumb_path = self.model.get_thumbnail(self.filepath)
			print(f"[Worker] Thumbnail fertig: {thumb_path}")

			# SCHRITT 5: Datenbank
			print(f"[Worker] Schreibe in MariaDB...")
			self.model.save_to_db(
				self.filepath, filename, file_hash, mi_data, exif_data
			)
			print(f"[Worker] Datenbank-Eintrag erfolgreich.")

			# Ergebnis senden
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
			# Voller Error-Stacktrace im Terminal ausgeben
			error_trace = traceback.format_exc()
			print(f"[Worker] KRITISCHER FEHLER:\n{error_trace}")
			self.signals.error.emit(str(e))