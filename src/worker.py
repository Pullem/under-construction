import os
import json
import subprocess
import traceback
from pathlib import Path
import numpy as np
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
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)             # mode, error_msg


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
			import traceback
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


class ElaWorker(QRunnable):
	def __init__(self, filepath, exports_dir, quality=95):
		super().__init__()
		self.filepath = filepath
		self.exports_dir = Path(exports_dir)
		self.quality = quality
		self.signals = ElaWorkerSignals()

	def run(self):
		try:
			from PIL import Image, ImageOps
			import numpy as np

			stem = Path(self.filepath).stem
			src = ImageOps.exif_transpose(Image.open(self.filepath)).convert("RGB")

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
			)

			data = {
				"diff": diff,
				"stats": {
					"quality": self.quality,
					"max_err": max_err,
					"mean_err": mean_err,
					"std_err": std_err,
					"altered": altered,
					"total_pixels": total_pixels,
					"pct_altered": pct_altered,
				},
			}
			self.signals.result.emit("ela", text, data)

		except Exception as e:
			self.signals.error.emit("ela", str(e))


SENSITIVITY_PRESETS = {
	"standard": {
		"contrast_threshold": 0.04,
		"ratio": 0.75,
		"spatial_dist": 30,
		"ransac_thresh": 5.0,
		"verdict_threshold": 15,
	},
	"empfindlich": {
		"contrast_threshold": 0.02,
		"ratio": 0.80,
		"spatial_dist": 20,
		"ransac_thresh": 5.0,
		"verdict_threshold": 12,
	},
	"sehr_empfindlich": {
		"contrast_threshold": 0.01,
		"ratio": 0.85,
		"spatial_dist": 15,
		"ransac_thresh": 8.0,
		"verdict_threshold": 8,
	},
}


class CopyMoveWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)


