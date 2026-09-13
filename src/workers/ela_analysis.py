import os
import traceback
from pathlib import Path
import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject


class ElaWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)
	error = pyqtSignal(str, str)


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

			stem = Path(self.filepath).stem
			src = ImageOps.exif_transpose(Image.open(self.filepath)).convert("RGB")

			temp_jpeg = self.exports_dir / f"{stem}_ela_temp.jpg"
			src.save(str(temp_jpeg), "JPEG", quality=self.quality)

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

			if temp_jpeg.exists():
				temp_jpeg.unlink()

			text = (
				f"ELA-Analyse: {Path(self.filepath).name}\n"
				f"{'-' * 50}\n"
				f"Qualität: {self.quality}%\n"
				f"Max-Fehler: {max_err}\n"
				f"Mittlerer Fehler: {mean_err:.2f}\n"
				f"Std-Abweichung: {std_err:.2f}\n"
				f"Veränderte Pixel: {altered} / {total_pixels} ({pct_altered:.1f}%)\n"
			)

			data = {
				"diff": diff,
				"stats": {
					"quality": self.quality,
					"max_err": max_err,
					"mean_err": mean_err,
					"std_err": std_err,
					"altered": altered,
					"total_pixels": total_pixels,
					"pct_altered": pct_altered,
				},
			}
			self.signals.result.emit("ela", text, data)

		except Exception as e:
			self.signals.error.emit("ela", str(e))