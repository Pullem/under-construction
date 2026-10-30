"""Analyse-Callbacks: Worker-Ergebnisse entgegennehmen und anzeigen."""

import json
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication

from ...worker import (FfprobeWorker, VSMetadataWorker, ElaWorker, CopyMoveWorker,
					  ResamplingWorker, JpegGridWorker, NoiseEstimatorWorker,
					  SharpnessDetectorWorker, MotionAnalyzerWorker, VideoStabilizerWorker)


class CallbacksMixin:
	"""Behandelt Ergebnisse/Fehler aller Analyse-Worker."""

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._last_probe_path = None
		self._last_probe_prefix = "video"
		self._copymove_running = False

	def handle_ffprobe_analyse(self, filepath, mode, prefix="video"):
		self._last_probe_path = filepath
		self._last_probe_prefix = prefix

		if mode == "ela":
			self._ffmpeg_log_probe(f"Starte {mode} (async)...")
			exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
			exports_dir.mkdir(parents=True, exist_ok=True)
			worker = ElaWorker(filepath, str(exports_dir))
			worker.signals.result.connect(self._on_ela_result)
			worker.signals.error.connect(self._on_ela_error)
			self.threadpool.start(worker)
			return

		if mode == "copymove":
			self._start_copymove(filepath, prefix)
			return

		if mode == "resample":
			self._ffmpeg_log_probe("Starte resample (async)...")
			exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
			exports_dir.mkdir(parents=True, exist_ok=True)
			worker = ResamplingWorker(filepath, str(exports_dir))
			worker.signals.result.connect(self._on_analysis_result)
			worker.signals.error.connect(self._on_analysis_error)
			self.threadpool.start(worker)
			return

		if mode == "jpeggrid":
			self._ffmpeg_log_probe("Starte jpeggrid (async)...")
			exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
			exports_dir.mkdir(parents=True, exist_ok=True)
			worker = JpegGridWorker(filepath, str(exports_dir))
			worker.signals.result.connect(self._on_analysis_result)
			worker.signals.error.connect(self._on_analysis_error)
			self.threadpool.start(worker)
			return

		if mode == "noise":
			self._ffmpeg_log_probe("Starte noise (async)...")
			worker = NoiseEstimatorWorker(filepath)
			worker.signals.result.connect(self._on_analysis_result)
			worker.signals.error.connect(self._on_analysis_error)
			self.threadpool.start(worker)
			return

		if mode == "sharpness":
			self._ffmpeg_log_probe("Starte sharpness (async)...")
			worker = SharpnessDetectorWorker(filepath)
			worker.signals.result.connect(self._on_analysis_result)
			worker.signals.error.connect(self._on_analysis_error)
			self.threadpool.start(worker)
			return

		if mode == "motion":
			self._ffmpeg_log_probe("Starte motion (async)...")
			worker = MotionAnalyzerWorker(filepath)
			worker.signals.result.connect(self._on_analysis_result)
			worker.signals.error.connect(self._on_analysis_error)
			self.threadpool.start(worker)
			return

		if mode == "stabilizer":
			self._ffmpeg_log_probe("Starte stabilizer (async)...")
			worker = VideoStabilizerWorker(filepath)
			worker.signals.result.connect(self._on_analysis_result)
			worker.signals.error.connect(self._on_analysis_error)
			self.threadpool.start(worker)
			return

		if mode in ("streams", "quickcheck", "format"):
			self._ffmpeg_log_probe(f"Starte {mode} via VapourSynth (async)...")
			vs_plugin_path = os.environ.get(
				'VAPOURSYNTH_PLUGIN_PATH',
				str(Path(__file__).parent.parent.parent / "vapoursynth_plugins" / "bestsource.dll")
			)
			worker = VSMetadataWorker(filepath, mode, vs_plugin_path)
			worker.signals.result.connect(self._on_vsmetadata_result)
			worker.signals.error.connect(self._on_vsmetadata_error)
			self.threadpool.start(worker)
			return

		cmd = self._build_ffprobe_cmd(filepath, mode)
		if not cmd:
			self._ffmpeg_log_probe(f"Unbekannter Modus: {mode}")
			return
		self._ffmpeg_log_probe(f"Starte {mode} (async)...")
		worker = FfprobeWorker(filepath, mode, cmd)
		worker.signals.result.connect(self._on_ffprobe_result)
		worker.signals.error.connect(self._on_ffprobe_error)
		self.threadpool.start(worker)

	def _start_copymove(self, filepath, prefix):
		if self._copymove_running:
			self._ffmpeg_log_probe("Copy-Move läuft bereits – überspringe.")
			return
		self._ffmpeg_log_probe("Starte copymove (async)...")
		self._copymove_running = True
		exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
		exports_dir.mkdir(parents=True, exist_ok=True)
		combo = getattr(self.view, f"{prefix}_sensitivity", None)
		sensitivity = "standard"
		if combo is not None:
			sensitivity = combo.currentData() or "standard"
		worker = CopyMoveWorker(filepath, str(exports_dir), sensitivity)
		worker.signals.result.connect(self._on_analysis_result)
		worker.signals.error.connect(self._on_analysis_error)
		self.threadpool.start(worker)

	def handle_sensitivity_changed(self, filepath, prefix):
		result_widget = getattr(self.view, f'{prefix}_result', None)
		if result_widget:
			result_widget.clear()
		self._start_copymove(filepath, prefix)

	# --- Callbacks ---
	def _on_ffprobe_result(self, mode, stdout, stderr):
		path = getattr(self, '_last_probe_path', None) or ""
		if mode == "streams":
			self._run_ffprobe_streams(path, stdout)
		elif mode == "pts_dts":
			self._run_ffprobe_pts_dts(path, stdout)
		elif mode == "frame_dist":
			self._run_ffprobe_frame_dist(path, stdout)
		elif mode == "freeze":
			self._run_ffmpeg_freezedetect(path, stderr)
		elif mode == "blackdetect":
			self._run_ffmpeg_blackdetect(path, stderr)
		elif mode == "scenedetect":
			self._run_ffmpeg_scenedetect(path, stderr)
		elif mode == "silencedetect":
			self._run_ffmpeg_silencedetect(path, stderr)
		elif mode == "bitrate":
			self._run_ffprobe_bitrate(path, stdout)
		elif mode == "quickcheck":
			self._run_ffprobe_quickcheck(path, stdout)

	def _on_ffprobe_error(self, mode, error_msg):
		self._ffmpeg_log_probe(f"Fehler bei {mode}: {error_msg}")

	def _on_vsmetadata_result(self, filepath, mode, metadata):
		self._ffmpeg_log_probe(f"VapourSynth {mode} abgeschlossen.")
		p = getattr(self, '_last_probe_prefix', 'video')

		if mode in ("streams", "quickcheck", "format"):
			text_result = json.dumps(metadata, indent=2, ensure_ascii=False)
			result_widget = getattr(self.view, f'{p}_result', None)
			if result_widget:
				result_widget.setPlainText(text_result)
			self._switch_to_tab(p, mode)
			self.view.show_analysis_result(p, mode, {"metadata": metadata})

	def _on_vsmetadata_error(self, filepath, error_msg):
		self._ffmpeg_log_probe(f"VapourSynth Fehler: {error_msg}")

	def _on_ela_result(self, mode, text_result, data):
		self._ffmpeg_log_probe("ELA-Analyse abgeschlossen.")
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(text_result)
		self._switch_to_tab(p, mode)
		self.view.show_analysis_result(p, mode, data)
		self._export_analysis_figures(p, mode)

	def _on_analysis_result(self, mode, text_result, data):
		self._copymove_running = False
		self._ffmpeg_log_probe(f"{mode}-Analyse abgeschlossen.")
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(text_result)
		self._switch_to_tab(p, mode)
		self.view.show_analysis_result(p, mode, data)
		self._export_analysis_figures(p, mode)

	def _export_analysis_figures(self, prefix, mode):
		filepath = getattr(self, '_last_probe_path', None)
		if not filepath:
			return
		exports_dir = Path(self.model.current_case_path) / "exports" \
			if self.model.current_case_path else Path()
		exports_dir.mkdir(parents=True, exist_ok=True)
		stem = Path(filepath).stem
		QApplication.processEvents()
		self.view.export_analysis_figures(prefix, mode, stem, str(exports_dir))

	def _switch_to_tab(self, prefix, mode):
		tabs = getattr(self.view, f"{prefix}_result_tabs", None)
		if tabs is None:
			return
		tab_modes = ["ela", "copymove", "resample", "jpeggrid"]
		if mode in tab_modes:
			tabs.setCurrentIndex(tab_modes.index(mode))

	def _on_ela_error(self, mode, error_msg):
		self._ffmpeg_log_probe(f"ELA-Fehler: {error_msg}")
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(f"ELA-Fehler: {error_msg}")

	def _on_analysis_error(self, mode, error_msg):
		self._copymove_running = False
		self._ffmpeg_log_probe(f"{mode}-Fehler: {error_msg}")
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(f"{mode}-Fehler: {error_msg}")

	# --- Logging Helpers ---
	def _write_probe_result(self, lines):
		text = "\n".join(lines) if isinstance(lines, list) else lines
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(text)

	def _ffmpeg_log_probe(self, msg):
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.appendPlainText(msg)