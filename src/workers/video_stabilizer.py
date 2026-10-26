"""
VideoStabilizerWorker - Kamerastabilitäts-/Wackelbewegungs-Analyse.

Misst über Frame-Paare die globale Kamerabewegung (Translation und Rotation)
und aggregiert einen Stabilitäts-Score. Das Ergebnis ist ein technischer
Indikator für Kamerabewegung, keine Aussage über Manipulation (AGENTS.md Abschnitt 13).

Die Implementierung nutzt Dense Optical Flow (Farneback) zwischen
gleichmäßig verteilten Frame-Paaren und akkumuliert die Bewegungsmagnitude.
"""

import logging
import time
import cv2
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import analysis_error


logger = logging.getLogger(__name__)

# Schwellwerte für die Indikator-Bewertung
STABILITY_HIGH = 0.8       # Stabilität: hoher Score = wenig Wackeln
STABILITY_LOW = 3.0        # Schwellwert für "wackelig" (akkumulierte px/Frame)
CV_SUSPECT = 1.5           # Variationskoeffizient über Frame-Paare


class VideoStabilizerWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)  # mode, text_result, data
	error = pyqtSignal(str, str)           # mode, error_json


def _as_uint8(img):
	"""Hilfsfunktion: sicher nach uint8 konvertieren für Optical Flow."""
	arr = np.asarray(img)
	if arr.dtype != np.uint8:
		arr = np.clip(arr, 0, 255).astype(np.uint8)
	return np.ascontiguousarray(arr)


