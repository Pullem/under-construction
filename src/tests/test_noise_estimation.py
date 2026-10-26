"""
Tests für den NoiseEstimatorWorker (AGENTS.md Abschnitt 12).

Reproduzierbare Testdaten: synthetische Frames mit bekanntem Rauschen
über einen festen RNG-Seed.
"""

import os
import tempfile
import unittest

import numpy as np

from src.workers.noise_estimation import (
	NoiseEstimatorWorker,
	classify_noise_profile,
	estimate_frame_sigma,
	summarize_noise_profile,
)


def _gradient_image(height=512, width=512):
	"""Glatter Verlauf als 'Signal'-Basis (ohne Rauschen)."""
	yy, xx = np.mgrid[0:height, 0:width]
	return (40.0 + 60.0 * yy / height + 30.0 * xx / width).astype(np.float32)


class EstimateFrameSigmaTest(unittest.TestCase):
	def test_known_gaussian_noise(self):
		"""σ-Schätzung liegt bei bekanntem Weißrauschen in der Toleranz."""
		rng = np.random.default_rng(42)
		noisy = _gradient_image() + rng.normal(0.0, 5.0, (512, 512)).astype(np.float32)
		sigma = estimate_frame_sigma(noisy)
		self.assertGreater(sigma, 3.75, "Schätzung unterschätzt σ deutlich")
		self.assertLess(sigma, 6.25, "Schätzung überschätzt σ deutlich")

	def test_clean_gradient_is_low(self):
		"""Ein rauschfreier Verlauf ergibt ein sehr kleines σ."""
		sigma = estimate_frame_sigma(_gradient_image())
		self.assertLess(sigma, 0.5)

	def test_flat_image_is_near_zero(self):
		"""Ein konstantes Bild ergibt praktisch σ = 0."""
		sigma = estimate_frame_sigma(np.full((256, 256), 128.0, dtype=np.float32))
		self.assertLess(sigma, 0.05)

	def test_higher_noise_yields_higher_sigma(self):
		"""Monotonie: mehr Rauschen -> größere Schätzung."""
		rng = np.random.default_rng(1)
		base = _gradient_image(256, 256)
		lo = estimate_frame_sigma(base + rng.normal(0.0, 2.0, base.shape).astype(np.float32))
		hi = estimate_frame_sigma(base + rng.normal(0.0, 8.0, base.shape).astype(np.float32))
		self.assertGreater(hi, lo * 2.0)


class SummarizeNoiseProfileTest(unittest.TestCase):
	def test_constant_profile(self):
		m = summarize_noise_profile([2.0] * 8)
		self.assertEqual(m["count"], 8)
		self.assertAlmostEqual(m["sigma_median"], 2.0, places=6)
		self.assertAlmostEqual(m["cv_frames"], 0.0, places=6)
		self.assertAlmostEqual(m["sigma_min"], 2.0, places=6)
		self.assertAlmostEqual(m["sigma_max"], 2.0, places=6)

	def test_mixed_profile(self):
		m = summarize_noise_profile([1.0, 1.0, 1.0, 5.0])
		self.assertEqual(m["count"], 4)
		self.assertAlmostEqual(m["sigma_median"], 1.0, places=6)
		self.assertAlmostEqual(m["sigma_max"], 5.0, places=6)
		self.assertAlmostEqual(m["sigma_mean"], 2.0, places=6)
		self.assertGreater(m["cv_frames"], 0.3)

	def test_nan_values_are_filtered(self):
		m = summarize_noise_profile([1.0, float("nan"), 3.0])
		self.assertEqual(m["count"], 2)
		self.assertAlmostEqual(m["sigma_median"], 2.0, places=6)

	def test_empty_profile_does_not_crash(self):
		m = summarize_noise_profile([])
		self.assertEqual(m["count"], 0)
		self.assertEqual(m["cv_frames"], 0.0)


