"""FFmpeg-Operationen: Komposition aus GPU, Runner, Analyzer, Callbacks."""

from .gpu import GPUConfigMixin
from .runner import FFmpegRunnerMixin
from .analyzer import AnalyzerMixin
from .callbacks import CallbacksMixin


class FfmpegOpsMixin(GPUConfigMixin, FFmpegRunnerMixin, AnalyzerMixin, CallbacksMixin):
	"""
	Komplette FFmpeg-Operations-Mixin für den Presenter.

	Zusammengesetzt aus:
	- GPUConfigMixin: Hardware-Beschleunigung & Encoding-Args
	- FFmpegRunnerMixin: Prozess-Start, Progress, Abort, Post-Process
	- AnalyzerMixin: ffprobe/ffmpeg-Analysen (Quick-Check, Streams, PTS/DTS, etc.)
	- CallbacksMixin: Worker-Ergebnisse/Fehler verarbeiten & anzeigen
	"""

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		# Attribute werden in den einzelnen Mixins initialisiert