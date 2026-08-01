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
			import matplotlib
			matplotlib.use("Agg")
			import matplotlib.pyplot as plt

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

			# Error distribution map
			errormap_path = self.exports_dir / f"{stem}_ela_errormap.png"
			fig, ax = plt.subplots(figsize=(8, 6), facecolor="#1e1e1e")
			vmax = max(1, max_err)
			im = ax.imshow(diff, cmap="hot", vmin=0, vmax=vmax)
			ax.set_title("ELA Error Distribution", color="#ccc", fontsize=12)
			ax.axis("off")
			cbar = fig.colorbar(im, ax=ax, label="Error-Level")
			cbar.ax.tick_params(colors="#ccc")
			cbar.set_label("Error-Level", color="#ccc")
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
	result = pyqtSignal(str, str, str, str)  # mode, text_result, result_image_path, _unused
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
				self.signals.result.emit("copymove", text, "", "")
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
					"",
					"",
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

			cm_path = self.exports_dir / f"{stem}_copymove.png"
			cv2.imwrite(str(cm_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))

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
				f"\n"
				f"Visualisierung: {cm_path}\n"
			)
			self.signals.result.emit("copymove", text, str(cm_path), "")

		except Exception as e:
			import traceback
			traceback.print_exc()
			self.signals.error.emit("copymove", str(e))


class ResamplingWorkerSignals(QObject):
	result = pyqtSignal(str, str, str, str)  # mode, text_result, error_map_path, hist_path
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
			import matplotlib
			matplotlib.use("Agg")
			import matplotlib.pyplot as plt

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
			P = np.abs(F) ** 2
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
				kurtosis = float(np.mean((P_ring - mu) ** 4) / (sd ** 4 + 1e-12))
				peak_frac = float((P_ring > mu + 10 * sd).mean())
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
			errormap_path = self.exports_dir / f"{stem}_resample_errormap.png"
			fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), facecolor="#1e1e1e")
			v_lim = max(1e-6, 3.0 * sigma_noise)
			im0 = axes[0].imshow(res, cmap="coolwarm", vmin=-v_lim, vmax=v_lim)
			axes[0].set_title("Interpolations-Residual (Resampling)", color="#ccc", fontsize=10)
			axes[0].axis("off")
			axes[0].tick_params(colors="#ccc")
			fig.colorbar(im0, ax=axes[0], fraction=0.046)
			im1 = axes[1].imshow(noise_map, cmap="plasma",
				vmin=0.0, vmax=max(1e-6, float(np.nanpercentile(noise_map, 95))),
				aspect="auto")
			axes[1].set_title(f"Rausch-Niveau-Karte (Block {bs}px)", color="#ccc", fontsize=10)
			axes[1].axis("off")
			axes[1].tick_params(colors="#ccc")
			fig.colorbar(im1, ax=axes[1], fraction=0.046)
			fig.savefig(str(errormap_path), dpi=150, bbox_inches="tight")
			plt.close(fig)

			# ---- Visualisierung: Rausch-Verteilung ----
			hist_path = self.exports_dir / f"{stem}_resample_histogram.png"
			fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#1e1e1e")
			ax.hist(valid, bins=40, color="#0f0", alpha=0.8)
			ax.axvline(sigma_noise, color="#ff9900", linestyle="--", linewidth=1.5,
				label=f"global σ ≈ {sigma_noise:.2f}")
			ax.set_xlabel("Rauschniveau (Std-Abweichung)", color="#ccc")
			ax.set_ylabel("Anzahl Blöcke", color="#ccc")
			ax.set_title(f"Rausch-Verteilung über Bildblöcke — {Path(self.filepath).name}", color="#ccc")
			ax.tick_params(colors="#ccc")
			ax.grid(axis="y", alpha=0.3)
			ax.legend(facecolor="#2a2a2a", labelcolor="#ccc")
			fig.tight_layout()
			fig.savefig(str(hist_path), dpi=150)
			plt.close(fig)

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
				f"\n"
				f"Error-Map: {errormap_path}\n"
				f"Histogram: {hist_path}\n"
			)
			self.signals.result.emit("resample", text, str(errormap_path), str(hist_path))

		except Exception as e:
			import traceback
			traceback.print_exc()
			self.signals.error.emit("resample", str(e))