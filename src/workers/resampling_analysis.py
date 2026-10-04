import traceback
import logging
from pathlib import Path
import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import AppError, ErrorCode, analysis_error


logger = logging.getLogger(__name__)


class ResamplingWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)
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

			blur = cv2.GaussianBlur(gray, (0, 0), 1.5)
			high = gray - blur
			med = float(np.median(high))
			sigma_noise = float(1.4826 * np.median(np.abs(high - med)))
			signal_power = float(np.mean((gray - float(gray.mean())) ** 2))
			snr_db = float(10.0 * np.log10(max(signal_power, 1e-12) / max(sigma_noise ** 2, 1e-12)))

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

			resample_suspect = (spectral_peakiness > 2.5) or (profile_periodicity > 10.0)
			resample_verdict = (
				"⚠️  Verdacht auf Resampling (Skalierung/Rotation)" if resample_suspect
				else "Keine auffälligen Resampling-Artefakte")
			noise_suspect = cv_coeff > self.CV_THRESHOLD
			noise_verdict = (
				"⚠️  Inkonsistentes Rauschniveau – Hinweis auf Compositing/Splicing "
				"oder stark variierende Bildbereiche"
				if noise_suspect else "Gleichmäßiges Rauschniveau")

			v_lim = max(1e-6, 3.0 * sigma_noise)
			noise_vmax = max(1e-6, float(np.nanpercentile(noise_map, 95)))

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
			err = analysis_error("Resampling analysis failed", mode="resample", filepath=self.filepath, exc=e)
			self.signals.error.emit("resample", err.to_json())
			logger.exception("Resampling analysis failed")