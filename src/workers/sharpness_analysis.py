"""
SharpnessDetectorWorker - Schärfe-/Unschärfe-Indikatoren pro Frame.

Schätzt pro Frame zwei Schärfe-Metriken (Laplacian-Varianz und
Tenengrad-Energie) und aggregiert die Werte zu einem Profil über die
Laufzeit. Ergebnisse sind Indikatoren/Scores, keine Echtheits-Aussage
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
LAP_VAR_VERY_LOW = 50.0  # unterhalb: sehr niedrige Schärfe (8-Bit-Graustufen)
CV_SUSPECT = 0.8         # Variationskoeffizient der Schärfe über Frames


class SharpnessDetectorWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)           # mode, error_json


def estimate_frame_sharpness(gray):
	"""Schärfe-Metriken eines Frames als dict.

	* lap_var: Varianz des Laplacians – klassische Unschärfe-Metrik
	  (niedrige Werte deuten auf Unschärfe hin)
	* tenengrad: mittlere Sobel-Energie (Gradientenenergie)

	Beide Metriken sind inhaltsabhängig: strukturarme Szenen liegen auch
	bei scharfem Material natürlicherweise niedriger.
	"""
	import cv2
	gray = np.asarray(gray, dtype=np.float32)
	# Hinweis: OpenCV 5 unterstützt keine Kombination CV_32F -> CV_64F;
	# daher wird durchgängig CV_32F gerechnet und die Varianz via
	# numpy in float64 akkumuliert.
	lap = cv2.Laplacian(gray, cv2.CV_32F)
	gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
	gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
	return {
		"lap_var": float(np.var(lap, dtype=np.float64)),
		"tenengrad": float(np.mean(gx * gx + gy * gy, dtype=np.float64)),
	}


def summarize_profile(values):
	"""Aggregiert eine Werte-Reihe (z. B. Schärfe über Frames) zu Kennzahlen."""
	arr = np.asarray(list(values), dtype=np.float64)
	arr = arr[np.isfinite(arr)]
	if arr.size == 0:
		return {
			"count": 0,
			"median": 0.0,
			"mean": 0.0,
			"std": 0.0,
			"min": 0.0,
			"max": 0.0,
			"q1": 0.0,
			"q3": 0.0,
			"cv": 0.0,
		}
	q1, median, q3 = (float(v) for v in np.percentile(arr, [25, 50, 75]))
	mean = float(arr.mean())
	std = float(arr.std())
	return {
		"count": int(arr.size),
		"median": median,
		"mean": mean,
		"std": std,
		"min": float(arr.min()),
		"max": float(arr.max()),
		"q1": q1,
		"q3": q3,
		"cv": std / max(mean, 1e-12),
	}


def classify_sharpness_profile(metrics):
	"""Bewertet ein Schärfe-Profil als (indikator_vorhanden, ergebnis_text).

	Liefert ausschließlich technische Indikatoren, keine Aussage darüber,
	ob das Material echt oder manipuliert ist (AGENTS.md Abschnitt 13).
	"""
	count = metrics.get("count", 0)
	if count == 0:
		return False, "Kein Schärfe-Profil berechenbar (keine Frames analysiert)"

	cv = metrics.get("cv_frames", 0.0)
	median = metrics.get("lap_var_median", 0.0)

	if median < LAP_VAR_VERY_LOW:
		return True, (
			"⚠️  Sehr niedrige Schärfe über die gesamte Laufzeit – Indikator für "
			"Unschärfe, starke Skalierung, Entrauschung oder synthetisches/"
			"gerendertes Material")
	if cv > CV_SUSPECT:
		return True, (
			"⚠️  Stark variierende Schärfe über die Frames – Indikator für "
			"Schnitte, Fokus-/Belichtungswechsel oder nachträgliche teilweise "
			"Bearbeitung (z. B. lokale Unschärfe-Maskierung)")
	return False, "Gleichmäßige, unauffällige Schärfe über die Frames"


class SharpnessDetectorWorker(QRunnable):
	"""Schärfe-/Unschärfe-Indikatoren über gleichmäßig verteilte Frames.

	Analysiert NUM_FRAMES Frames (oder bei unbekannter Frame-Anzahl die
	ersten NUM_FRAMES), misst je Frame Laplacian-Varianz und Tenengrad-
	Energie und liefert das aggregierte Profil als Textbericht +
	Datenstruktur. Läuft wie alle Analyse-Worker im QThreadPool, nie im
	GUI-Thread (AGENTS.md Abschnitt 3).
	"""

	NUM_FRAMES = 24
	MAX_ANALYSIS_DIM = 4096  # wie ResamplingWorker/NoiseEstimatorWorker

	def __init__(self, filepath, num_frames=NUM_FRAMES):
		super().__init__()
		self.filepath = filepath
		self.num_frames = max(1, int(num_frames))
		self.signals = SharpnessDetectorWorkerSignals()

	def _measure_frame(self, frame):
		"""Ein BGR-Frame -> (lap_var, tenengrad, begrenzt, breite, hoehe)."""
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
		metrics = estimate_frame_sharpness(gray)
		return metrics["lap_var"], metrics["tenengrad"], scaled, gray.shape[1], gray.shape[0]

	def run(self):
		started = time.monotonic()
		cap = None
		try:
			import cv2

			path = Path(self.filepath)
			logger.info("Sharpness analysis started for %s", path.name)

			cap = cv2.VideoCapture(str(path))
			if not cap.isOpened():
				raise RuntimeError(f"Datei konnte nicht geöffnet werden: {path.name}")

			total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
			measurements = []   # (frame_index, lap_var, tenengrad)
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
					lap_var, tenengrad, frame_scaled, width, height = self._measure_frame(frame)
					scaled = scaled or frame_scaled
					measurements.append((int(target), lap_var, tenengrad))
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
					lap_var, tenengrad, frame_scaled, width, height = self._measure_frame(frame)
					scaled = scaled or frame_scaled
					measurements.append((idx, lap_var, tenengrad))
					del frame
					idx += 1

			if not measurements:
				raise RuntimeError("Keine analysierbaren Frames gelesen")

			frame_indices = np.asarray([m[0] for m in measurements], dtype=np.int64)
			lap_vars = np.asarray([m[1] for m in measurements], dtype=np.float64)
			tenegrads = np.asarray([m[2] for m in measurements], dtype=np.float64)

			lap = summarize_profile(lap_vars)
			ten = summarize_profile(tenegrads)
			metrics = {
				"lap_var_median": lap["median"],
				"lap_var_mean": lap["mean"],
				"lap_var_std": lap["std"],
				"lap_var_min": lap["min"],
				"lap_var_max": lap["max"],
				"lap_var_q1": lap["q1"],
				"lap_var_q3": lap["q3"],
				"cv_frames": lap["cv"],
				"tenengrad_median": ten["median"],
				"tenengrad_mean": ten["mean"],
				"count": lap["count"],
				"total_frames": total,
				"frames_failed": failed,
				"sampling": sampling,
				"scaled": scaled,
				"width": width,
				"height": height,
			}
			indicator, verdict = classify_sharpness_profile(metrics)

			sampling_txt = (
				f"{metrics['count']} von {total} Frames (gleichmäßig verteilt)"
				if total > 0 else
				f"erste {metrics['count']} Frames (Gesamtzahl unbekannt)")
			size_txt = f"{width}×{height}" + (
				f" (auf max. {self.MAX_ANALYSIS_DIM} px begrenzt)" if scaled else "")

			elapsed = time.monotonic() - started
			text = (
				f"Schärfe-Analyse: {path.name}\n"
				f"{'-' * 50}\n"
				f"Methode: Laplacian-Varianz und Tenengrad-Energie je Frame\n"
				f"Analysierte Frames: {sampling_txt}\n"
				f"Analysierte Auflösung: {size_txt}\n"
				f"\n"
				f"[Schärfe über Frames]\n"
				f"Laplacian-Varianz – Median: {metrics['lap_var_median']:.1f}, "
				f"Mittel: {metrics['lap_var_mean']:.1f}, "
				f"Std: {metrics['lap_var_std']:.1f}\n"
				f"Laplacian-Varianz – Min: {metrics['lap_var_min']:.1f}, "
				f"Max: {metrics['lap_var_max']:.1f}, "
				f"Quartile Q1/Q3: {metrics['lap_var_q1']:.1f}/{metrics['lap_var_q3']:.1f}\n"
				f"Tenengrad-Energie – Median: {metrics['tenengrad_median']:.1f}, "
				f"Mittel: {metrics['tenengrad_mean']:.1f}\n"
				f"Variationskoeffizient (Laplacian) über Frames: {metrics['cv_frames']:.2f}\n"
				f"Fehlerhafte Frame-Lesevorgänge: {failed}\n"
				f"Ergebnis: {verdict}\n"
				f"\n"
				f"Hinweis: Schärfe-Metriken sind inhaltsabhängig (strukturarme Szenen "
				f"liegen natürlicherweise niedriger) – technischer Indikator, keine "
				f"Aussage darüber, ob das Material echt oder manipuliert ist.\n"
			)

			data = {
				"lap_var": lap_vars,
				"tenengrad": tenegrads,
				"frame_indices": frame_indices,
				"metrics": metrics,
			}

			logger.info(
				"Sharpness analysis finished for %s: frames=%d, lap_var_median=%.1f, "
				"cv=%.2f, indicator=%s, duration=%.1fs",
				path.name, metrics["count"], metrics["lap_var_median"],
				metrics["cv_frames"], indicator, elapsed)
			self.signals.result.emit("sharpness", text, data)

		except Exception as e:
			err = analysis_error("Sharpness analysis failed", mode="sharpness",
								 filepath=self.filepath, exc=e)
			self.signals.error.emit("sharpness", err.to_json())
			logger.exception("Sharpness analysis failed for %s", self.filepath)
		finally:
			if cap is not None:
				cap.release()
