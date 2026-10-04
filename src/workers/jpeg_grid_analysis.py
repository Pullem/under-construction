import traceback
import logging
from pathlib import Path
import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import AppError, ErrorCode, analysis_error


logger = logging.getLogger(__name__)


class JpegGridWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)
	error = pyqtSignal(str, str)


class JpegGridWorker(QRunnable):
	"""JPEG-Grid-Analyse: erkennt das 8×8-DCT-Blockraster der JPEG-Kompression
	und prüft die bildweite Raster-Ausrichtung. Regionen mit abweichendem
	Raster-Offset deuten auf Neu-Kompression, Crop/Splicing oder Compositing hin."""

	BLOCK = 8
	MIN_DIM = 16
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

			block_vmax = max(1e-6, float(np.percentile(block, 98))) \
				if block is not None and block.size else 0.0

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
			err = analysis_error("JPEG Grid analysis failed", mode="jpeggrid", filepath=self.filepath, exc=e)
			self.signals.error.emit("jpeggrid", err.to_json())
			logger.exception("JPEG Grid analysis failed")