class ClassifyNoiseProfileTest(unittest.TestCase):
	def test_empty_profile(self):
		indicator, text = classify_noise_profile(summarize_noise_profile([]))
		self.assertFalse(indicator)
		self.assertIn("Kein Rauschprofil", text)

	def test_inconsistent_noise_is_indicator(self):
		# Ein Ausreißer-Frame erzeugt einen hohen Variationskoeffizienten.
		m = summarize_noise_profile([1.0, 1.0, 1.0, 1.0, 10.0])
		indicator, text = classify_noise_profile(m)
		self.assertTrue(indicator)
		self.assertIn("variierend", text)

	def test_very_low_noise_is_indicator(self):
		m = summarize_noise_profile([0.1] * 5)
		indicator, text = classify_noise_profile(m)
		self.assertTrue(indicator)
		self.assertIn("niedrig", text)

	def test_very_high_noise_is_technical_note(self):
		m = summarize_noise_profile([8.0] * 5)
		indicator, text = classify_noise_profile(m)
		self.assertFalse(indicator)
		self.assertIn("hohes Rauschniveau", text)

	def test_uniform_normal_profile(self):
		m = summarize_noise_profile([2.0] * 8)
		indicator, text = classify_noise_profile(m)
		self.assertFalse(indicator)
		self.assertIn("unauffällig", text)

	def test_no_manipulation_claim(self):
		"""Ergebnistexte enthalten keine Echtheits-Aussage (Abschnitt 13)."""
		for values in ([2.0] * 8, [0.1] * 5, [1.0, 1.0, 1.0, 9.0]):
			_, text = classify_noise_profile(summarize_noise_profile(values))
			self.assertNotIn("gefälscht", text.lower())
			self.assertNotIn("manipuliert ist", text.lower())


class NoiseEstimatorWorkerTest(unittest.TestCase):
	"""End-to-End-Test des Workers auf einem erzeugten Testvideo."""

	@staticmethod
	def _write_test_video(path, num_frames=50, noise_sigma=12.0):
		import cv2
		writer = cv2.VideoWriter(
			path, cv2.VideoWriter_fourcc(*"MJPG"), 25.0, (160, 120))
		if not writer.isOpened():
			return False
		rng = np.random.default_rng(7)
		base = _gradient_image(120, 160)
		for i in range(num_frames):
			noisy = base + rng.normal(0.0, noise_sigma, base.shape).astype(np.float32)
			frame = np.clip(noisy, 0, 255).astype(np.uint8)
			writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
		writer.release()
		return True

	def test_worker_produces_profile(self):
		tmpdir = tempfile.mkdtemp(prefix="noise_worker_test_")
		video_path = os.path.join(tmpdir, "noise_test.avi")
		if not self._write_test_video(video_path):
			self.skipTest("cv2.VideoWriter nicht verfügbar")

		results = []
		errors = []
		worker = NoiseEstimatorWorker(video_path, num_frames=8)
		worker.signals.result.connect(
			lambda mode, text, data: results.append((mode, text, data)))
		worker.signals.error.connect(
			lambda mode, msg: errors.append((mode, msg)))
		worker.run()  # synchron ausführen, Signale sind Direct-Connections

		self.assertEqual(errors, [], msg=f"Worker-Fehler: {errors}")
		self.assertEqual(len(results), 1)
		mode, text, data = results[0]
		self.assertEqual(mode, "noise")
		self.assertIn("Rauschprofil-Analyse", text)
		self.assertIn("Indikator", text)

		metrics = data["metrics"]
		self.assertGreater(metrics["count"], 0)
		self.assertLessEqual(metrics["count"], 8)
		self.assertEqual(len(data["sigmas"]), metrics["count"])
		self.assertEqual(len(data["frame_indices"]), metrics["count"])
		# MJPG-Kompression dämpft das Rauschen, aber es bleibt messbar.
		self.assertGreater(metrics["sigma_median"], 0.5)
		# Frames werden gleichmäßig über die Laufzeit verteilt angesteuert.
		self.assertEqual(metrics["sampling"], "evenly")

	def test_missing_file_reports_error(self):
		errors = []
		worker = NoiseEstimatorWorker(
			os.path.join(tempfile.gettempdir(), "does_not_exist_12345.mp4"))
		worker.signals.error.connect(lambda mode, msg: errors.append((mode, msg)))
		worker.run()
		self.assertEqual(len(errors), 1)
		mode, msg = errors[0]
		self.assertEqual(mode, "noise")
		self.assertIn("noise", msg)


if __name__ == "__main__":
	unittest.main()