class CopyMoveWorker(QRunnable):
	"""Keypoint-basierte Copy-Move-Forgery-Erkennung mittels SIFT + FLANN + RANSAC."""

	def __init__(self, filepath, exports_dir, sensitivity="standard"):
		super().__init__()
		self.filepath = filepath
		self.exports_dir = Path(exports_dir)
		self.sensitivity = sensitivity
		self.params = SENSITIVITY_PRESETS.get(sensitivity, SENSITIVITY_PRESETS["standard"])
		self.signals = CopyMoveWorkerSignals()

	def run(self):
		try:
			from PIL import Image, ImageOps
			import numpy as np
			import cv2

			stem = Path(self.filepath).stem
			src = ImageOps.exif_transpose(Image.open(self.filepath)).convert("RGB")
			gray = cv2.cvtColor(np.array(src), cv2.COLOR_RGB2GRAY)

			# 1) SIFT-Features extrahieren
			sift = cv2.SIFT_create(contrastThreshold=self.params["contrast_threshold"])
			kp, desc = sift.detectAndCompute(gray, None)

			if desc is None or len(kp) < 8:
				text = (
					f"Copy-Move-Analyse: {Path(self.filepath).name}\n"
					f"{'-' * 50}\n"
					f"Zu wenig Features ({len(kp) if kp is not None else 0} gefunden, min 8)."
				)
				self.signals.result.emit("copymove", text, {"vis": None})
				return

			# 2) FLANN-Matcher (self-match)
			FLANN_INDEX_KDTREE = 1
			flann = cv2.FlannBasedMatcher(
				{"algorithm": FLANN_INDEX_KDTREE, "trees": 5},
				{"checks": 50}
			)
			# k=3: pair[0] ist beim Self-Matching immer der Deskriptor selbst
			# (Distanz 0) – Ratio-Test daher auf die beiden nächsten
			# Nicht-Selbst-Nachbarn (pair[1], pair[2]) anwenden.
			matches = flann.knnMatch(desc, desc, k=3)

			# 3) Ratio-Test + Self-Match + Distanz-Filter
			good = []
			for pair in matches:
				if len(pair) < 3:
					continue
				m, n = pair[1], pair[2]
				if m.queryIdx == m.trainIdx:
					continue
				if m.distance < self.params["ratio"] * n.distance:
					pt1 = np.array(kp[m.queryIdx].pt)
					pt2 = np.array(kp[m.trainIdx].pt)
					if np.linalg.norm(pt1 - pt2) > self.params["spatial_dist"]:
						good.append(m)

			# 4) RANSAC-konsistente Transformation
			pairs = []
			if len(good) >= 4:
				src_pts = np.float32([kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
				dst_pts = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
				_, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, self.params["ransac_thresh"])
				if mask is not None:
					for i, m in enumerate(good):
						if mask[i]:
							pairs.append((kp[m.queryIdx], kp[m.trainIdx]))

			if not pairs:
				# Ohne räumlich konsistente Inlier keine Kopier-Region zeichnen
				# (rohe Matches ergeben nur bei strukturierten Bildern Fehlalarme).
				self.signals.result.emit(
					"copymove",
					f"Copy-Move-Analyse: {Path(self.filepath).name}\n"
					f"{'-' * 50}\n"
					f"Empfindlichkeit: {self.sensitivity} "
					f"(ratio={self.params['ratio']}, dist={self.params['spatial_dist']})\n"
					f"SIFT-Features: {len(kp)}\n"
					f"Matched (Ratio-Test): {len(good)}\n"
					f"RANSAC-Inlier: 0\n"
					f"Ergebnis: Keine konsistente Transformationsgruppe (RANSAC) gefunden\n"
					f"→ vermutlich keine Copy-Move-Manipulation oder zu glatte/komprimierte Region.",
					{"vis": None},
				)
				return

			# 5) Visualisierung
			vis = np.array(src)
			for qk, tk in pairs:
				cv2.line(vis,
					(int(qk.pt[0]), int(qk.pt[1])),
					(int(tk.pt[0]), int(tk.pt[1])),
					(0, 255, 0), 1)
				cv2.circle(vis, (int(qk.pt[0]), int(qk.pt[1])), 4, (255, 0, 0), -1)
				cv2.circle(vis, (int(tk.pt[0]), int(tk.pt[1])), 4, (0, 0, 255), -1)

			shifts = np.array(
				[[tk.pt[0] - qk.pt[0], tk.pt[1] - qk.pt[1]] for qk, tk in pairs],
				dtype=np.float32)

			# 6) Report
			verdict = "⚠️  Copy-Move verdächtig" if len(pairs) > self.params["verdict_threshold"] else "Keine offensichtliche Copy-Move erkannt"
			text = (
				f"Copy-Move-Analyse: {Path(self.filepath).name}\n"
				f"{'-' * 50}\n"
				f"Empfindlichkeit: {self.sensitivity} "
				f"(ratio={self.params['ratio']}, dist={self.params['spatial_dist']})\n"
				f"SIFT-Features: {len(kp)}\n"
				f"Matched (Ratio-Test): {len(good)}\n"
				f"RANSAC-Inlier: {len(pairs)}\n"
				f"Ergebnis: {verdict}\n"
			)
			self.signals.result.emit("copymove", text, {"vis": vis, "shifts": shifts})

		except Exception as e:
			import traceback
			traceback.print_exc()
			self.signals.error.emit("copymove", str(e))


class ResamplingWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)