def estimate_motion_magnitude(prev_gray, next_gray):
	"""Dense Optical Flow Magnitude zwischen zwei Graustufen-Frames.

	Liefert:
	* mean_mag: mittlere Flussmagnitude in px/Frame
* total_motion: akkumulierte Bewegung über alle Pixel
* max_mag: maximale Einzelmagnitude
"""
	import cv2
	prev = _as_uint8(prev_gray)
	nxt = _as_uint8(next_gray)
	flow = cv2.calcOpticalFlowFarneback(
		prev, nxt, None,
		pyr_scale=0.5, levels=3, winsize=15,
		iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
	mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
	return {
		"mean_mag": float(mag.mean()),
		"total_mag": float(mag.sum()),
		"max_mag": float(mag.max()),
	}


def classify_stability(metrics):
	"""Bewertet die Kamerastabilität als (indikator_vorhanden, ergebnis_text).

	Liefert ausschließlich technische Indikatoren, keine Echtheits-Aussage
	(AGENTS.md Abschnitt 13).
	"""
	count = metrics.get("count", 0)
	if count == 0:
		return False, "Kein Stabilitätsprofil berechenbar (keine Frame-Paare analysiert)"

	cv = metrics.get("cv", 0.0)
	mean_mag = metrics.get("mean_mag", 0.0)
	total_motion = metrics.get("total_motion", 0.0)
	accel = metrics.get("accel", 0.0)

	if cv > CV_SUSPECT:
		return True, (
			"⚠️  Stark variierende Wackelbewegung – Indikator für unsichere "
			"Kameraführung, Stativ-Unterstützung unzureichend oder "
			"nachträgliche Kamera-Shake-Redukktion notwendig")
	if mean_mag < 0.3:
		return False, (
			"Sehr geringe globale Bewegung – Indikator für stabilen Einsatz "
			"(z. B. Trippod, Monopod oder Bildstabilisierung aktiv)")
	if total_motion / max(count, 1) < STABILITY_HIGH:
		return True, (
			"Wackelbewegungs-Score niedrig – Indikator für überwiegend stabile "
			"Kameraführung (Score: {:.2f})".format(total_motion / max(count, 1)))
	# Akzelerations-Check: wenn die Bewegung pro Paar zunimmt
	if accel > 0.1:
		return True, (
			"⚠️  Zunehmende Bewegung über die Laufzeit – Indikator für "
			"allmählich unsicherer werdende Kameraführung oder auslaufendes "
			"Stativ")
	return False, "Gleichmäßige Bewegung – keine auffälligen Stabilitäts-Probleme"


class VideoStabilizerWorker(QRunnable):
	"""Kamerastabilitäts-Analyse über Frame-Paare eines Videos.

	Misst je Frame-Paar die globale Kamerabewegung (magnitude des Optical
	Flow) und aggregiert diese zu einem Stabilitäts-Score über die gesamte
	Laufzeit. Läuft wie alle Analyse-Worker im QThreadPool, nie im
	GUI-Thread (AGENTS.md Abschnitt 3).
	"""

	NUM_FRAMES = 30           # Anzahl Frame-Paare (mehr als Motion, für Stabilität)
	MAX_FLOW_DIM = 480        # Flow-Resize-Grenze für Tempo

	def __init__(self, filepath, num_frames=NUM_FRAMES):
		super().__init__()
		self.filepath = filepath
		self.num_frames = max(1, int(num_frames))
		self.signals = VideoStabilizerWorkerSignals()

	def _prepare_gray(self, frame):
		"""BGR-Frame -> uint8-Graustufen, auf MAX_FLOW_DIM begrenzt."""
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
			logger.info("Video stabilizer analysis started for %s", path.name)

			cap = cv2.VideoCapture(str(path))
			if not cap.isOpened():
				raise RuntimeError(f"Datei konnte nicht geöffnet werden: {path.name}")

			total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
			measurements = []   # (frame_index, mean_mag, total_mag, max_mag)
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
					m = estimate_motion_magnitude(prev, nxt)
					flow_h, flow_w = prev.shape
					measurements.append((t, m["mean_mag"], m["total_mag"], m["max_mag"]))
					del frame1, frame2
			else:
				sampling = "sequential"
				logger.warning(
					"Frame-Anzahl unbekannt für %s – analysiere erste %d Frame-Paare",
					path.name, self.num_frames)
				idx = 0
				ret, prev_frame = cap.read()
				while idx < self.num_frames - 1 and ret:
					ret, next_frame = cap.read()
					if not ret:
						break
					prev = self._prepare_gray(prev_frame)
					nxt = self._prepare_gray(next_frame)
					m = estimate_motion_magnitude(prev, nxt)
					flow_h, flow_w = prev.shape
					measurements.append((idx, m["mean_mag"], m["total_mag"], m["max_mag"]))
					prev_frame = next_frame
					idx += 1

			if not measurements:
				raise RuntimeError("Keine analysierbaren Frame-Paare gelesen")

			frame_indices = np.asarray([m[0] for m in measurements], dtype=np.int64)
			mean_mags = np.asarray([m[1] for m in measurements], dtype=np.float64)
			total_mags = np.asarray([m[2] for m in measurements], dtype=np.float64)
			max_mags = np.asarray([m[3] for m in measurements], dtype=np.float64)

			n = len(mean_mags)
			# Akkumierte Bewegung und einfache "Akzeleration" (Diff des Mittelwerts)
			total_motion = float(total_mags.sum())
			mean_mag = float(mean_mags.mean())
			if n > 1:
				accel = float((mean_mags[-1] - mean_mags[0]) / max(n - 1, 1))
			else:
				accel = 0.0

			cv = float(np.std(mean_mags) / mean_mag) if mean_mag > 0 else 0.0

			metrics = {
				"count": n,
				"mean_mag": mean_mag,
				"total_motion": total_motion,
				"max_mag": float(max_mags.max()),
				"cv": cv,
				"accel": accel,
				"total_frames": total,
				"frames_failed": failed,
				"sampling": sampling,
				"flow_width": flow_w,
				"flow_height": flow_h,
			}
			indicator, verdict = classify_stability(metrics)

			sampling_txt = (
				f"{metrics['count']} von max. {total - 1} möglichen Paaren "
				f"(gleichmäßig verteilt)" if total >= 2 else
				f"{metrics['count']} aufeinanderfolgende Paare am Sequenzanfang")
			size_txt = f"{flow_w}×{flow_h} px (Eingabe auf max. {self.MAX_FLOW_DIM} px begrenzt)"

			elapsed = time.monotonic() - started
			text = (
				f"Kamera-Stabilitäts-Analyse: {path.name}\n"
				f"{'-' * 50}\n"
				f"Methode: Dense Optical Flow (Farneback) je Frame-Paar\n"
				f"Flow-Berechnung: {size_txt}\n"
				f"Analysierte Frame-Paare: {sampling_txt}\n"
				f"\n"
				f"[Kamera-Bewegung]\n"
				f"Mittlere Bewegungsmagnitude: {metrics['mean_mag']:.2f} px/Frame\n"
				f"Maximale Einzel-Magnitude: {metrics['max_mag']:.2f} px/Frame\n"
				f"Akkumulierte Bewegung: {metrics['total_motion']:.1f} px\n"
				f"Variationskoeffizient (CV): {metrics['cv']:.2f}\n"
				f"Akzeleration (Pro-Frame-Change): {metrics['accel']:.3f} px/Frame\n"
				f"\n"
				f"[Stabilitäts-Bewertung]\n"
				f"{verdict}\n"
				f"\n"
				f"Hinweis: technischer Indikator – keine Aussage darüber, "
				f"ob das Material echt oder manipuliert ist.\n"
			)

			data = {
				"mean_magnitudes": mean_mags,
				"total_magnitudes": total_mags,
				"max_magnitudes": max_mags,
				"frame_indices": frame_indices,
				"metrics": metrics,
			}

			logger.info(
				"Video stabilizer analysis finished for %s: pairs=%d, mean_mag=%.2f, "
				"cv=%.2f, accel=%.3f, indicator=%s, duration=%.1fs",
				path.name, metrics["count"], metrics["mean_mag"], metrics["cv"],
				metrics["accel"], indicator, elapsed)
			self.signals.result.emit("stabilizer", text, data)

		except Exception as e:
			err = analysis_error("Video stabilizer analysis failed", mode="stabilizer",
								 filepath=self.filepath, exc=e)
			self.signals.error.emit("stabilizer", err.to_json())
			logger.exception("Video stabilizer analysis failed for %s", self.filepath)
		finally:
			if cap is not None:
				cap.release()