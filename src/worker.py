import os
import json
import subprocess
import traceback
from pathlib import Path
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
import exiftool
from pymediainfo import MediaInfo

BASE_DIR = Path(__file__).resolve().parent.parent

class WorkerSignals(QObject):
	result = pyqtSignal(dict)
	finished = pyqtSignal()
	error = pyqtSignal(str)

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
				import subprocess
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


class FfprobeWorkerSignals(QObject):
	result = pyqtSignal(str, str, str)  # mode, stdout, stderr
	error = pyqtSignal(str, str)        # mode, error_msg

class FfprobeWorker(QRunnable):
	def __init__(self, filepath, mode, cmd, timeout=120):
		super().__init__()
		self.filepath = filepath
		self.mode = mode
		self.cmd = cmd
		self.timeout = timeout
		self.signals = FfprobeWorkerSignals()

	def run(self):
		try:
			r = subprocess.run(
				self.cmd,
				capture_output=True, text=True, timeout=self.timeout
			)
			self.signals.result.emit(self.mode, r.stdout, r.stderr)
		except Exception as e:
			self.signals.error.emit(self.mode, str(e))