class ResamplingWorker(QRunnable):
	"""Resampling-/Rausch-Analyse: Interpolations-Residual + FFT-Periodizität
	(Resampling-Erkennung) und blockweise Rausch-Konsistenz (Splicing-Hinweis)."""

	MAX_ANALYSIS_DIM = 4096
	BLOCK_SIZE = 32
	CV_THRESHOLD = 0.5

	def __init__(self, filepath, exports_dir):
		super().__init__()
		self.filepath = filepath
		self.exports_dir = Path(exports_dir)
		self.signals = ResamplingWorkerSignals()

	def run(self):
		try:
			from PIL import Image, ImageOps
			import numpy as np
			import cv2

			stem = Path(self.filepath).stem
			src = ImageOps.exif_transpose(Image.open(self.filepath)).convert("RGB")
			gray = np.array(src.convert("L"), dtype=np.float32)
			h, w = gray.shape

			scaled = False
			max_dim = max(h, w)
			if max_dim > self.MAX_ANALYSIS_DIM:
				scale = self.MAX_ANALYSIS_DIM / max_dim
				gray = cv2.resize(gray, (int(w * scale), int(h * scale)),
								  interpolation=cv2.INTER_AREA)
				h, w = gray.shape
				scaled = True

			# ---- Rauschschätzung (Hochpass über Gaussian-Filter) ----
			blur = cv2.GaussianBlur(gray, (0, 0), 1.5)
			high = gray - blur
			med = float(np.median(high))
			sigma_noise = float(1.4826 * np.median(np.abs(high - med)))
			signal_power = float(np.mean((gray - float(gray.mean())) ** 2))
			snr_db = float(10.0 * np.log10(max(signal_power, 1e-12) / max(sigma_noise ** 2, 1e-12)))

			# ---- Blockweise Rauschkarte (Inkonsistenzen) ----
			bs = self.BLOCK_SIZE
			b_rows = (h + bs - 1) // bs
			b_cols = (w + bs - 1) // bs
			noise_map = np.full((b_rows, b_cols), np.nan, dtype=np.float32)
			for by in range(b_rows):
				y0, y1 = by * bs, min((by + 1) * bs, h)
				for bx in range(b_cols):
					x0, x1 = bx * bs, min((bx + 1) * bs, w)
					block = high[y0:y1, x0:x1]
					if block.size > (bs * bs) // 2:
						noise_map[by, bx] = float(block.std())
			valid = noise_map[~np.isnan(noise_map)]
			if valid.size == 0:
				valid = np.array([sigma_noise], dtype=np.float32)
			noise_mean = float(valid.mean())
			noise_std = float(valid.std())
			cv_coeff = noise_std / max(noise_mean, 1e-12)

			# ---- Resampling-Erkennung: Interpolations-Residual + FFT ----
			res = gray - 0.25 * (
				np.roll(gray, -1, 0) + np.roll(gray, 1, 0) +
				np.roll(gray, -1, 1) + np.roll(gray, 1, 1))
			res = res - float(res.mean())

			F = np.fft.fftshift(np.fft.fft2(res))
			P = np.abs(F).astype(np.float64) ** 2
			cy, cx = h // 2, w // 2
			cut_r = max(4, min(h, w) // 40)
			max_r = min(h, w) * 0.45
			yy, xx = np.mgrid[0:h, 0:w]
			r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
			# Kanten (Letterbox, Rahmen, helle Stufen) erzeugen Spektral-Linien
			# genau auf den Achsen – diese Bänder ausschließen, um Fehlalarme zu
			# vermeiden. Resampling-Rotation erzeugt Peaks abseits der Achsen.
			du = np.abs(xx - cx)
			dv = np.abs(yy - cy)
			ring = (r >= cut_r) & (r <= max_r) & (du > 3) & (dv > 3)
			P_ring = P[ring]
			mu = float(P_ring.mean())
			sd = float(P_ring.std())
			if sd > 0:
				z = (P_ring - mu) / sd
				kurtosis = float(np.mean(z ** 4))
				peak_frac = float((z > 10.0).mean())
			else:
				kurtosis, peak_frac = 1.0, 0.0
			spectral_peakiness = kurtosis / 20.0

			# 1D-Periodizität der Zeilen/Spalten-Profile (Skalierungs-Artefakte).
			# Nur das mittlere Frequenzband (5–95 % der Nyquist-Frequenz, also
			# Perioden von 2–20 px): Stufenkanten (Splicing-Seams, Letterbox)
			# liegen im sehr niedrigen Frequenzbereich und würden sonst
			# fälschlich als Skalierung gewertet.
			def _band_periodicity(profile):
				p = np.abs(np.fft.rfft(profile - float(profile.mean())))[1:]
				n = len(p)
				band = p[int(n * 0.05):int(n * 0.95)]
				if band.size == 0:
					return 0.0
				return float(band.max() / (band.mean() + 1e-12))

			profile_periodicity = max(
				_band_periodicity(np.abs(res).mean(axis=1)),
				_band_periodicity(np.abs(res).mean(axis=0)))

			# ---- Verdicts ----
			resample_suspect = (spectral_peakiness > 2.5) or (profile_periodicity > 10.0)
			resample_verdict = (
				"⚠️  Verdacht auf Resampling (Skalierung/Rotation)" if resample_suspect
				else "Keine auffälligen Resampling-Artefakte")
			noise_suspect = cv_coeff > self.CV_THRESHOLD
			noise_verdict = (
				"⚠️  Inkonsistentes Rauschniveau – Hinweis auf Compositing/Splicing "
				"oder stark variierende Bildbereiche"
				if noise_suspect else "Gleichmäßiges Rauschniveau")

			# ---- Visualisierung: Residual + Rauschkarte ----
			v_lim = max(1e-6, 3.0 * sigma_noise)
			noise_vmax = max(1e-6, float(np.nanpercentile(noise_map, 95)))

			# ---- Report ----
			analysis_size = f"{w}×{h}" + (" (auf max. 4096 px begrenzt)" if scaled else "")
			text = (
				f"Resampling/Rauschen-Analyse: {Path(self.filepath).name}\n"
				f"{'-' * 50}\n"
				f"[Resampling]\n"
				f"Analysierte Auflösung: {analysis_size}\n"
				f"Spektrum-Peakiness: {spectral_peakiness:.2f} "
				f"(Kurtosis {kurtosis:.1f}, Peak-Anteil {peak_frac * 100:.2f}%)\n"
				f"Zeilen/Spalten-Periodizität: {profile_periodicity:.1f}\n"
				f"Ergebnis: {resample_verdict}\n"
				f"\n"
				f"[Rauschen]\n"
				f"Geschätztes Rauschen (σ): {sigma_noise:.2f}\n"
				f"SNR: {snr_db:.1f} dB\n"
				f"Blockgröße: {bs}px\n"
				f"Rauschlevel: Mittel {noise_mean:.2f}, Std {noise_std:.2f}, "
				f"Variationskoeffizient {cv_coeff:.2f}\n"
				f"Ergebnis: {noise_verdict}\n"
			)
			data = {
				"res": res,
				"noise_map": noise_map,
				"sigma_noise": sigma_noise,
				"block_size": bs,
				"v_lim": v_lim,
				"noise_vmax": noise_vmax,
				"metrics": {
					"spectral_peakiness": spectral_peakiness,
					"kurtosis": kurtosis,
					"peak_frac": peak_frac,
					"profile_periodicity": profile_periodicity,
					"snr_db": snr_db,
					"noise_mean": noise_mean,
					"noise_std": noise_std,
					"cv_coeff": cv_coeff,
					"scaled": scaled,
					"width": w,
					"height": h,
				},
			}
			self.signals.result.emit("resample", text, data)

		except Exception as e:
			import traceback
			traceback.print_exc()
			self.signals.error.emit("resample", str(e))


class JpegGridWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)


