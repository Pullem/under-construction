import os
import traceback
import logging
from pathlib import Path
import numpy as np
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

from src.utils.errors import AppError, ErrorCode, analysis_error
from src.utils.gpu_config import get_gpu_config, check_cuda_available


logger = logging.getLogger(__name__)


SENSITIVITY_PRESETS = {
	"standard": {
		"contrast_threshold": 0.04,
		"ratio": 0.75,
		"spatial_dist": 30,
		"ransac_thresh": 5.0,
		"verdict_threshold": 15,
	},
	"empfindlich": {
		"contrast_threshold": 0.02,
		"ratio": 0.80,
		"spatial_dist": 20,
		"ransac_thresh": 5.0,
		"verdict_threshold": 12,
	},
	"sehr_empfindlich": {
		"contrast_threshold": 0.01,
		"ratio": 0.85,
		"spatial_dist": 15,
		"ransac_thresh": 8.0,
		"verdict_threshold": 8,
	},
}


class CopyMoveWorkerSignals(QObject):
	result = pyqtSignal(str, str, object)
	error = pyqtSignal(str, str)


class CopyMoveWorker(QRunnable):
	"""Keypoint-basierte Copy-Move-Forgery-Erkennung mittels SIFT + FLANN + RANSAC."""

	def __init__(self, filepath, exports_dir, sensitivity="standard"):
		super().__init__()
		self.filepath = filepath
		self.exports_dir = Path(exports_dir)
		self.sensitivity = sensitivity
		self.params = SENSITIVITY_PRESETS.get(sensitivity, SENSITIVITY_PRESETS["standard"])
		self.signals = CopyMoveWorkerSignals()
		self._gpu_config = None
		self._cuda_available = False
		self._init_gpu()

	def _init_gpu(self):
		try:
			self._gpu_config = get_gpu_config()
			self._cuda_available, _ = check_cuda_available()
		except Exception:
			self._cuda_available = False
			self._gpu_config = None

	def _get_sift(self, contrast_threshold):
		"""Get SIFT detector, using CUDA if available."""
		if self._cuda_available and self._gpu_config and self._gpu_config.enabled:
			try:
				if hasattr(cv2, 'cuda') and cv2.cuda.getCudaEnabledDeviceCount() > 0:
					return cv2.cuda_SIFT_create(contrastThreshold=contrast_threshold)
			except Exception:
				pass
		return cv2.SIFT_create(contrastThreshold=contrast_threshold)

	def run(self):
		try:
			from PIL import Image, ImageOps
			import cv2

			stem = Path(self.filepath).stem
			src = ImageOps.exif_transpose(Image.open(self.filepath)).convert("RGB")
			gray = cv2.cvtColor(np.array(src), cv2.COLOR_RGB2GRAY)

			sift = self._get_sift(self.params["contrast_threshold"])
			
			# Use CUDA GpuMat if CUDA SIFT is available
			use_cuda = (self._cuda_available and self._gpu_config and self._gpu_config.enabled 
					   and hasattr(sift, 'detectAndComputeAsync'))
			if use_cuda:
				gpu_gray = cv2.cuda_GpuMat()
				gpu_gray.upload(gray)
				kp_gpu, desc_gpu = sift.detectAndComputeAsync(gpu_gray, None)
				kp = sift.convert(kp_gpu)
				desc = desc_gpu.download() if desc_gpu is not None else None
			else:
				kp, desc = sift.detectAndCompute(gray, None)

			if desc is None or len(kp) < 8:
				text = (
					f"Copy-Move-Analyse: {Path(self.filepath).name}\n"
					f"{'-' * 50}\n"
					f"Zu wenig Features ({len(kp) if kp is not None else 0} gefunden, min 8)."
				)
				self.signals.result.emit("copymove", text, {"vis": None})
				return

			FLANN_INDEX_KDTREE = 1
			flann = cv2.FlannBasedMatcher(
				{"algorithm": FLANN_INDEX_KDTREE, "trees": 5},
				{"checks": 50}
			)
			matches = flann.knnMatch(desc, desc, k=3)

			good = []
			for pair in matches:
				if len(pair) < 3:
					continue
				m, n = pair[1], pair[2]
				if m.queryIdx == m.trainIdx:
					continue
				if m.distance < self.params["ratio"] * n.distance:
					pt1 = np.array(kp[m.queryIdx].pt)
					pt2 = np.array(kp[m.trainIdx].pt)
					if np.linalg.norm(pt1 - pt2) > self.params["spatial_dist"]:
						good.append(m)

			pairs = []
			if len(good) >= 4:
				src_pts = np.float32([kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
				dst_pts = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
				_, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, self.params["ransac_thresh"])
				if mask is not None:
					for i, m in enumerate(good):
						if mask[i]:
							pairs.append((kp[m.queryIdx], kp[m.trainIdx]))

			if not pairs:
				self.signals.result.emit(
					"copymove",
					f"Copy-Move-Analyse: {Path(self.filepath).name}\n"
					f"{'-' * 50}\n"
					f"Empfindlichkeit: {self.sensitivity} "
					f"(ratio={self.params['ratio']}, dist={self.params['spatial_dist']})\n"
					f"SIFT-Features: {len(kp)}\n"
					f"Matched (Ratio-Test): {len(good)}\n"
					f"RANSAC-Inlier: 0\n"
					f"Ergebnis: Keine konsistente Transformationsgruppe (RANSAC) gefunden\n"
					f"\u2192 vermutlich keine Copy-Move-Manipulation oder zu glatte/komprimierte Region.",
					{"vis": None},
				)
				return

			vis = np.array(src)
			for qk, tk in pairs:
				cv2.line(vis,
					(int(qk.pt[0]), int(qk.pt[1])),
					(int(tk.pt[0]), int(tk.pt[1])),
					(0, 255, 0), 1)
				cv2.circle(vis, (int(qk.pt[0]), int(qk.pt[1])), 4, (255, 0, 0), -1)
				cv2.circle(vis, (int(tk.pt[0]), int(tk.pt[1])), 4, (0, 0, 255), -1)

			shifts = np.array(
				[[tk.pt[0] - qk.pt[0], tk.pt[1] - qk.pt[1]] for qk, tk in pairs],
				dtype=np.float32)

			verdict = "\u26a0\ufe0f  Copy-Move verd\u00e4chtig" if len(pairs) > self.params["verdict_threshold"] else "Keine offensichtliche Copy-Move erkannt"
			text = (
				f"Copy-Move-Analyse: {Path(self.filepath).name}\n"
				f"{'-' * 50}\n"
				f"Empfindlichkeit: {self.sensitivity} "
				f"(ratio={self.params['ratio']}, dist={self.params['spatial_dist']})\n"
				f"SIFT-Features: {len(kp)}\n"
				f"Matched (Ratio-Test): {len(good)}\n"
				f"RANSAC-Inlier: {len(pairs)}\n"
				f"Ergebnis: {verdict}\n"
			)
			self.signals.result.emit("copymove", text, {"vis": vis, "shifts": shifts})

		except Exception as e:
			err = analysis_error("Copy-Move analysis failed", mode="copymove", filepath=self.filepath, exc=e)
			self.signals.error.emit("copymove", err.to_json())
			logger.exception("Copy-Move analysis failed")