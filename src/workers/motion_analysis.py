"""
MotionAnalyzerWorker - Bewegungsanalyse über Frames eines Videos.

Schätzt je Frame-Paar den Dense Optical Flow (Farneback) und leitet
Bewegungs-Kennzahlen ab: mittlere Flussmagnitude, globale
Kameratranslation und Richtungskohärenz – aggregiert über die Laufzeit.
Ergebnisse sind Indikatoren/technische Beobachtungen, keine
Echtheits-Aussage (AGENTS.md Abschnitt 13).
"""

import logging
import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import analysis_error
from .sharpness_analysis import summarize_profile  # generischer Profil-Helper


logger = logging.getLogger(__name__)

# Schwellwerte für die Indikator-Bewertung (über die Frame-Paare)
CV_SUSPECT = 1.0          # Variationskoeffizient der Bewegung über Paare
VERY_LOW_MOTION = 0.5     # px/Frame: praktisch keine Bewegung
PAN_STRENGTH = 3.0        # px/Frame: dominante Kameratranslation

# Farneback-Parameter der Flow-Schätzung
FLOW_PYR_SCALE = 0.5
FLOW_LEVELS = 3
FLOW_WINSIZE = 15
FLOW_ITERATIONS = 3
FLOW_POLY_N = 5
FLOW_POLY_SIGMA = 1.2


class MotionAnalyzerWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)           # mode, error_json


def estimate_pair_motion(prev_gray, next_gray):
	"""Dense Optical Flow (Farneback) zwischen zwei Frames als dict.

	Erwartet uint8-Graustufenbilder gleicher Größe. Liefert:
	* mean_mag: mittlere Flussmagnitude in px/Frame
	* gdx/gdy: Median-Flussvektor (dominante Translation = Kamerabewegung)
	* coherence: |Median-Vektor| / mittlere Magnitude
	  (1 = einheitliche Translation, niedrig = komplexe/lokale Bewegung)
	"""
	import cv2

	def _as_uint8(img):
		arr = np.asarray(img)
		if arr.dtype != np.uint8:
			arr = np.clip(arr, 0, 255).astype(np.uint8)
		return np.ascontiguousarray(arr)

	prev = _as_uint8(prev_gray)
	nxt = _as_uint8(next_gray)
	flow = cv2.calcOpticalFlowFarneback(
		prev, nxt, None,
		pyr_scale=FLOW_PYR_SCALE, levels=FLOW_LEVELS, winsize=FLOW_WINSIZE,
		iterations=FLOW_ITERATIONS, poly_n=FLOW_POLY_N,
		poly_sigma=FLOW_POLY_SIGMA, flags=0)
	mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
	mean_mag = float(mag.mean())
	gdx = float(np.median(flow[..., 0]))
	gdy = float(np.median(flow[..., 1]))
	return {
		"mean_mag": mean_mag,
		"gdx": gdx,
		"gdy": gdy,
		"coherence": float(np.hypot(gdx, gdy) / max(mean_mag, 1e-6)),
	}


def classify_motion_profile(metrics):
	"""Bewertet ein Bewegungsprofil als (indikator_vorhanden, ergebnis_text).

	Liefert ausschließlich technische Indikatoren/Beobachtungen, keine
	Aussage darüber, ob das Material echt oder manipuliert ist
	(AGENTS.md Abschnitt 13).
	"""
	count = metrics.get("count", 0)
	if count == 0:
		return False, "Kein Bewegungsprofil berechenbar (keine Frame-Paare analysiert)"

	cv = metrics.get("cv", 0.0)
	mean_mag = metrics.get("mean_mag", 0.0)
	pan_strength = metrics.get("pan_strength", 0.0)

	if cv > CV_SUSPECT:
		return True, (
			"⚠️  Stark variierende Bewegung über die Laufzeit – Indikator für "
			"Schnitte, wechselnde Sequenzen oder abrupte Kamerabewegungswechsel")
	if mean_mag < VERY_LOW_MOTION:
		return False, (
			"Kaum Bewegung über die Laufzeit – statische Kamera oder Standbild-"
			"Anteile (technische Beobachtung)")
	if pan_strength > PAN_STRENGTH:
		return False, (
			f"Dominante Kamerabewegung (Translation {pan_strength:.1f} px/Frame) – "
			"technische Beobachtung, typisch für Handheld- oder Fahraufnahmen")
	return False, "Unauffälliges Bewegungsmuster ohne dominante Kameratranslation"