class JpegGridWorker(QRunnable):
	"""JPEG-Grid-Analyse: erkennt das 8×8-DCT-Blockraster der JPEG-Kompression
	und prüft die bildweite Raster-Ausrichtung. Regionen mit abweichendem
	Raster-Offset deuten auf Neu-Kompression, Crop/Splicing oder Compositing hin."""

	BLOCK = 8
	MIN_DIM = 16
	# Sharpness = (bester Score - zweitbester Score) / internal, gemittelt über
	# x/y. Echte JPEG-Raster ≥ ~0.09, Rauschboden (weißes Rauschen, geglättet)
	# ≤ ~0.035, schwaches JPEG-Raster ~0.04-0.07.
	GRID_STRONG_THRESHOLD = 0.045
	MIN_STRONG_FRACTION = 0.15
	DEVIATION_RATIO = 0.10

	def __init__(self, filepath, exports_dir):
		super().__init__()
		self.filepath = filepath
		self.exports_dir = Path(exports_dir)
		self.signals = JpegGridWorkerSignals()

	def _scores_aligned(self, diff, start, axis):
		"""Blockiness-Scores aller 8 Offsets. start = globaler Versatz des
		Regionsbeginns entlang der Achse (0 für das ganze Bild).
		Blockgrenzen bei Offset o liegen auf Index j ≡ o-1 (mod 8)."""
		total = float(diff.mean())
		scores = []
		internals = []
		for o in range(8):
			if axis == 1:
				sel = diff[:, (o - 1 - start) % 8::8]
			else:
				sel = diff[(o - 1 - start) % 8::8, :]
			if sel.size == 0:
				scores.append(0.0)
				internals.append(total)
				continue
			b = float(sel.mean())
			frac = sel.size / diff.size
			internal = (total - frac * b) / (1 - frac) if frac < 1 else 0.0
			scores.append(b - internal)
			internals.append(internal)
		return scores, internals

	def _blockiness_map(self, gray, ox, oy):
		"""Blockiness pro 8×8-Zelle (vektorisiert), ausgerichtet am erkannten Offset."""
		B = self.BLOCK
		gx = np.abs(np.diff(gray, axis=1))
		gy = np.abs(np.diff(gray, axis=0))
		sx0 = ox % B
		sy0 = oy % B
		n_cols = (gx.shape[1] - sx0) // B
		n_rows = (gy.shape[0] - sy0) // B
		if n_cols < 1 or n_rows < 1:
			return None
		gx_c = gx[sy0:sy0 + n_rows * B, sx0:sx0 + n_cols * B]
		gy_c = gy[sy0:sy0 + n_rows * B, sx0:sx0 + n_cols * B]
		gx4 = gx_c.reshape(n_rows, B, n_cols, B)
		gy4 = gy_c.reshape(n_rows, B, n_cols, B)
		bound_v = gx4[:, :, :, -1].mean(axis=1)
		int_v = gx4[:, :, :, :-1].mean(axis=(1, 3))
		bound_h = gy4[:, -1, :, :].mean(axis=2)
		int_h = gy4[:, :-1, :, :].mean(axis=(1, 3))
		return np.clip((bound_v - int_v) + (bound_h - int_h), 0, None)

	def _region_consistency(self, gx, gy, region):
		"""Per-Region Raster-Offset + Sharpness (Spitzenwert des Blockiness-Score-
		Verlaufs). Sharpness ≥ GRID_STRONG_THRESHOLD → Region hat ein echtes
		Raster; bei Rauschen bleibt sie nahe 0 (alle 8 Offsets gleich flach)."""
		H, _ = gx.shape
		We = gy.shape[1]
		regions = []
		for y0 in range(0, H, region):
			for x0 in range(0, We, region):
				y1 = min(y0 + region, H)
				x1 = min(x0 + region, We)
				if y1 - y0 < self.MIN_DIM or x1 - x0 < self.MIN_DIM:
					continue
				gxr = gx[y0:y1, x0:x1]
				gyr = gy[y0:y1, x0:x1]
				if gyr.shape[0] < 2:
					continue
				sx, ix = self._scores_aligned(gxr, x0, 1)
				sy, iy = self._scores_aligned(gyr, y0, 0)
				rox = int(np.argmax(sx))
				roy = int(np.argmax(sy))
				s2x = float(np.partition(sx, -2)[-2])
				s2y = float(np.partition(sy, -2)[-2])
				sharp_x = (sx[rox] - s2x) / (ix[rox] + 1e-9)
				sharp_y = (sy[roy] - s2y) / (iy[roy] + 1e-9)
				strength = 0.5 * (sharp_x + sharp_y)
				regions.append((y0, x0, y1, x1, rox, roy, strength))
		return regions

	def run(self):
		try:
			from PIL import Image, ImageOps
			import numpy as np

			stem = Path(self.filepath).stem
			src = ImageOps.exif_transpose(Image.open(self.filepath)).convert("RGB")
			gray = np.array(src.convert("L"), dtype=np.float32)
			h, w = gray.shape

			if min(h, w) < self.MIN_DIM:
				self.signals.result.emit(
					"jpeggrid",
					f"JPEG-Grid-Analyse: {Path(self.filepath).name}\n"
					f"{'-' * 50}\n"
					f"Bild zu klein für eine Raster-Analyse ({w}×{h}).",
					{"block": None})
				return

			gx = np.abs(np.diff(gray, axis=1))
			gy = np.abs(np.diff(gray, axis=0))

			sx, ix = self._scores_aligned(gx, 0, 1)
			sy, iy = self._scores_aligned(gy, 0, 0)
			ox = int(np.argmax(sx))
			oy = int(np.argmax(sy))
			rel_x = sx[ox] / (ix[ox] + 1e-9)
			rel_y = sy[oy] / (iy[oy] + 1e-9)
			global_strength = 0.5 * (rel_x + rel_y)

			# Regionen-basierte Erkennung: dominanter Offset der starken Regionen
			# (robust gegen nicht-komprimierte Bereiche, die den globalen Wert
			# verwässern).
			region = max(128, min(256, max(h, w) // 10))
			regions = self._region_consistency(gx, gy, region)
			strong = [r for r in regions if r[6] >= self.GRID_STRONG_THRESHOLD]
			if strong:
				offs = np.array([(r[4], r[5]) for r in strong])
				vals, counts = np.unique(offs, axis=0, return_counts=True)
				ox, oy = int(vals[int(np.argmax(counts))][0]), int(vals[int(np.argmax(counts))][1])
				global_strength = float(np.mean([r[6] for r in strong]))
			n_strong = len(strong)
			n_deviating = sum(1 for r in strong if (r[4], r[5]) != (ox, oy))
			n_weak = len(regions) - n_strong
			grid_detected = (n_strong >= 1 and
				n_strong / max(1, len(regions)) >= self.MIN_STRONG_FRACTION)

			block = self._blockiness_map(gray, ox, oy) if grid_detected else None

			if not grid_detected:
				verdict = ("Kein 8×8-Blockraster erkennbar "
						   "(keine JPEG-Kompression oder stark geglättet)")
			elif n_deviating > 0 and n_strong > 0 and \
					n_deviating / n_strong > self.DEVIATION_RATIO:
				verdict = (f"⚠️  Abweichendes Raster in {n_deviating} von {n_strong} "
						   "starken Regionen – Hinweis auf Neu-Kompression/Crop/Splicing")
			else:
				verdict = f"Konsistentes Blockraster (Offset x={ox}, y={oy})"

			# ---- Visualisierung (Daten für pyqtgraph-View) ----
			block_vmax = max(1e-6, float(np.percentile(block, 98))) \
				if block is not None and block.size else 0.0

			# Regions-Overlay auf Original-Auflösung
			# (grün konsistent, rot abweichend, grau schwach)
			overlay = np.zeros((h, w, 3), dtype=np.float32)
			alpha = np.zeros((h, w), dtype=np.float32)
			for (y0, x0, y1, x1, rox, roy, rstrength) in regions:
				y1 = min(y1, h); x1 = min(x1, w)
				if y1 <= y0 or x1 <= x0:
					continue
				if rstrength >= self.GRID_STRONG_THRESHOLD:
					color = (0.0, 0.8, 0.0) if (rox, roy) == (ox, oy) else (0.9, 0.1, 0.1)
				else:
					color = (0.5, 0.5, 0.5)
				overlay[y0:y1, x0:x1] = color
				alpha[y0:y1, x0:x1] = 0.55

			# ---- Report ----
			block_mean = float(block.mean()) if block is not None and block.size else 0.0
			block_max = float(block.max()) if block is not None and block.size else 0.0
			text = (
				f"JPEG-Grid-Analyse: {Path(self.filepath).name}\n"
				f"{'-' * 50}\n"
				f"Auflösung: {w}×{h}\n"
				f"Blockraster: {'8×8-DCT-Raster' if grid_detected else 'nicht erkannt'} "
				f"(Offset x={ox}, y={oy}, Stärke {global_strength:.3f})\n"
				f"Blockiness: Mittel {block_mean:.2f}, Max {block_max:.2f}\n"
				f"Regionen: {len(regions)} gesamt, {n_strong} stark, "
				f"{n_deviating} abweichend, {n_weak} schwach/unbestimmt\n"
				f"Ergebnis: {verdict}\n"
			)
			data = {
				"block": block,
				"gray": np.asarray(src.convert("L"), dtype=np.uint8),
				"overlay": overlay,
				"alpha": alpha,
				"grid_detected": grid_detected,
				"ox": ox,
				"oy": oy,
				"strength": global_strength,
				"block_mean": block_mean,
				"block_max": block_max,
				"block_vmax": block_vmax,
				"regions": regions,
				"n_strong": n_strong,
				"n_deviating": n_deviating,
				"n_weak": n_weak,
				"width": w,
				"height": h,
			}
			self.signals.result.emit("jpeggrid", text, data)

		except Exception as e:
			import traceback
			traceback.print_exc()
			self.signals.error.emit("jpeggrid", str(e))