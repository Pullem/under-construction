import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import QProcess, QByteArray

from ..model.base import BASE_DIR
from ..worker import AnalysisWorker


class FfmpegOpsMixin:
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._ffmpeg_proc = None

	def handle_ffmpeg_run(self, input_path, args_str, codec_fmt):
		if self._ffmpeg_proc:
			return

		parts = args_str.split("|", 2)
		start_ts = parts[0] if len(parts) > 0 else "00:00:00"
		end_ts = parts[1] if len(parts) > 1 else ""
		filter_str = parts[2] if len(parts) > 2 else ""

		src = Path(input_path)
		if not src.exists():
			self._ffmpeg_log(f"Datei nicht gefunden: {input_path}")
			return

		# Ausgabepfad
		exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
		exports_dir.mkdir(parents=True, exist_ok=True)

		stem = src.stem
		codec_map = {
			"ffv1": ("mkv", ["-c:v", "ffv1", "-pix_fmt", "yuv420p"]),
			"h264_crf18": ("mp4", ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p"]),
			"h264_crf10": ("mp4", ["-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p"]),
		}
		ext, codec_args = codec_map.get(codec_fmt, ("mkv", ["-c:v", "ffv1"]))

		op_name = "trim" if end_ts else "proc"
		out_filename = f"{stem}_{op_name}.{ext}"
		out_path = exports_dir / out_filename
		out_idx = 1
		while out_path.exists():
			out_filename = f"{stem}_{op_name}_{out_idx}.{ext}"
			out_path = exports_dir / out_filename
			out_idx += 1

		cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y"]

		if start_ts != "00:00:00":
			cmd += ["-ss", start_ts]
		cmd += ["-i", str(src)]
		if end_ts:
			cmd += ["-to", end_ts]
		timecode_mode = (filter_str == "__TIMECODE__")
		if filter_str and filter_str not in ("-f framehash -",) and not timecode_mode:
			cmd += ["-vf", filter_str]
		if filter_str == "-f framehash -":
			cmd += ["-f", "framehash", "-"]
			out_path = None
		elif timecode_mode:
			cmd += codec_args
			cmd += ["-timecode", start_ts + ":00"]
			cmd.append(str(out_path))
		else:
			cmd += codec_args
			cmd.append(str(out_path))

		self._ffmpeg_log(f"Starte: {' '.join(cmd)}")
		if hasattr(self.view, 'ffmpeg_progress'):
			self.view.ffmpeg_progress.setValue(0)
		if hasattr(self.view, 'ffmpeg_btn_run'):
			self.view.ffmpeg_btn_run.setEnabled(False)
		if hasattr(self.view, 'ffmpeg_btn_abort'):
			self.view.ffmpeg_btn_abort.setEnabled(True)

		self._ffmpeg_proc = QProcess()
		self._ffmpeg_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

		# Fontconfig für Windows einrichten (drawtext braucht es)
		env = self._ffmpeg_proc.processEnvironment()
		fc_path = self._setup_fontconfig()
		if fc_path:
			env.insert("FONTCONFIG_PATH", fc_path)
			self._ffmpeg_proc.setProcessEnvironment(env)

		timecode_pattern = None
		if filter_str == "-f framehash -":
			pass  # kein Fortschritt möglich
		else:
			# Dauer für Progress ermitteln
			dur = self._get_duration(str(src))
			if dur > 0:
				timecode_pattern = dur

		self._ffmpeg_proc.readyReadStandardOutput.connect(
			lambda: self._on_ffmpeg_output(timecode_pattern)
		)
		self._ffmpeg_proc.finished.connect(
			lambda exit_code, status: self._on_ffmpeg_finished(exit_code, status, out_path)
		)

		self._ffmpeg_timecode = timecode_pattern
		self._ffmpeg_proc.start(cmd[0], cmd[1:])

	def _on_ffmpeg_output(self, duration):
		if not self._ffmpeg_proc:
			return
		data = self._ffmpeg_proc.readAllStandardOutput().data().decode("utf-8", errors="replace")
		self._ffmpeg_log(data.rstrip())
		update_progress(data, duration, self.view)

	def _on_ffmpeg_finished(self, exit_code, status, out_path):
		self._ffmpeg_proc = None
		if hasattr(self.view, 'ffmpeg_progress'):
			self.view.ffmpeg_progress.setValue(100 if exit_code == 0 else 0)
		if hasattr(self.view, 'ffmpeg_btn_run'):
			self.view.ffmpeg_btn_run.setEnabled(True)
		if hasattr(self.view, 'ffmpeg_btn_abort'):
			self.view.ffmpeg_btn_abort.setEnabled(False)

		if exit_code == 0 and out_path and out_path.exists():
			self._ffmpeg_log(f"Fertig: {out_path}")
			# In DB registrieren
			try:
				info = self._scan_output(out_path)
				if info:
					self.model.save_to_db(
						str(out_path), out_path.name,
						info["hash"], info["metadata"], info["exif"]
					)
					self._ffmpeg_log(f"✓ In Datenbank registriert: {out_path.name}")
					self.refresh_ui_list()
			except Exception as e:
				self._ffmpeg_log(f"Fehler bei DB-Registrierung: {e}")
		elif exit_code != 0:
			self._ffmpeg_log(f"ffmpeg beendet mit Fehler (Code {exit_code})")

	def handle_ffmpeg_abort(self):
		if self._ffmpeg_proc and self._ffmpeg_proc.state() == QProcess.ProcessState.Running:
			self._ffmpeg_proc.kill()
			self._ffmpeg_proc = None
			self._ffmpeg_log("Abgebrochen.")
			if hasattr(self.view, 'ffmpeg_btn_run'):
				self.view.ffmpeg_btn_run.setEnabled(True)
			if hasattr(self.view, 'ffmpeg_btn_abort'):
				self.view.ffmpeg_btn_abort.setEnabled(False)

	def _ffmpeg_log(self, msg):
		if hasattr(self.view, 'ffmpeg_log'):
			self.view.ffmpeg_log.appendPlainText(msg)

	def _setup_fontconfig(self):
		try:
			fc_dir = Path(str(BASE_DIR)) / ".fontconfig"
			fc_dir.mkdir(parents=True, exist_ok=True)
			conf = fc_dir / "fonts.conf"
			if not conf.exists():
				conf.write_text(
					'<?xml version="1.0"?>\n'
					'<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
					'<fontconfig>\n'
					'  <dir>C:/Windows/Fonts</dir>\n'
					'</fontconfig>\n',
					encoding="utf-8"
				)
			return str(fc_dir)
		except Exception as e:
			self._ffmpeg_log(f"Fontconfig-Setup fehlgeschlagen: {e}")
			return None

	def _get_duration(self, filepath):
		try:
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-show_entries", "format=duration",
				 "-of", "csv=p=0", filepath],
				capture_output=True, text=True, timeout=15
			)
			return float(r.stdout.strip())
		except Exception:
			return 0

	def _scan_output(self, out_path):
		try:
			hash_val = self.model.calculate_hash(str(out_path))
			mi_data = {}
			exif_data = {}
			try:
				from pymediainfo import MediaInfo
				mi = MediaInfo.parse(str(out_path))
				mi_data = {t.track_type: t.to_data() for t in mi.tracks}
			except Exception:
				pass
			try:
				import exiftool
				exif_path = str(BASE_DIR / "exiftool.exe")
				if not os.path.exists(exif_path):
					exif_path = str(BASE_DIR / "exiftool_files" / "exiftool.pl")
				with exiftool.ExifToolHelper(executable=exif_path) as et:
					meta = et.get_metadata(str(out_path))
					if meta:
						exif_data = meta[0]
			except Exception:
				pass
			return {"hash": hash_val, "metadata": mi_data, "exif": exif_data}
		except Exception as e:
			self._ffmpeg_log(f"Scan fehlgeschlagen: {e}")
			return None


def update_progress(data, duration, view):
	import re
	if not duration or not hasattr(view, 'ffmpeg_progress'):
		return
	m = re.search(r"time=(\d+):(\d+):(\d+)\.(\d+)", data)
	if m:
		h, mi, s, _ = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
		current = h * 3600 + mi * 60 + s
		pct = min(99, int(current / duration * 100))
		view.ffmpeg_progress.setValue(pct)
