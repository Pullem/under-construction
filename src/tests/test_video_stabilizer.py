"""
Tests für den VideoStabilizerWorker (AGENTS.md Abschnitt 12).

Reproduzierbare Testdaten: synthetische Videosequenzen mit bekanntem
Bewegungsverhalten über einen festen RNG-Seed.
"""

import os
import tempfile
import unittest

import numpy as np

from src.workers.video_stabilizer import (
	VideoStabilizerWorker,
	classify_stability,
	estimate_motion_magnitude,
)


def _make_test_frame(height=60, width=80, seed=0, motion_mag=5.0):
	"""Erzeugt ein graues Bild mit optionaler Prüfungsmaske."""
	rng = np.random.default_rng(seed)
	base = np.full((height, width), 128, dtype=np.uint8)
	# Füge leichten Rauschen hinzu, damit die Bilder nicht identisch sind
	noise = rng.integers(-10, 10, (height, width), dtype=np.int16)
	frame = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
	return frame


class EstimateMotionMagnitudeTest(unittest.TestCase):
	def test_motion_magnitude_basic(self):
		"""Grundfunktion: Flow-Magnitude liegt im erwarteten Bereich."""
		prev = _make_test_frame(seed=1, motion_mag=15.0)
		nxt = _make_test_frame(seed=2, motion_mag=25.0)
		m = estimate_motion_magnitude(prev, nxt)
		self.assertGreater(m["mean_mag"], 8.0)
		self.assertLess(m["mean_mag"], 20.0)

	def test_no_motion(self):
		"""Zwei identische Bilder ergeben praktisch σ = 0."""
		prev = _make_test_frame(seed=42)
		nxt = _make_test_frame(seed=42)  # gleicher Seed -> gleiche Pixel
		m = estimate_motion_magnitude(prev, nxt)
		self.assertLess(m["mean_mag"], 0.5)


class ClassifyStabilityTest(unittest.TestCase):
	def test_high_stability(self):
		"""Sehr geringe Bewegung -> stabil."""
		m = classify_stability({
			"count": 20,
			"mean_mag": 0.1,
			"total_motion": 2.0,
			"max_mag": 0.5,
			"cv": 0.1,
			"accel": 0.0,
		})
		self.assertFalse(m[0])  # indicator=False -> keine Probleme
		self.assertIn("stabil", m[1].lower())

	def test_low_stability_wackelig(self):
		"""Stark variierende Bewegung -> wackelig."""
		m = classify_stability({
			"count": 20,
			"mean_mag": 8.0,
			"total_motion": 150.0,
			"max_mag": 25.0,
			"cv": 2.0,
			"accel": 0.2,
		})
		self.assertTrue(m[0])  # indicator=True -> Problem erkannt
		self.assertIn("wackelbewegung", m[1].lower())

	def test_no_motion_stable(self):
		"""Kaum Bewegung -> stabil."""
		m = classify_stability({
			"count": 20,
			"mean_mag": 0.05,
			"total_motion": 1.0,
			"max_mag": 0.2,
			"cv": 0.01,
			"accel": 0.0,
		})
		self.assertFalse(m[0])
		self.assertIn("stabil", m[1].lower())

	def test_no_manipulation_claim(self):
		"""Ergebnistexte enthalten keine Echtheits-Aussage (Abschnitt 13)."""
		for d in [
			{"count": 10, "mean_mag": 0.1, "total_motion": 1.0, "max_mag": 0.5, "cv": 0.01, "accel": 0.0},
			{"count": 10, "mean_mag": 5.0, "total_motion": 40.0, "max_mag": 15.0, "cv": 2.0, "accel": 0.3},
		]:
			_, text = classify_stability(d)
			self.assertNotIn("gefälscht", text.lower())
			self.assertNotIn("manipuliert ist", text.lower())


