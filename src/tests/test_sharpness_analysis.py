"""
Tests für den SharpnessDetectorWorker (AGENTS.md Abschnitt 12).

Reproduzierbare Testdaten: synthetische Textur-Muster über einen festen
RNG-Seed.
"""

import os
import tempfile
import unittest

import numpy as np

from src.workers.sharpness_analysis import (
	SharpnessDetectorWorker,
	classify_sharpness_profile,
	estimate_frame_sharpness,
	summarize_profile,
)


def _texture_image(height=256, width=256, seed=3):
	"""Strukturiertes Muster (Schachbrett + Rauschen) als scharfe Testbasis."""
	rng = np.random.default_rng(seed)
	yy, xx = np.mgrid[0:height, 0:width]
	checker = (((yy // 8) + (xx // 8)) % 2).astype(np.float32) * 150.0 + 50.0
	return (checker + rng.normal(0.0, 10.0, checker.shape)).astype(np.float32)


def _profile_metrics(values):
	"""Kennzahlen aus summarize_profile ins classify-Format überführen."""
	s = summarize_profile(values)
	return {
		"count": s["count"],
		"cv_frames": s["cv"],
		"lap_var_median": s["median"],
	}


class EstimateFrameSharpnessTest(unittest.TestCase):
	def test_blurred_lower_than_sharp(self):
		"""Ein unscharfes Bild hat deutlich niedrigere Metriken."""
		import cv2
		sharp = _texture_image()
		blurred = cv2.GaussianBlur(sharp, (0, 0), 3.0)
		m_sharp = estimate_frame_sharpness(sharp)
		m_blur = estimate_frame_sharpness(blurred)
		self.assertGreater(m_sharp["lap_var"], m_blur["lap_var"] * 2.0)
		self.assertGreater(m_sharp["tenengrad"], m_blur["tenengrad"] * 2.0)

	def test_flat_image_near_zero(self):
		"""Ein konstantes Bild hat praktisch keine Schärfe-Energie."""
		m = estimate_frame_sharpness(np.full((128, 128), 128.0, dtype=np.float32))
		self.assertLess(m["lap_var"], 1.0)
		self.assertLess(m["tenengrad"], 1.0)

	def test_output_keys(self):
		m = estimate_frame_sharpness(_texture_image(128, 128))
		self.assertIn("lap_var", m)
		self.assertIn("tenengrad", m)
		self.assertTrue(np.isfinite(m["lap_var"]))
		self.assertTrue(np.isfinite(m["tenengrad"]))

	def test_higher_blur_yields_lower_sharpness(self):
		"""Monotonie: mehr Unschärfe -> niedrigere Laplacian-Varianz."""
		import cv2
		base = _texture_image()
		less = estimate_frame_sharpness(cv2.GaussianBlur(base, (0, 0), 1.0))
		more = estimate_frame_sharpness(cv2.GaussianBlur(base, (0, 0), 4.0))
		self.assertGreater(less["lap_var"], more["lap_var"])


class SummarizeProfileTest(unittest.TestCase):
	def test_constant_profile(self):
		s = summarize_profile([300.0] * 8)
		self.assertEqual(s["count"], 8)
		self.assertAlmostEqual(s["median"], 300.0, places=6)
		self.assertAlmostEqual(s["cv"], 0.0, places=6)

	def test_mixed_profile(self):
		s = summarize_profile([100.0, 100.0, 100.0, 900.0])
		self.assertEqual(s["count"], 4)
		self.assertAlmostEqual(s["median"], 100.0, places=6)
		self.assertAlmostEqual(s["max"], 900.0, places=6)
		self.assertGreater(s["cv"], 0.5)

	def test_nan_filtered(self):
		s = summarize_profile([100.0, float("nan"), 300.0])
		self.assertEqual(s["count"], 2)
		self.assertAlmostEqual(s["median"], 200.0, places=6)

	def test_empty_profile(self):
		s = summarize_profile([])
		self.assertEqual(s["count"], 0)
		self.assertEqual(s["cv"], 0.0)


class ClassifySharpnessProfileTest(unittest.TestCase):
	def test_empty_profile(self):
		indicator, text = classify_sharpness_profile(summarize_profile([]))
		self.assertFalse(indicator)
		self.assertIn("Kein Schärfe-Profil", text)

	def test_very_low_sharpness_is_indicator(self):
		indicator, text = classify_sharpness_profile(
			_profile_metrics([20.0, 22.0, 21.0, 19.0]))
		self.assertTrue(indicator)
		self.assertIn("niedrige Schärfe", text)

	def test_inconsistent_sharpness_is_indicator(self):
		# Ein sehr scharfer Ausreißer in einer ansonsten moderaten Sequenz.
		indicator, text = classify_sharpness_profile(
			_profile_metrics([100.0, 100.0, 100.0, 100.0, 2000.0]))
		self.assertTrue(indicator)
		self.assertIn("variierende Schärfe", text)

	def test_normal_profile(self):
		indicator, text = classify_sharpness_profile(
			_profile_metrics([300.0] * 8))
		self.assertFalse(indicator)
		self.assertIn("unauffällig", text)

	def test_no_manipulation_claim(self):
		"""Ergebnistexte enthalten keine Echtheits-Aussage (Abschnitt 13)."""
		for values in ([300.0] * 8, [10.0] * 5, [100.0, 100.0, 5000.0]):
			_, text = classify_sharpness_profile(_profile_metrics(values))
			self.assertNotIn("gefälscht", text.lower())
			self.assertNotIn("manipuliert ist", text.lower())


class SharpnessDetectorWorkerTest(unittest.TestCase):
	"""End-to-End-Tests des Workers auf erzeugten Testvideos."""

	@staticmethod
	def _write_test_video(path, blurred=False, num_frames=40):
		import cv2
		writer = cv2.VideoWriter(
			path, cv2.VideoWriter_fourcc(*"MJPG"), 25.0, (160, 120))
		if not writer.isOpened():
			return False
		rng = np.random.default_rng(11)
		for i in range(num_frames):
			yy, xx = np.mgrid[0:120, 0:160]
			checker = (((yy // 8) + (xx // 8) + i) % 2).astype(np.float32) * 150.0 + 50.0
			frame = checker + rng.normal(0.0, 10.0, checker.shape).astype(np.float32)
			if blurred:
				frame = cv2.GaussianBlur(frame, (0, 0), 3.0)
			bgr = cv2.cvtColor(np.clip(frame, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
			writer.write(bgr)
		writer.release()
		return True

	@staticmethod
	def _run_worker(path, num_frames):
		results = []
		errors = []
		worker = SharpnessDetectorWorker(path, num_frames=num_frames)
		worker.signals.result.connect(
			lambda mode, text, data: results.append((mode, text, data)))
		worker.signals.error.connect(
			lambda mode, msg: errors.append((mode, msg)))
		worker.run()  # synchron ausführen, Signale sind Direct-Connections
		return results, errors

	def test_sharp_video_produces_profile(self):
		tmpdir = tempfile.mkdtemp(prefix="sharpness_worker_test_")
		video_path = os.path.join(tmpdir, "sharp_test.avi")
		if not self._write_test_video(video_path):
			self.skipTest("cv2.VideoWriter nicht verfügbar")

		results, errors = self._run_worker(video_path, num_frames=8)

		self.assertEqual(errors, [], msg=f"Worker-Fehler: {errors}")
		self.assertEqual(len(results), 1)
		mode, text, data = results[0]
		self.assertEqual(mode, "sharpness")
		self.assertIn("Schärfe-Analyse", text)
		self.assertIn("Indikator", text)

		metrics = data["metrics"]
		self.assertGreater(metrics["count"], 0)
		self.assertLessEqual(metrics["count"], 8)
		self.assertEqual(len(data["lap_var"]), metrics["count"])
		self.assertEqual(len(data["tenengrad"]), metrics["count"])
		self.assertEqual(len(data["frame_indices"]), metrics["count"])
		self.assertGreater(metrics["lap_var_median"], 100.0,
						   "Schachbrett-Video sollte hohe Schärfe haben")
		self.assertEqual(metrics["sampling"], "evenly")

	def test_blurred_frame_lower_than_sharp_frame(self):
		"""Direkter Metriken-Vergleich: unscharfer Frame < scharfer Frame."""
		import cv2
		tmpdir = tempfile.mkdtemp(prefix="sharpness_worker_test_")
		video_path = os.path.join(tmpdir, "sharp_cmp.avi")
		if not self._write_test_video(video_path):
			self.skipTest("cv2.VideoWriter nicht verfügbar")

		cap = cv2.VideoCapture(video_path)
		ret, frame = cap.read()
		cap.release()
		self.assertTrue(ret)

		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
		blurred = cv2.GaussianBlur(gray, (0, 0), 3.0)
		self.assertGreater(
			estimate_frame_sharpness(gray)["lap_var"],
			estimate_frame_sharpness(blurred)["lap_var"])

	def test_missing_file_reports_error(self):
		errors = []
		worker = SharpnessDetectorWorker(
			os.path.join(tempfile.gettempdir(), "does_not_exist_54321.mp4"))
		worker.signals.error.connect(lambda mode, msg: errors.append((mode, msg)))
		worker.run()
		self.assertEqual(len(errors), 1)
		mode, msg = errors[0]
		self.assertEqual(mode, "sharpness")
		self.assertIn("sharpness", msg)


if __name__ == "__main__":
	unittest.main()
