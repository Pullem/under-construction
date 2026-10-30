"""FFmpeg-Prozess-Verwaltung: Start, Progress, Abort, Post-Process."""

import os
from pathlib import Path
from PyQt6.QtCore import QProcess, QThreadPool

from ...model.base import BASE_DIR
from ...model.media import DuplicateMediaError
from ...worker import PostProcessWorker
from .utils import setup_fontconfig, get_duration


class FFmpegRunnerMixin:
	"""Startet und überwacht FFmpeg-Prozesse (Trim, Export, etc.)."""

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._ffmpeg_proc = None
		self._ffmpeg_prefix = "video"
		self._ffmpeg_timecode = None

	def _ffmpeg_log(self, msg):
		p = getattr(self, '_ffmpeg_prefix', 'video')
		log_widget = getattr(self.view, f'{p}_log', None)
		if log_widget:
			log_widget.appendPlainText(msg)

	def handle_ffmpeg_run(self, input_path, args_str, codec_fmt, prefix="video"):
		if self._ffmpeg_proc:
			return
		self._ffmpeg_prefix = prefix

		parts = args_str.split("|", 2)
		start_ts = parts[0] if len(parts) > 0 else "00:00:00"
		end_ts = parts[1] if len(parts) > 1 else ""
		filter_str = parts[2] if len(parts) > 2 else ""

		src = Path(input_path)
		if not src.exists():
			self._ffmpeg_log(f"Datei nicht gefunden: {input_path}")
			return

		exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
		exports_dir.mkdir(parents=True, exist_ok=True)

		stem = src.stem
		ext, codec_args = self._get_encode_args(codec_fmt)

		if filter_str == "__BITSTREAM__":
			op_name = "bitstream"
		elif filter_str == "-f framehash -":
			op_name = "hash"
		elif "drawtext" in filter_str and "timecode" in filter_str:
			op_name = "tc"
		elif filter_str.startswith("fps="):
			op_name = "frames"
		elif end_ts:
			op_name = "trim"
		else:
			op_name = "proc"
		out_filename = f"{stem}_{op_name}.{ext}"
		out_path = exports_dir / out_filename
		out_idx = 1
		while out_path.exists():
			out_filename = f"{stem}_{op_name}_{out_idx}.{ext}"
			out_path = exports_dir / out_filename
			out_idx += 1

		if "rate=25" in filter_str:
			fps = get_framerate(str(src))
			if fps:
				filter_str = filter_str.replace("rate=25", f"rate={fps}")

		bitstream_mode = (filter_str == "__BITSTREAM__")
		framehash_mode = (filter_str == "-f framehash -")

		hwaccel_args = self._get_hwaccel_args(for_decode=True)

		if bitstream_mode:
			out_path_capture = None
			cmd = [str(BASE_DIR / "ffmpeg.exe")] + hwaccel_args + ["-i", str(src), "-f", "null", "-"]
		elif framehash_mode:
			out_path_capture = None
			cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y"] + hwaccel_args
			if start_ts != "00:00:00":
				cmd += ["-ss", start_ts]
			cmd += ["-i", str(src)]
			cmd += ["-f", "framehash", "-"]
		else:
			out_path_capture = out_path
			cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y"] + hwaccel_args
			if start_ts != "00:00:00":
				cmd += ["-ss", start_ts]
			cmd += ["-i", str(src)]
			if end_ts:
				cmd += ["-to", end_ts]
			if filter_str:
				cmd += ["-vf", filter_str]
			cmd += codec_args
			cmd.append(str(out_path_capture))

		self._ffmpeg_log(f"Starte: {' '.join(cmd)}")
		v = self.view
		p = self._ffmpeg_prefix
		progress = getattr(v, f'{p}_progress', None)
		if progress:
			progress.setValue(0)
		btn_run = getattr(v, f'{p}_btn_run', None)
		if btn_run:
			btn_run.setEnabled(False)
		btn_abort = getattr(v, f'{p}_btn_abort', None)
		if btn_abort:
			btn_abort.setEnabled(True)

		self._ffmpeg_proc = QProcess()
		self._ffmpeg_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

		if not bitstream_mode and not framehash_mode:
			env = self._ffmpeg_proc.processEnvironment()
			fc_path = setup_fontconfig(self)
			if fc_path:
				env.insert("FONTCONFIG_PATH", fc_path)
				self._ffmpeg_proc.setProcessEnvironment(env)

		timecode_pattern = None
		if filter_str == "-f framehash -":
			pass
		elif not bitstream_mode:
			dur = get_duration(str(src))
			if dur > 0:
				timecode_pattern = dur

		self._ffmpeg_proc.readyReadStandardOutput.connect(
			lambda: self._on_ffmpeg_output(timecode_pattern)
		)
		self._ffmpeg_proc.finished.connect(
			lambda exit_code, status, captured=out_path_capture: self._on_ffmpeg_finished(exit_code, status, captured)
		)

		self._ffmpeg_timecode = timecode_pattern
		self._ffmpeg_proc.start(cmd[0], cmd[1:])

	def _on_ffmpeg_output(self, duration):
		if not self._ffmpeg_proc:
			return
		data = self._ffmpeg_proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
		self._ffmpeg_log(data.rstrip())
		update_progress(data, duration, self.view, getattr(self, '_ffmpeg_prefix', 'video'))

	def _on_ffmpeg_finished(self, exit_code, status, out_path):
		self._ffmpeg_proc = None
		p = getattr(self, '_ffmpeg_prefix', 'video')
		v = self.view
		progress = getattr(v, f'{p}_progress', None)
		if progress:
			progress.setValue(100 if exit_code == 0 else 0)
		btn_run = getattr(v, f'{p}_btn_run', None)
		if btn_run:
			btn_run.setEnabled(True)
		btn_abort = getattr(v, f'{p}_btn_abort', None)
		if btn_abort:
			btn_abort.setEnabled(False)

		if exit_code == 0 and out_path and out_path.exists():
			self._ffmpeg_log(f"Fertig: {out_path}")
			worker = PostProcessWorker(self.model, str(out_path))
			worker.signals.result.connect(self._on_post_process_result)
			worker.signals.error.connect(lambda e: self._ffmpeg_log(f"Post-Process Fehler: {e}"))
			self.threadpool.start(worker)
		elif exit_code != 0:
			self._ffmpeg_log(f"ffmpeg beendet mit Fehler (Code {exit_code})")

	def _on_post_process_result(self, info):
		try:
			self.model.save_to_db(
				info["filepath"], os.path.basename(info["filepath"]),
				info["hash"], info["metadata"], info["exif"]
			)
			self._ffmpeg_log(f"✓ In Datenbank registriert: {os.path.basename(info['filepath'])}")
			self.refresh_ui_list()
		except DuplicateMediaError:
			self._ffmpeg_log(f"– Bereits in Datenbank registriert: {os.path.basename(info['filepath'])}")
		except Exception as e:
			self._ffmpeg_log(f"Fehler bei DB-Registrierung: {e}")

	def handle_ffmpeg_abort(self):
		if self._ffmpeg_proc and self._ffmpeg_proc.state() == QProcess.ProcessState.Running:
			self._ffmpeg_proc.kill()
			self._ffmpeg_proc = None
			self._ffmpeg_log("Abgebrochen.")
			p = getattr(self, '_ffmpeg_prefix', 'video')
			v = self.view
			btn_run = getattr(v, f'{p}_btn_run', None)
			if btn_run:
				btn_run.setEnabled(True)
			btn_abort = getattr(v, f'{p}_btn_abort', None)
			if btn_abort:
				btn_abort.setEnabled(False)

	def handle_lossless_trim(self, input_path, start_frame, end_frame, mode):
		self._ffmpeg_prefix = "video"
		src = Path(input_path)
		if not src.exists():
			self._ffmpeg_log(f"Datei nicht gefunden: {input_path}")
			return
		fps = get_framerate(str(src)) or 25.0
		start_ts = frame_to_timestamp(start_frame, fps)
		end_ts = frame_to_timestamp(end_frame, fps)
		self._ffmpeg_log(f"Lossless Trim: Frame {start_frame}–{end_frame}  ({start_ts} – {end_ts})  Mode: {mode}")

		exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
		exports_dir.mkdir(parents=True, exist_ok=True)
		stem = src.stem
		ext = "mkv"
		codec_args = ["-c:v", "ffv1"]
		if mode == "stream_copy":
			ext = src.suffix[1:] if src.suffix else "mkv"
			codec_args = ["-c:v", "copy"]
		out_filename = f"{stem}_trim_lossless.{ext}"
		out_path = exports_dir / out_filename
		out_idx = 1
		while out_path.exists():
			out_filename = f"{stem}_trim_lossless_{out_idx}.{ext}"
			out_path = exports_dir / out_filename
			out_idx += 1

		hwaccel_args = self._get_hwaccel_args(for_decode=True)
		cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y"] + hwaccel_args + [
			"-ss", start_ts, "-i", str(src),
			"-to", end_ts,
			*codec_args,
			"-avoid_negative_ts", "make_zero",
			str(out_path)]
		self._ffmpeg_log(f"Starte: {' '.join(cmd)}")
		p = self._ffmpeg_prefix
		v = self.view
		progress = getattr(v, f'{p}_progress', None)
		if progress:
			progress.setValue(0)
		btn_run = getattr(v, f'{p}_btn_run', None)
		if btn_run:
			btn_run.setEnabled(False)
		btn_abort = getattr(v, f'{p}_btn_abort', None)
		if btn_abort:
			btn_abort.setEnabled(True)

		self._ffmpeg_proc = QProcess()
		self._ffmpeg_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
		dur = get_duration(str(src))
		self._ffmpeg_proc.readyReadStandardOutput.connect(
			lambda: self._on_ffmpeg_output(dur)
		)
		self._ffmpeg_proc.finished.connect(
			lambda exit_code, status, captured=out_path: self._on_ffmpeg_finished(exit_code, status, captured)
		)
		self._ffmpeg_proc.start(cmd[0], cmd[1:])


def update_progress(data, duration, view, prefix="video"):
	import re
	if not duration:
		return
	progress = getattr(view, f'{prefix}_progress', None)
	if not progress:
		return
	m = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", data)
	if m:
		h, mi, s, _ = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
		current = h * 3600 + mi * 60 + s
		pct = min(99, int(current / duration * 100))
		progress.setValue(pct)