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


class ElaWorkerSignals(QObject):
	result = pyqtSignal(str, str, str, str)  # mode, text_result, error_map_path, hist_path
	error = pyqtSignal(str, str)             # mode, error_msg

class ElaWorker(QRunnable):
	def __init__(self, filepath, exports_dir, quality=95):
		super().__init__()
		self.filepath = filepath
		self.exports_dir = Path(exports_dir)
		self.quality = quality
		self.signals = ElaWorkerSignals()

	def run(self):
		try:
			from PIL import Image
			import numpy as np
			import matplotlib
			matplotlib.use("Agg")
			import matplotlib.pyplot as plt

			stem = Path(self.filepath).stem
			src = Image.open(self.filepath).convert("RGB")

			# Re-save at target quality
			temp_jpeg = self.exports_dir / f"{stem}_ela_temp.jpg"
			src.save(str(temp_jpeg), "JPEG", quality=self.quality)

			# Reload and compute difference
			recomp = Image.open(str(temp_jpeg)).convert("RGB")
			arr_src = np.array(src, dtype=np.int16)
			arr_rec = np.array(recomp, dtype=np.int16)
			diff = np.abs(arr_src - arr_rec).max(axis=2).astype(np.uint8)

			max_err = int(diff.max())
			total_pixels = diff.size
			altered = int((diff > 0).sum())
			mean_err = float(diff.mean())
			std_err = float(diff.std())
			pct_altered = altered / total_pixels * 100

			# Error distribution map
			errormap_path = self.exports_dir / f"{stem}_ela_errormap.png"
			fig, ax = plt.subplots(figsize=(8, 6), facecolor="#1e1e1e")
			vmax = max(1, max_err)
			im = ax.imshow(diff, cmap="hot", vmin=0, vmax=vmax)
			ax.set_title("ELA Error Distribution", color="#ccc", fontsize=12)
			ax.axis("off")
			fig.colorbar(im, ax=ax, label="Error-Level")
			fig.savefig(str(errormap_path), dpi=150, bbox_inches="tight")
			plt.close(fig)

			# Error histogram
			hist_path = self.exports_dir / f"{stem}_ela_histogram.png"
			fig, ax = plt.subplots(figsize=(6, 3), facecolor="#1e1e1e")
			ax.hist(diff.ravel(), bins=256, range=(0, 255), color="#0f0", alpha=0.8)
			ax.set_xlabel("Error-Level", color="#ccc")
			ax.set_ylabel("Pixel", color="#ccc")
			ax.set_title(f"ELA Histogram — {Path(self.filepath).name}", color="#ccc")
			ax.tick_params(colors="#ccc")
			ax.grid(axis="y", alpha=0.3)
			fig.tight_layout()
			fig.savefig(str(hist_path), dpi=150)
			plt.close(fig)

			# Clean up temp
			if temp_jpeg.exists():
				temp_jpeg.unlink()

			# Build text result
			text = (
				f"ELA-Analyse: {Path(self.filepath).name}\n"
				f"{'-' * 50}\n"
				f"Qualität: {self.quality}%\n"
				f"Max-Fehler: {max_err}\n"
				f"Mittlerer Fehler: {mean_err:.2f}\n"
				f"Std-Abweichung: {std_err:.2f}\n"
				f"Veränderte Pixel: {altered} / {total_pixels} ({pct_altered:.1f}%)\n"
				f"\n"
				f"Error-Map: {errormap_path}\n"
				f"Histogram: {hist_path}\n"
			)

			self.signals.result.emit("ela", text, str(errormap_path), str(hist_path))

		except Exception as e:
			self.signals.error.emit("ela", str(e))