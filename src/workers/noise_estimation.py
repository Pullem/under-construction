"""
NoiseEstimatorWorker - Rauschprofil über Frames eines Videos.

Schätzt pro Frame eine robuste Rauschstärke σ (MAD auf Hochpass-Resten)
und aggregiert die Werte zu einem Profil (Verteilung über Frames).
Ergebnisse sind Indikatoren/Scores, keine Echtheits-Aussage
(AGENTS.md Abschnitt 13).
"""

import logging
import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import analysis_error


logger = logging.getLogger(__name__)

# Schwellwerte für die Indikator-Bewertung (über das Frame-Profil)
CV_SUSPECT = 0.35       # Variationskoeffizient der σ-Werte über Frames
SIGMA_VERY_LOW = 0.5    # unterhalb: sehr niedriges Rauschniveau
SIGMA_VERY_HIGH = 6.0   # oberhalb: sehr hohes Rauschniveau


class NoiseEstimatorWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)           # mode, error_json


def estimate_frame_sigma(gray, blur_sigma=1.5):
	"""Robuste Rauschschätzung σ eines Frames (in Graustufen-Werten).

	Verfahren: Hochpass-Rest (Gaussian-Blur) und MAD-basierte Schätzung
	sigma = 1.4826 * median(|x - median(x)|) – identisch zur Rausch-
	schätzung in ResamplingWorker, damit Werte projektweit vergleichbar sind.
	"""
	import cv2
	gray = np.asarray(gray, dtype=np.float32)
	hp = gray - cv2.GaussianBlur(gray, (0, 0), blur_sigma)
	med = float(np.median(hp))
	return float(1.4826 * np.median(np.abs(hp - med)))


def summarize_noise_profile(sigmas):
	"""Aggregiert die σ-Werte mehrerer Frames zu Kennzahlen des Profils."""
	arr = np.asarray(list(sigmas), dtype=np.float64)
	arr = arr[np.isfinite(arr)]
	if arr.size == 0:
		return {
			"count": 0,
			"sigma_median": 0.0,
			"sigma_mean": 0.0,
			"sigma_std": 0.0,
			"sigma_min": 0.0,
			"sigma_max": 0.0,
			"sigma_q1": 0.0,
			"sigma_q3": 0.0,
			"cv_frames": 0.0,
		}
	q1, median, q3 = (float(v) for v in np.percentile(arr, [25, 50, 75]))
	mean = float(arr.mean())
	std = float(arr.std())
	return {
		"count": int(arr.size),
		"sigma_median": median,
		"sigma_mean": mean,
		"sigma_std": std,
		"sigma_min": float(arr.min()),
		"sigma_max": float(arr.max()),
		"sigma_q1": q1,
		"sigma_q3": q3,
		"cv_frames": std / max(mean, 1e-12),
	}


def classify_noise_profile(metrics):
	"""Bewertet ein Rauschprofil als (indikator_vorhanden, ergebnis_text).

	Liefert ausschließlich technische Indikatoren, keine Aussage darüber,
	ob das Material echt oder manipuliert ist (AGENTS.md Abschnitt 13).
	"""
	count = metrics.get("count", 0)
	if count == 0:
		return False, "Kein Rauschprofil berechenbar (keine Frames analysiert)"

	cv = metrics.get("cv_frames", 0.0)
	median = metrics.get("sigma_median", 0.0)

	if cv > CV_SUSPECT:
		return True, (
			"⚠️  Stark variierendes Rauschniveau über die Frames – Indikator für "
			"Schnitte, wechselnde Aufnahmebedingungen oder nachträgliche Bearbeitung "
			"(z. B. teilweise Entrauschung)")
	if median < SIGMA_VERY_LOW:
		return True, (
			"⚠️  Sehr niedriges Rauschniveau – Indikator für starke Entrauschung, "
			"Skalierung oder synthetisches/gerendertes Material")
	if median > SIGMA_VERY_HIGH:
		return False, (
			"Sehr hohes Rauschniveau – typisch für stark rauschendes, z. B. schwach "
			"belichtetes oder stark vergrößertes Material (technische Auffälligkeit)")
	return False, "Gleichmäßiges, unauffälliges Rauschniveau über die Frames"


