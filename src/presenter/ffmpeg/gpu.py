"""GPU / Hardware-Beschleunigung für FFmpeg-Operationen."""

from ...utils.gpu_config import get_gpu_config, check_cuda_available


class GPUConfigMixin:
	"""Stellt GPU-Konfiguration und HWAccel-Argumente bereit."""

	def _init_gpu(self):
		try:
			self._gpu_config = get_gpu_config()
			self._cuda_available, _ = check_cuda_available()
		except Exception as e:
			self._ffmpeg_log(f"GPU config init failed: {e}")
			self._gpu_config = None
			self._cuda_available = False

	def _get_hwaccel_args(self, for_decode: bool = True) -> list[str]:
		if not self._cuda_available or not self._gpu_config or not self._gpu_config.enabled:
			return []
		if for_decode:
			hwaccel = self._gpu_config.decode_hwaccel
			if hwaccel in ("nvdec", "cuda"):
				return ["-hwaccel", hwaccel, "-hwaccel_device", str(self._gpu_config.device_index)]
		return []

	def _get_encode_args(self, codec_fmt: str) -> tuple[str, list[str]]:
		codec_map = {
			"ffv1": ("mkv", ["-c:v", "ffv1", "-pix_fmt", "yuv420p"]),
			"h264_crf18": ("mp4", ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p"]),
			"h264_crf10": ("mp4", ["-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p"]),
		}
		ext, codec_args = codec_map.get(codec_fmt, ("mkv", ["-c:v", "ffv1"]))
		return ext, codec_args