import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

from PyQt6.QtCore import Qt, QProcess, QByteArray, QThreadPool

from ..model.base import BASE_DIR
from ..worker import AnalysisWorker, FfprobeWorker, ElaWorker


class FfmpegOpsMixin:
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._ffmpeg_proc = None

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

		# Framerate für timecode-Preset automatisch ermitteln
		if "rate=25" in filter_str:
			fps = self._get_framerate(str(src))
			if fps:
				filter_str = filter_str.replace("rate=25", f"rate={fps}")

		bitstream_mode = (filter_str == "__BITSTREAM__")
		framehash_mode = (filter_str == "-f framehash -")

		if bitstream_mode:
			out_path_capture = None
			cmd = [str(BASE_DIR / "ffmpeg.exe"), "-i", str(src), "-f", "null", "-"]
		elif framehash_mode:
			out_path_capture = None
			cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y"]
			if start_ts != "00:00:00":
				cmd += ["-ss", start_ts]
			cmd += ["-i", str(src)]
			cmd += ["-f", "framehash", "-"]
		else:
			out_path_capture = out_path
			cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y"]
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
			# Fontconfig für Windows einrichten (drawtext braucht es)
			env = self._ffmpeg_proc.processEnvironment()
			fc_path = self._setup_fontconfig()
			if fc_path:
				env.insert("FONTCONFIG_PATH", fc_path)
				self._ffmpeg_proc.setProcessEnvironment(env)

		timecode_pattern = None
		if filter_str == "-f framehash -":
			pass  # kein Fortschritt möglich
		elif not bitstream_mode:
			# Dauer für Progress ermitteln
			dur = self._get_duration(str(src))
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
		fps = self._get_framerate(str(src)) or 25.0
		start_ts = self._frame_to_timestamp(start_frame, fps)
		end_ts = self._frame_to_timestamp(end_frame, fps)
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

		cmd = [str(BASE_DIR / "ffmpeg.exe"), "-y",
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
		dur = self._get_duration(str(src))
		self._ffmpeg_proc.readyReadStandardOutput.connect(
			lambda: self._on_ffmpeg_output(dur)
		)
		self._ffmpeg_proc.finished.connect(
			lambda exit_code, status, captured=out_path: self._on_ffmpeg_finished(exit_code, status, captured)
		)
		self._ffmpeg_proc.start(cmd[0], cmd[1:])

	@staticmethod
	def _frame_to_timestamp(frame, fps):
		total_s = frame / fps
		h = int(total_s // 3600)
		m = int((total_s % 3600) // 60)
		s = total_s - h * 3600 - m * 60
		return f"{h:02d}:{m:02d}:{s:06.3f}"

	def _get_keyframes(self, filepath):
		"""Returns sorted list of (frame_number, pts_seconds) for keyframes."""
		try:
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-select_streams", "v:0",
				 "-skip_frame", "nokey",
				 "-show_frames",
				 "-show_entries", "frame=coded_picture_number,pkt_pts_time",
				 "-of", "csv=p=0", filepath],
				capture_output=True, text=True, timeout=120
			)
			keyframes = []
			for line in r.stdout.strip().split("\n"):
				line = line.strip()
				if not line or "," not in line:
					continue
				frame_str, pts_str = line.split(",", 1)
				if frame_str and pts_str:
					try:
						keyframes.append((int(float(frame_str)), float(pts_str)))
					except ValueError:
						pass
			keyframes.sort()
			return keyframes
		except Exception as e:
			self._ffmpeg_log(f"Keyframe-Erkennung fehlgeschlagen: {e}")
			return []

	def _ffmpeg_log(self, msg):
		p = getattr(self, '_ffmpeg_prefix', 'video')
		log_widget = getattr(self.view, f'{p}_log', None)
		if log_widget:
			log_widget.appendPlainText(msg)

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

	def _get_framerate(self, filepath):
		try:
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-select_streams", "v:0",
				 "-show_entries", "stream=r_frame_rate",
				 "-of", "csv=p=0", filepath],
				capture_output=True, text=True, timeout=15
			)
			out = r.stdout.strip()
			if out and "/" in out:
				num, den = out.split("/")
				return round(float(num) / float(den))
			elif out:
				return round(float(out))
		except Exception:
			pass
		return None

	def handle_ffprobe_analyse(self, filepath, mode, prefix="video"):
		self._last_probe_path = filepath
		self._last_probe_prefix = prefix

		# ELA nutzt Python (Pillow + NumPy + matplotlib), kein ffprobe/ffmpeg
		if mode == "ela":
			self._ffmpeg_log_probe(f"Starte {mode} (async)...")
			exports_dir = Path(self.model.current_case_path) / "exports" if self.model.current_case_path else Path()
			exports_dir.mkdir(parents=True, exist_ok=True)
			worker = ElaWorker(filepath, str(exports_dir))
			worker.signals.result.connect(self._on_ela_result)
			worker.signals.error.connect(self._on_ela_error)
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

	def _build_ffprobe_cmd(self, filepath, mode):
		if mode == "streams":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-show_streams", "-show_format", "-of", "json", filepath]
		if mode == "pts_dts":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-select_streams", "v:0", "-show_packets", "-of", "json", filepath]
		if mode == "frame_dist":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-select_streams", "v:0", "-show_frames", "-of", "json", filepath]
		if mode == "freeze":
			return [str(BASE_DIR / "ffmpeg.exe"), "-v", "info", "-i", filepath,
					"-vf", "freezedetect", "-f", "null", "-"]
		if mode == "blackdetect":
			return [str(BASE_DIR / "ffmpeg.exe"), "-v", "info", "-i", filepath,
					"-vf", "blackdetect=d=1.0:pic_th=0.98", "-f", "null", "-"]
		if mode == "scenedetect":
			return [str(BASE_DIR / "ffmpeg.exe"), "-v", "info", "-i", filepath,
					"-vf", "scdet", "-f", "null", "-"]
		if mode == "silencedetect":
			return [str(BASE_DIR / "ffmpeg.exe"), "-v", "info", "-i", filepath,
					"-af", "silencedetect=n=-30dB:d=0.5", "-f", "null", "-"]
		if mode == "bitrate":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-select_streams", "v:0", "-show_packets", "-of", "json", filepath]
		if mode == "quickcheck":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-show_streams", "-show_format", "-of", "json", filepath]
		return []

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

	def _on_ela_result(self, mode, text_result, error_map_path, hist_path):
		self._ffmpeg_log_probe("ELA-Analyse abgeschlossen.")
		p = getattr(self, '_last_probe_prefix', 'video')
		# Text-Ergebnis anzeigen
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(text_result)
		# Error-Map auf der rechten Seite anzeigen
		self._set_ela_image(p, f'{p}_error_map_view', error_map_path)
		# Histogram auf der rechten Seite anzeigen
		self._set_ela_image(p, f'{p}_histogram_view', hist_path)

	def _set_ela_image(self, prefix, attr, path):
		label = getattr(self.view, attr, None)
		if label is None or not os.path.exists(path):
			return
		from PyQt6.QtGui import QPixmap
		pixmap = QPixmap(path)
		if not pixmap.isNull():
			label.setPixmap(pixmap.scaled(
				label.width(), label.height(),
				Qt.AspectRatioMode.KeepAspectRatio,
				Qt.TransformationMode.SmoothTransformation))
			label.setVisible(True)

	def _on_ela_error(self, mode, error_msg):
		self._ffmpeg_log_probe(f"ELA-Fehler: {error_msg}")
		p = getattr(self, '_last_probe_prefix', 'video')
		result_widget = getattr(self.view, f'{p}_result', None)
		if result_widget:
			result_widget.setPlainText(f"ELA-Fehler: {error_msg}")

	def _run_ffprobe_quickcheck(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Quick-Check: {filepath}")
		try:
			if raw_output is not None:
				data = json.loads(raw_output)
			else:
				r = subprocess.run(
					[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					 "-show_streams", "-show_format",
					 "-of", "json", filepath],
					capture_output=True, text=True, timeout=30
				)
				data = json.loads(r.stdout)
		except Exception as e:
			self._ffmpeg_log_probe(f"Fehler: {e}")
			return

		streams = data.get("streams", [])
		fmt = data.get("format", {})

		CODEC_WHITELIST = {"h264", "hevc", "mpeg4", "prores", "dnxhd",
						   "ffv1", "vp9", "av1", "mpeg2video", "mjpeg"}
		STANDARD_ARS = {16/9, 4/3, 1.778, 1.333, 1.85, 2.35, 2.39, 1.33, 1.78}
		TOLERANCE = 0.05

		checks = []
		passed = 0
		failed = 0

		# 1. Stream 0 ist Video
		if streams:
			s0 = streams[0]
			if s0.get("codec_type") == "video":
				checks.append(("✓", "Stream 0", "Video-Stream"))
				passed += 1
			else:
				checks.append(("✗", "Stream 0", f"Ist {s0.get('codec_type','?')}, erwartet video"))
				failed += 1
		else:
			checks.append(("✗", "Stream 0", "Keine Streams gefunden"))
			failed += 1

		# 2. Codec-Whitelist
		video_streams = [s for s in streams if s.get("codec_type") == "video"]
		if video_streams:
			codec = video_streams[0].get("codec_name", "")
			if codec in CODEC_WHITELIST:
				checks.append(("✓", "Codec", codec))
				passed += 1
			else:
				checks.append(("✗", "Codec", f"'{codec}' nicht in Whitelist"))
				failed += 1
		else:
			checks.append(("✗", "Codec", "Kein Video-Stream"))
			failed += 1

		# 3. Auflösungs-Validierung
		if video_streams:
			w = video_streams[0].get("width", 0)
			h = video_streams[0].get("height", 0)
			if w > 0 and h > 0:
				ar = w / h
				if w >= 320 and h >= 240:
					ar_ok = any(abs(ar - sar) < TOLERANCE for sar in STANDARD_ARS) if True else False
					check_ar = True
					for sar in STANDARD_ARS:
						if abs(ar - sar) < TOLERANCE:
							check_ar = True
							break
					else:
						check_ar = False
					if check_ar:
						checks.append(("✓", "Auflösung", f"{w}x{h} (AR {ar:.3f})"))
						passed += 1
					else:
						checks.append(("⚠", "Auflösung", f"{w}x{h} (AR {ar:.3f}) ungewöhnlich"))
						failed += 1
				else:
					checks.append(("⚠", "Auflösung", f"{w}x{h} sehr klein"))
					failed += 1
			else:
				checks.append(("✗", "Auflösung", "Keine Maße"))
				failed += 1
		else:
			checks.append(("✗", "Auflösung", "Kein Video-Stream"))
			failed += 1

		# 4. Interlaced
		if video_streams:
			fo = video_streams[0].get("field_order", "progressive")
			if fo in ("progressive", "unknown"):
				status = "progressive" if fo == "progressive" else "unknown (o.k.)"
				checks.append(("✓", "Interlace", status))
				passed += 1
			else:
				checks.append(("⚠", "Interlace", f"Field Order: {fo}"))
				failed += 1
		else:
			checks.append(("✗", "Interlace", "Kein Video-Stream"))
			failed += 1

		# 5. Encoder-ID
		if video_streams:
			tag = video_streams[0].get("codec_tag_string", "")
			if tag:
				checks.append(("✓", "Encoder-Tag", tag))
				passed += 1
			else:
				checks.append(("⚠", "Encoder-Tag", "Kein Tag vorhanden"))
				failed += 1
		else:
			checks.append(("✗", "Encoder-Tag", "Kein Video-Stream"))
			failed += 1

		lines = [
			f"Quick-Check [{filepath}]",
			"-" * 60,
			f"Gesamt: {passed} bestanden, {failed} Probleme",
			("Geprüft: Stream 0, Codec, Auflösung, Interlace, Encoder-Tag"),
			"",
		]
		for icon, check, msg in checks:
			lines.append(f"  {icon}  {check}: {msg}")
		lines.append("")
		if failed == 0:
			lines.append("Ergebnis: ALLE CHECKS BESTANDEN ✓")
		elif passed > 0:
			lines.append(f"Ergebnis: {passed}/{passed+failed} bestanden – bitte prüfen")
		else:
			lines.append("Ergebnis: KRITISCHE PROBLEME – Datei nicht sauber")
		self._write_probe_result(lines)

	def _run_ffprobe_streams(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Analysiere: {filepath}")
		try:
			if raw_output is not None:
				data = json.loads(raw_output)
			else:
				r = subprocess.run(
					[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					 "-show_streams", "-show_format",
					 "-of", "json", filepath],
					capture_output=True, text=True, timeout=30
				)
				data = json.loads(r.stdout)
		except Exception as e:
			self._ffmpeg_log_probe(f"ffprobe Fehler: {e}")
			return

		lines = []
		fmt = data.get("format", {})
		lines.append(f"Format: {fmt.get('format_long_name', '?')}")
		lines.append(f"Duration: {fmt.get('duration', '?')}s")
		lines.append(f"Size: {fmt.get('size', '?')} bytes")
		lines.append(f"Bitrate: {fmt.get('bit_rate', '?')} bps")
		if "creation_time" in fmt.get("tags", {}):
			lines.append(f"Creation Time: {fmt['tags']['creation_time']}")
		lines.append("")

		streams = data.get("streams", [])
		lines.append(f"Streams ({len(streams)}):")
		lines.append("-" * 60)

		for s in streams:
			idx = s.get("index", "?")
			codec = s.get("codec_name", "?")
			stype = s.get("codec_type", "?").upper()
			lines.append(f"  Stream #{idx} [{stype}]")

			if stype == "VIDEO":
				res = f"{s.get('width','?')}x{s.get('height','?')}"
				fps = s.get("r_frame_rate", "?")
				pix = s.get("pix_fmt", "?")
				br = s.get("bit_rate", "?")
				sar = s.get("sample_aspect_ratio", "?")
				dar = s.get("display_aspect_ratio", "?")
				lines.append(f"    Codec: {codec}  Res: {res}  SAR: {sar}  DAR: {dar}")
				lines.append(f"    FPS: {fps}  PixFmt: {pix}  Bitrate: {br} bps")
			elif stype == "AUDIO":
				sr = s.get("sample_rate", "?")
				ch = s.get("channels", "?")
				chl = s.get("channel_layout", "?")
				br = s.get("bit_rate", "?")
				lines.append(f"    Codec: {codec}  SR: {sr}Hz  Ch: {ch} ({chl})  Bitrate: {br} bps")
			elif stype in ("DATA", "SUBTITLE"):
				tags = s.get("tags", {})
				tc = tags.get("timecode", "–")
				lang = tags.get("language", "?")
				lines.append(f"    Type: {codec}  Timecode: {tc}  Lang: {lang}")
			else:
				lines.append(f"    Codec: {codec}")

			extra = []
			tags = s.get("tags", {})
			for k, v in tags.items():
				if k not in ("language", "timecode", "creation_time", "handler_name"):
					extra.append(f"{k}={v}")
			if extra:
				lines.append(f"    Tags: {', '.join(extra)}")

		self._write_probe_result(lines)

	def _run_ffprobe_pts_dts(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"PTS/DTS-Check: {filepath}")
		try:
			if raw_output is not None:
				data = json.loads(raw_output)
			else:
				r = subprocess.run(
					[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					 "-select_streams", "v:0",
					 "-show_packets", "-of", "json", filepath],
					capture_output=True, text=True, timeout=60
				)
				data = json.loads(r.stdout)
		except Exception as e:
			self._ffmpeg_log_probe(f"Fehler: {e}")
			return

		packets = data.get("packets", [])
		if not packets:
			self._ffmpeg_log_probe("Keine Video-Packets gefunden.")
			return

		lines = [f"Video-Packets: {len(packets)}", "-" * 50]
		gaps = []
		non_mono = 0
		last_pts = None

		for p in packets:
			pts = p.get("pts")
			dts = p.get("dts")
			if pts is None:
				continue
			pts = int(pts)
			if last_pts is not None:
				diff = pts - last_pts
				if diff < 0:
					non_mono += 1
					if non_mono <= 5:
						lines.append(f"  Nicht-monoton PTS: {last_pts} → {pts} (Δ={diff})")
				elif diff > 1:
					gaps.append(diff)
					if len(gaps) <= 5:
						lines.append(f"  PTS-Sprung: {last_pts} → {pts} (Δ={diff})")
			last_pts = pts

		lines.append("")
		lines.append(f"Nicht-monotone PTS: {non_mono}")
		lines.append(f"PTS-Sprünge >1: {len(gaps)}")
		if gaps:
			lines.append(f"  Max: {max(gaps)}, Min: {min(gaps)}, Median: {sorted(gaps)[len(gaps)//2]}")
		lines.append(f"Erwartete Packet-Anzahl (bei 25fps): ~{int(data.get('format', {}).get('duration', 0)) * 25}")

		self._write_probe_result(lines)

	def _run_ffprobe_frame_dist(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Frame-Verteilung: {filepath}")
		try:
			if raw_output is not None:
				data = json.loads(raw_output)
			else:
				r = subprocess.run(
					[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					 "-select_streams", "v:0",
					 "-show_frames", "-of", "json", filepath],
					capture_output=True, text=True, timeout=120
				)
				data = json.loads(r.stdout)
		except Exception as e:
			self._ffmpeg_log_probe(f"Fehler: {e}")
			return

		frames = data.get("frames", [])
		if not frames:
			self._ffmpeg_log_probe("Keine Video-Frames gefunden.")
			return

		counts = {"I": 0, "P": 0, "B": 0, "?": 0}
		i_positions = []
		for i, f in enumerate(frames):
			pt = f.get("pict_type", "?")
			counts[pt] = counts.get(pt, 0) + 1
			if pt == "I":
				i_positions.append(i)

		lines = [f"Frames: {len(frames)}", "-" * 50]
		lines.append(f"  I-Frames: {counts['I']}")
		lines.append(f"  P-Frames: {counts['P']}")
		lines.append(f"  B-Frames: {counts['B']}")
		lines.append(f"  Unbekannt: {counts['?']}")
		if len(frames) > 0:
			lines.append(f"  I-Anteil: {counts['I']/len(frames)*100:.1f}%")
			lines.append(f"  P-Anteil: {counts['P']/len(frames)*100:.1f}%")
			lines.append(f"  B-Anteil: {counts['B']/len(frames)*100:.1f}%")

		lines.append("")
		if len(i_positions) > 1:
			i_gaps = [i_positions[j+1] - i_positions[j] for j in range(len(i_positions)-1)]
			avg_gap = sum(i_gaps) / len(i_gaps)
			lines.append(f"I-Frame-Abstände (Frames): Ø={avg_gap:.1f}  Min={min(i_gaps)}  Max={max(i_gaps)}")
			irregular = [g for g in i_gaps if abs(g - avg_gap) > avg_gap * 0.5]
			if irregular:
				lines.append(f"  Unregelmäßige Abstände (>50% Abweichung): {len(irregular)}")
				for j, g in enumerate(i_gaps):
					if abs(g - avg_gap) > avg_gap * 0.5:
						lines.append(f"    Frame {i_positions[j]} → {i_positions[j+1]}: {g}")
		else:
			lines.append("Nur 1 I-Frame (ganzes Video = ein GOP?)")

		self._write_probe_result(lines)

	def _run_ffmpeg_freezedetect(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Freeze-Detect: {filepath}")
		freeze_log = []
		if raw_output is None:
			try:
				r = subprocess.run(
					[str(BASE_DIR / "ffmpeg.exe"), "-v", "info",
					 "-i", filepath,
					 "-vf", "freezedetect",
					 "-f", "null", "-"],
					capture_output=True, text=True, timeout=120
				)
				raw_output = r.stdout + "\n" + r.stderr
			except Exception as e:
				self._ffmpeg_log_probe(f"Fehler: {e}")
				return
		for line in raw_output.split("\n"):
			if "freeze" in line.lower() or "dup" in line.lower():
				freeze_log.append(line.strip())

		lines = ["Freeze-Detect Ergebnisse", "-" * 50]
		if freeze_log:
			lines.extend(freeze_log)
		else:
			lines.append("Keine Freezes oder Duplikate erkannt.")
		lines.append("")
		lines.append("Hinweis: freezedetect erkennt eingefrorene Einzelbilder")
		lines.append("(wiederholte Frames > Standard-Dauer).")

		self._write_probe_result(lines)

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

	def _run_ffmpeg_blackdetect(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Black-Detect: {filepath}")
		results = []
		if raw_output is None:
			try:
				r = subprocess.run(
					[str(BASE_DIR / "ffmpeg.exe"), "-v", "info",
					 "-i", filepath,
					 "-vf", "blackdetect=d=1.0:pic_th=0.98",
					 "-f", "null", "-"],
					capture_output=True, text=True, timeout=120
				)
				raw_output = r.stdout + "\n" + r.stderr
			except Exception as e:
				self._ffmpeg_log_probe(f"Fehler: {e}")
				return
		for line in raw_output.split("\n"):
			if "black_start" in line or "black_end" in line or "black_duration" in line:
				results.append(line.strip())

		lines = ["Black-Detect Ergebnisse", "-" * 50]
		if results:
			lines.extend(results)
			lines.append("")
			durations = []
			for rl in results:
				if "black_duration" in rl:
					try:
						durations.append(float(rl.split("black_duration:")[-1].strip()))
					except ValueError:
						pass
			if durations:
				lines.append(f"Schwarzblenden gesamt: {len(durations)}")
				lines.append(f"  Kürzeste: {min(durations):.2f}s")
				lines.append(f"  Längste:  {max(durations):.2f}s")
				lines.append(f"  Summe:    {sum(durations):.2f}s")
		else:
			lines.append("Keine Schwarzblenden erkannt (d=1.0s, pic_th=0.98).")
		self._write_probe_result(lines)

	def _run_ffmpeg_scenedetect(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Scene-Detect: {filepath}")
		results = []
		if raw_output is None:
			try:
				r = subprocess.run(
					[str(BASE_DIR / "ffmpeg.exe"), "-v", "info",
					 "-i", filepath,
					 "-vf", "scdet",
					 "-f", "null", "-"],
					capture_output=True, text=True, timeout=120
				)
				raw_output = r.stdout + "\n" + r.stderr
			except Exception as e:
				self._ffmpeg_log_probe(f"Fehler: {e}")
				return
		for line in raw_output.split("\n"):
			if "lavfi.scd" in line:
				results.append(line.strip())

		lines = ["Scene-Detect Ergebnisse", "-" * 50]
		if results:
			lines.extend(results)
			lines.append("")
			lines.append(f"Szenenwechsel erkannt: {len(results)}")
		else:
			lines.append("Keine Szenenwechsel erkannt (Standard-Schwellwert).")
		lines.append("")
		lines.append("Hinweis: scdet erfasst Szenenwechsel auf Basis")
		lines.append("von Pixel-Differenzen. Score > 0 = Kandidat.")
		self._write_probe_result(lines)

	def _run_ffmpeg_silencedetect(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Silence-Detect: {filepath}")
		results = []
		if raw_output is None:
			try:
				r = subprocess.run(
					[str(BASE_DIR / "ffmpeg.exe"), "-v", "info",
					 "-i", filepath,
					 "-af", "silencedetect=n=-30dB:d=0.5",
					 "-f", "null", "-"],
					capture_output=True, text=True, timeout=120
				)
				raw_output = r.stdout + "\n" + r.stderr
			except Exception as e:
				self._ffmpeg_log_probe(f"Fehler: {e}")
				return
		for line in raw_output.split("\n"):
			if "silence_start" in line or "silence_end" in line or "silence_duration" in line:
				results.append(line.strip())

		lines = ["Silence-Detect Ergebnisse", "-" * 50]
		if results:
			lines.extend(results)
			lines.append("")
			durations = []
			for rl in results:
				if "silence_duration" in rl:
					try:
						durations.append(float(rl.split("silence_duration:")[-1].strip()))
					except ValueError:
						pass
			if durations:
				lines.append(f"Stille-Passagen gesamt: {len(durations)}")
				lines.append(f"  Kürzeste: {min(durations):.2f}s")
				lines.append(f"  Längste:  {max(durations):.2f}s")
				lines.append(f"  Summe:    {sum(durations):.2f}s")
		else:
			lines.append("Keine Stille erkannt (n=-30dB, d=0.5s).")
		self._write_probe_result(lines)

	def _run_ffprobe_bitrate(self, filepath, raw_output=None):
		self._ffmpeg_log_probe(f"Bitrate-Check: {filepath}")
		try:
			if raw_output is not None:
				data = json.loads(raw_output)
			else:
				r = subprocess.run(
					[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					 "-select_streams", "v:0",
					 "-show_packets", "-of", "json", filepath],
					capture_output=True, text=True, timeout=60
				)
				data = json.loads(r.stdout)
		except Exception as e:
			self._ffmpeg_log_probe(f"Fehler: {e}")
			return

		packets = data.get("packets", [])
		if not packets:
			self._ffmpeg_log_probe("Keine Video-Packets gefunden.")
			return

		dur = self._get_duration(filepath)
		sizes = []
		pts_vals = []
		for p in packets:
			s = p.get("size")
			pts = p.get("pts")
			if s is not None:
				sizes.append(int(s))
			if pts is not None:
				pts_vals.append(int(pts))

		if not sizes:
			self._ffmpeg_log_probe("Keine Größen-Informationen.")
			return

		total_bits = sum(sizes) * 8
		avg_bitrate = total_bits / dur if dur else 0
		sizes_sorted = sorted(sizes)
		n = len(sizes_sorted)
		p10 = sizes_sorted[int(n * 0.1)]
		p90 = sizes_sorted[int(n * 0.9)]
		threshold = sizes_sorted[int(n * 0.95)]
		outliers = [s for s in sizes if s > threshold * 3]

		lines = [
			f"Bitrate-Check Video-Stream",
			"-" * 50,
			f"Packets: {n}",
			f"Dauer: {dur:.2f}s" if dur else "Dauer: ?",
			f"Gesamtgröße: {sum(sizes)} Bytes",
			f"Durchschnittliche Bitrate: {avg_bitrate/1000:.0f} kbps",
			"",
			f"Packet-Größen (Bytes):",
			f"  Min:  {min(sizes)}",
			f"  P10:  {p10}",
			f"  P50:  {sizes_sorted[n//2]}",
			f"  P90:  {p90}",
			f"  Max:  {max(sizes)}",
			"",
			f"10% kleinste Packets: {sum(sizes_sorted[:int(n*0.1)])} Bytes total",
			f"10% größte Packets:  {sum(sizes_sorted[-int(n*0.1):])} Bytes total",
		]
		if outliers:
			lines.append("")
			lines.append(f"Ausreißer (>3× P95): {len(outliers)} Packets")
			for o in outliers[:10]:
				lines.append(f"  {o} Bytes")
			if len(outliers) > 10:
				lines.append(f"  ... und {len(outliers)-10} weitere")

		if len(pts_vals) > 1:
			deltas = [pts_vals[i+1] - pts_vals[i] for i in range(len(pts_vals)-1)]
			irregular = [d for d in deltas if abs(d - max(deltas)) > 0]
			if irregular:
				lines.append("")
				lines.append(f"Unregelmäßige PTS-Abstände: {len(irregular)} von {len(deltas)}")

		lines.append("")
		lines.append("Hinweis: Sehr kleine Packets = leere/Referenz-Frames;")
		lines.append("sehr große = volle I-Frames. Ausreißer deuten")
		lines.append("auf Re-Encoding-Versatz oder Edit hin.")
		self._write_probe_result(lines)

	def _get_duration(self, filepath):
		try:
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-show_entries", "format=duration",
				 "-of", "csv=p=0", filepath],
				capture_output=True, text=True, timeout=15
			)
			out = r.stdout.strip()
			return float(out) if out else 0
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