class NoiseEstimatorWorker(QRunnable):
	"""Rauschprofil über gleichmäßig verteilte Frames eines Videos.

	Analysiert NUM_FRAMES Frames (oder bei unbekannter Frame-Anzahl die
	ersten NUM_FRAMES), schätzt je Frame σ robust und liefert das
	aggregierte Profil als Textbericht + Datenstruktur. Läuft wie alle
	Analyse-Worker im QThreadPool, nie im GUI-Thread (AGENTS.md Abschnitt 3).
	"""

	NUM_FRAMES = 24
	MAX_ANALYSIS_DIM = 4096   # wie ResamplingWorker
	BLUR_SIGMA = 1.5          # wie ResamplingWorker

	def __init__(self, filepath, num_frames=NUM_FRAMES):
		super().__init__()
		self.filepath = filepath
		self.num_frames = max(1, int(num_frames))
		self.signals = NoiseEstimatorWorkerSignals()

	def _measure_frame(self, frame):
		"""Ein BGR-Frame -> (sigma, helligkeit, begrenzt, breite, hoehe)."""
		import cv2
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
		h, w = gray.shape
		scaled = False
		max_dim = max(h, w)
		if max_dim > self.MAX_ANALYSIS_DIM:
			scale = self.MAX_ANALYSIS_DIM / max_dim
			gray = cv2.resize(
				gray, (max(1, int(w * scale)), max(1, int(h * scale))),
				interpolation=cv2.INTER_AREA)
			scaled = True
		sigma = estimate_frame_sigma(gray, self.BLUR_SIGMA)
		return sigma, float(gray.mean()), scaled, gray.shape[1], gray.shape[0]

	def run(self):
		started = time.monotonic()
		cap = None
		try:
			import cv2

			path = Path(self.filepath)
			logger.info("Noise profile analysis started for %s", path.name)

			cap = cv2.VideoCapture(str(path))
			if not cap.isOpened():
				raise RuntimeError(f"Datei konnte nicht geöffnet werden: {path.name}")

			total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
			measurements = []   # (frame_index, sigma, helligkeit)
			failed = 0
			scaled = False
			width = height = 0
			sampling = "evenly"

			if total > 0:
				targets = np.unique(
					np.linspace(0, total - 1, self.num_frames).astype(int))
				for target in targets:
					cap.set(cv2.CAP_PROP_POS_FRAMES, int(target))
					ret, frame = cap.read()
					if not ret:
						failed += 1
						logger.debug("Frame %d konnte nicht gelesen werden", int(target))
						continue
					sigma, bri, frame_scaled, width, height = self._measure_frame(frame)
					scaled = scaled or frame_scaled
					measurements.append((int(target), sigma, bri))
					del frame
			else:
				sampling = "sequential_start"
				logger.warning(
					"Frame-Anzahl unbekannt für %s – analysiere erste %d Frames",
					path.name, self.num_frames)
				idx = 0
				while idx < self.num_frames:
					ret, frame = cap.read()
					if not ret:
						break
					sigma, bri, frame_scaled, width, height = self._measure_frame(frame)
					scaled = scaled or frame_scaled
					measurements.append((idx, sigma, bri))
					del frame
					idx += 1

			if not measurements:
				raise RuntimeError("Keine analysierbaren Frames gelesen")

			frame_indices = np.asarray([m[0] for m in measurements], dtype=np.int64)
			sigmas = np.asarray([m[1] for m in measurements], dtype=np.float64)
			brightness = np.asarray([m[2] for m in measurements], dtype=np.float64)

			metrics = summarize_noise_profile(sigmas)
			metrics.update({
				"total_frames": total,
				"frames_failed": failed,
				"sampling": sampling,
				"scaled": scaled,
				"width": width,
				"height": height,
				"blur_sigma": self.BLUR_SIGMA,
				"brightness_mean": float(brightness.mean()),
			})
			indicator, verdict = classify_noise_profile(metrics)

			sampling_txt = (
				f"{metrics['count']} von {total} Frames (gleichmäßig verteilt)"
				if total > 0 else
				f"erste {metrics['count']} Frames (Gesamtzahl unbekannt)")
			size_txt = f"{width}×{height}" + (
				f" (auf max. {self.MAX_ANALYSIS_DIM} px begrenzt)" if scaled else "")

			elapsed = time.monotonic() - started
			text = (
				f"Rauschprofil-Analyse: {path.name}\n"
				f"{'-' * 50}\n"
				f"Methode: MAD-Schätzung σ je Frame auf Hochpass-Resten "
				f"(Gaussian σ={self.BLUR_SIGMA})\n"
				f"Analysierte Frames: {sampling_txt}\n"
				f"Analysierte Auflösung: {size_txt}\n"
				f"\n"
				f"[Rauschprofil über Frames]\n"
				f"σ Median: {metrics['sigma_median']:.2f}, "
				f"Mittel: {metrics['sigma_mean']:.2f}, "
				f"Std: {metrics['sigma_std']:.2f}\n"
				f"σ Min: {metrics['sigma_min']:.2f}, "
				f"Max: {metrics['sigma_max']:.2f}, "
				f"Quartile Q1/Q3: {metrics['sigma_q1']:.2f}/{metrics['sigma_q3']:.2f}\n"
				f"Variationskoeffizient über Frames: {metrics['cv_frames']:.2f}\n"
				f"Mittlere Helligkeit (Kontextwert): {metrics['brightness_mean']:.1f}\n"
				f"Fehlerhafte Frame-Lesevorgänge: {failed}\n"
				f"Ergebnis: {verdict}\n"
				f"\n"
				f"Hinweis: technischer Indikator – keine Aussage darüber, "
				f"ob das Material echt oder manipuliert ist.\n"
			)

			data = {
				"sigmas": sigmas,
				"frame_indices": frame_indices,
				"brightness": brightness,
				"metrics": metrics,
			}

			logger.info(
				"Noise profile analysis finished for %s: frames=%d, median_sigma=%.2f, "
				"cv=%.2f, indicator=%s, duration=%.1fs",
				path.name, metrics["count"], metrics["sigma_median"],
				metrics["cv_frames"], indicator, elapsed)
			self.signals.result.emit("noise", text, data)

		except Exception as e:
			err = analysis_error("Noise profile analysis failed", mode="noise",
								 filepath=self.filepath, exc=e)
			self.signals.error.emit("noise", err.to_json())
			logger.exception("Noise profile analysis failed for %s", self.filepath)
		finally:
			if cap is not None:
				cap.release()