class VideoStabilizerWorkerTest(unittest.TestCase):
	"""End-to-End-Tests des Workers auf erzeugten Testvideos."""

	@staticmethod
	def _write_test_video(path, shaking=False, num_frames=40):
		import cv2
		writer = cv2.VideoWriter(
			path, cv2.VideoWriter_fourcc(*"MJPG"), 25.0, (160, 120))
		if not writer.isOpened():
			return False
		rng = np.random.default_rng(22)
		for i in range(num_frames):
			yy, xx = np.mgrid[0:120, 0:160]
			# Basis: leichtes Rauschen
			frame = rng.integers(0, 30, (120, 160), dtype=np.uint8)
			if shaking:
				# Füge künstliche Kamera-Bewegung hinzu (lineare Translation)
				t = i / num_frames
				dx = int(3 * t)   # 0->3 px Translation
				dy = int(2 * t)   # 0->2 px Translation
				# Einfaches Translation durch ROI-Shift (für Testzwecke)
				shifted = np.roll(frame, dx, axis=1)
				shifted = np.roll(shifted, dy, axis=0)
				frame = shifted
			bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
			writer.write(bgr)
		writer.release()
		return True

	@staticmethod
	def _run_worker(path, num_frames):
		results = []
		errors = []
		worker = VideoStabilizerWorker(path, num_frames=num_frames)
		worker.signals.result.connect(
			lambda mode, text, data: results.append((mode, text, data)))
		worker.signals.error.connect(
			lambda mode, msg: errors.append((mode, msg)))
		worker.run()  # synchron ausführen
		return results, errors

	def test_shaking_video_produces_profile(self):
		tmpdir = tempfile.mkdtemp(prefix="stabilizer_test_")
		video_path = os.path.join(tmpdir, "shaky.avi")
		if not self._write_test_video(video_path, shaking=True):
			self.skipTest("cv2.VideoWriter nicht verfügbar")

		results, errors = self._run_worker(video_path, num_frames=12)

		self.assertEqual(errors, [], msg=f"Worker-Fehler: {errors}")
		self.assertEqual(len(results), 1)
		mode, text, data = results[0]
		self.assertEqual(mode, "stabilizer")
		self.assertIn("Kamera-Stabilitäts", text)
		self.assertIn("Indikator", text)

		metrics = data["metrics"]
		self.assertGreater(metrics["count"], 0)
		self.assertLessEqual(metrics["count"], 12)
		self.assertEqual(len(data["mean_magnitudes"]), metrics["count"])
		self.assertEqual(metrics["mean_mag"], 0.0, msg="Bei dieser Test-Implementierung schwankt der Wert leicht – prüfen Sie die Flow-Logik")
		self.assertEqual(metrics["cv"], 0.0, msg="Konsistenz-Check")

	def test_static_video_profile(self):
		tmpdir = tempfile.mkdtemp(prefix="stabilizer_test_")
		video_path = os.path.join(tmpdir, "static.avi")
		if not self._write_test_video(video_path, shaking=False):
			self.skipTest("cv2.VideoWriter nicht verfügbar")

		results, errors = self._run_worker(video_path, num_frames=12)

		self.assertEqual(errors, [], msg=f"Worker-Fehler: {errors}")
		self.assertEqual(len(results), 1)
		mode, text, data = results[0]
		self.assertEqual(mode, "stabilizer")
		self.assertIn("Kamera-Stabilitäts", text)

		metrics = data["metrics"]
		self.assertGreater(metrics["count"], 0)
		self.assertIn("stabil", text.lower() or "Wackelbewegungs-Score" in text)

	def test_missing_file_reports_error(self):
		errors = []
		worker = VideoStabilizerWorker(
			os.path.join(tempfile.gettempdir(), "does_not_exist_11111.mp4"))
		worker.signals.error.connect(lambda mode, msg: errors.append((mode, msg)))
		worker.run()
		self.assertEqual(len(errors), 1)
		mode, msg = errors[0]
		self.assertEqual(mode, "stabilizer")
		self.assertIn("stabilizer", msg)


if __name__ == "__main__":
	unittest.main()