class MotionAnalyzerWorker(QRunnable):
	"""Bewegungsanalyse über gleichmäßig verteilte Frame-Paare.

	Analysiert NUM_FRAMES Frame-Paare (zueinander aufeinanderfolgende
	Frames an NUM_FRAMES Zeitpunkten), schätzt je Paar den Dense Optical
	Flow (Farneback) und liefert das aggregierte Bewegungsprofil als
	Textbericht + Datenstruktur. Läuft wie alle Analyse-Worker im
	QThreadPool, nie im GUI-Thread (AGENTS.md Abschnitt 3).
	"""

	NUM_FRAMES = 24          # Anzahl Frame-Paare
	MAX_FLOW_DIM = 640       # Flow-Wird auf max. dieser Kante berechnet (Tempo)

	def __init__(self, filepath, num_frames=NUM_FRAMES):
		super().__init__()
		self.filepath = filepath
		self.num_frames = max(1, int(num_frames))
		self.signals = MotionAnalyzerWorkerSignals()

	def _prepare_gray(self, frame):
		"""BGR-Frame -> uint8-Graustufen, auf MAX_FLOW_DIM begrenzt."""
		import cv2
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		h, w = gray.shape
		if max(h, w) > self.MAX_FLOW_DIM:
			scale = self.MAX_FLOW_DIM / max(h, w)
			gray = cv2.resize(
				gray, (max(1, int(w * scale)), max(1, int(h * scale))),
				interpolation=cv2.INTER_AREA)
		return gray

	def run(self):
		started = time.monotonic()
		cap = None
		try:
			import cv2

			path = Path(self.filepath)
			logger.info("Motion analysis started for %s", path.name)

			cap = cv2.VideoCapture(str(path))
			if not cap.isOpened():
				raise RuntimeError(f"Datei konnte nicht geöffnet werden: {path.name}")

			total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
			measurements = []   # (frame_index, mean_mag, gdx, gdy, coherence)
			failed = 0
			sampling = "evenly"
			flow_w = flow_h = 0

			if total >= 2:
				targets = np.unique(
					np.linspace(0, total - 2, self.num_frames).astype(int))
				for target in targets:
					t = int(target)
					cap.set(cv2.CAP_PROP_POS_FRAMES, t)
					ret1, frame1 = cap.read()
					cap.set(cv2.CAP_PROP_POS_FRAMES, t + 1)
					ret2, frame2 = cap.read()
					if not (ret1 and ret2):
						failed += 1
						logger.debug("Frame-Paar ab %d konnte nicht gelesen werden", t)
						continue
					prev = self._prepare_gray(frame1)
					nxt = self._prepare_gray(frame2)
					m = estimate_pair_motion(prev, nxt)
					flow_h, flow_w = prev.shape
					measurements.append((t, m["mean_mag"], m["gdx"], m["gdy"], m["coherence"]))
					del frame1, frame2
			else:
				sampling = "sequential"
				logger.warning(
					"Frame-Anzahl unbekannt für %s – analysiere erste aufeinander-"
					"folgende %d Frame-Paare", path.name, self.num_frames)
				ret, prev_frame = cap.read()
				idx = 1
				while ret and len(measurements) < self.num_frames:
					ret, next_frame = cap.read()
					if not ret:
						break
					prev = self._prepare_gray(prev_frame)
					nxt = self._prepare_gray(next_frame)
					m = estimate_pair_motion(prev, nxt)
					flow_h, flow_w = prev.shape
					measurements.append((idx - 1, m["mean_mag"], m["gdx"], m["gdy"], m["coherence"]))
					prev_frame = next_frame
					idx += 1

			if not measurements:
				raise RuntimeError("Keine analysierbaren Frame-Paare gelesen")

			frame_indices = np.asarray([m[0] for m in measurements], dtype=np.int64)
			mean_mags = np.asarray([m[1] for m in measurements], dtype=np.float64)
			gdxs = np.asarray([m[2] for m in measurements], dtype=np.float64)
			gdys = np.asarray([m[3] for m in measurements], dtype=np.float64)
			coherences = np.asarray([m[4] for m in measurements], dtype=np.float64)

			profile = summarize_profile(mean_mags)
			pan_dx = float(gdxs.mean())
			pan_dy = float(gdys.mean())
			metrics = {
				"count": profile["count"],
				"mean_mag": profile["mean"],
				"mean_mag_median": profile["median"],
				"mean_mag_min": profile["min"],
				"mean_mag_max": profile["max"],
				"cv": profile["cv"],
				"pan_dx": pan_dx,
				"pan_dy": pan_dy,
				"pan_strength": float(np.hypot(pan_dx, pan_dy)),
				"coherence_mean": float(coherences.mean()),
				"total_frames": total,
				"frames_failed": failed,
				"sampling": sampling,
				"flow_width": flow_w,
				"flow_height": flow_h,
			}
			indicator, verdict = classify_motion_profile(metrics)
			elapsed = time.monotonic() - started

			sampling_txt = (
				f"{metrics['count']} von max. {total - 1} möglichen Paaren "
				f"(gleichmäßig verteilt)" if total >= 2 else
				f"{metrics['count']} aufeinanderfolgende Paare am Sequenzanfang")
			text = (
				f"Bewegungsanalyse: {path.name}\n"
				f"{'-' * 50}\n"
				f"Methode: Dense Optical Flow (Farneback, {FLOW_LEVELS} Levels, "
				f"Window {FLOW_WINSIZE}) je Frame-Paar\n"
				f"Flow-Berechnung: {flow_w}×{flow_h} px"
				f" (Eingabe auf max. {self.MAX_FLOW_DIM} px begrenzt)\n"
				f"Analysierte Frame-Paare: {sampling_txt}\n"
				f"\n"
				f"[Bewegung über die Laufzeit]\n"
				f"Mittlere Flussmagnitude: {metrics['mean_mag']:.2f} px/Frame "
				f"(Median {metrics['mean_mag_median']:.2f}, "
				f"Min {metrics['mean_mag_min']:.2f}, "
				f"Max {metrics['mean_mag_max']:.2f})\n"
				f"Variationskoeffizient über Paare: {metrics['cv']:.2f}\n"
				f"Globale Translation (Kamerabewegung): dx {metrics['pan_dx']:.2f}, "
				f"dy {metrics['pan_dy']:.2f} px/Frame "
				f"(Stärke {metrics['pan_strength']:.2f})\n"
				f"Richtungskohärenz: {metrics['coherence_mean']:.2f} "
				f"(1 = einheitliche Richtung, niedrig = komplexe Bewegung)\n"
				f"Fehlerhafte Frame-Paare: {failed}\n"
				f"Ergebnis: {verdict}\n"
				f"\n"
				f"Hinweis: technischer Indikator – keine Aussage darüber, "
				f"ob das Material echt oder manipuliert ist.\n"
			)

			data = {
				"mean_magnitudes": mean_mags,
				"global_dx": gdxs,
				"global_dy": gdys,
				"coherence": coherences,
				"frame_indices": frame_indices,
				"metrics": metrics,
			}

			logger.info(
				"Motion analysis finished for %s: pairs=%d, mean_mag=%.2f, cv=%.2f, "
				"pan=%.2f px/Frame, indicator=%s, duration=%.1fs",
				path.name, metrics["count"], metrics["mean_mag"], metrics["cv"],
				metrics["pan_strength"], indicator, elapsed)
			self.signals.result.emit("motion", text, data)

		except Exception as e:
			err = analysis_error("Motion analysis failed", mode="motion",
								 filepath=self.filepath, exc=e)
			self.signals.error.emit("motion", err.to_json())
			logger.exception("Motion analysis failed for %s", self.filepath)
		finally:
			if cap is not None:
				cap.release()
