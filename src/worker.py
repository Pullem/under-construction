import os
import json
import traceback
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject
import exiftool
from pymediainfo import MediaInfo

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
			print(f"[Worker] MediaInfo fertig.")

			# SCHRITT 3: ExifTool
			print(f"[Worker] ExifTool Deep Dive (Suche nach Binary)...")
			exif_data = {}
			try:
				# Hier könnte es hängen, wenn exiftool.exe nicht reagiert
				with exiftool.ExifToolHelper() as et:
					metadata = et.get_metadata(self.filepath)
					exif_data = metadata[0] if metadata else {}
				print(f"[Worker] ExifTool fertig ({len(exif_data)} Tags).")
			except Exception as e:
				print(f"[Worker] ExifTool übersprungen/Fehler: {e}")

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