"""FFprobe/FFmpeg-Analyse-Runner: baut Kommandos und führt Analysen aus."""

import json
import subprocess
from pathlib import Path

from ...model.base import BASE_DIR
from .utils import get_duration, get_framerate


class AnalyzerMixin:
	"""Führt ffprobe/ffmpeg-Analysen aus und formatiert Ergebnisse."""

	def _build_ffprobe_cmd(self, filepath, mode):
		hwaccel_args = self._get_hwaccel_args(for_decode=True)
		base_decode = [str(BASE_DIR / "ffmpeg.exe"), "-v", "info"] + hwaccel_args + ["-i", filepath]
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
			return base_decode + ["-vf", "freezedetect", "-f", "null", "-"]
		if mode == "blackdetect":
			return base_decode + ["-vf", "blackdetect=d=1.0:pic_th=0.98", "-f", "null", "-"]
		if mode == "scenedetect":
			return base_decode + ["-vf", "scdet", "-f", "null", "-"]
		if mode == "silencedetect":
			return base_decode + ["-af", "silencedetect=n=-30dB:d=0.5", "-f", "null", "-"]
		if mode == "bitrate":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-select_streams", "v:0", "-show_packets", "-of", "json", filepath]
		if mode == "quickcheck":
			return [str(BASE_DIR / "ffprobe.exe"), "-v", "error",
					"-show_streams", "-show_format", "-of", "json", filepath]
		return []

	# --- ffprobe: quickcheck ---
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

		if video_streams:
			w = video_streams[0].get("width", 0)
			h = video_streams[0].get("height", 0)
			if w > 0 and h > 0:
				ar = w / h
				if w >= 320 and h >= 240:
					check_ar = False
					for sar in STANDARD_ARS:
						if abs(ar - sar) < TOLERANCE:
							check_ar = True
							break
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

	# --- ffprobe: streams ---
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

	# --- ffprobe: pts/dts ---
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

	# --- ffprobe: frame distribution ---
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

	# --- ffmpeg: freezedetect ---
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

	# --- ffmpeg: blackdetect ---
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

	# --- ffmpeg: scenedetect ---
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

	# --- ffmpeg: silencedetect ---
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

	# --- ffprobe: bitrate ---
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

		dur = get_duration(filepath)
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