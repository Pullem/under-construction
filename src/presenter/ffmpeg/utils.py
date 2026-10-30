"""Gemeinsame Hilfsfunktionen für FFmpeg-Operationen."""

import os
import subprocess
from pathlib import Path

from ...model.base import BASE_DIR


def setup_fontconfig(self):
	"""Fontconfig für drawtext unter Windows einrichten."""
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


def get_framerate(filepath: str) -> int | None:
	"""Framerate der Datei per ffprobe ermitteln."""
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


def get_duration(filepath: str) -> float:
	"""Dauer der Datei in Sekunden per ffprobe ermitteln."""
	try:
		r = subprocess.run(
			[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
			 "-show_entries", "format=duration",
			 "-of", "csv=p=0", filepath],
			capture_output=True, text=True, timeout=15
		)
		out = r.stdout.strip()
		return float(out) if out else 0.0
	except Exception:
		return 0.0


def get_keyframes(filepath: str, ffmpeg_log) -> list[tuple[int, float]]:
	"""Keyframes (Frame-Nummer, PTS) per ffprobe ermitteln."""
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
		ffmpeg_log(f"Keyframe-Erkennung fehlgeschlagen: {e}")
		return []


def frame_to_timestamp(frame: int, fps: float) -> str:
	"""Frame-Nummer in HH:MM:SS.mmm wandeln."""
	total_s = frame / fps
	h = int(total_s // 3600)
	m = int((total_s % 3600) // 60)
	s = total_s - h * 3600 - m * 60
	return f"{h:02d}:{m:02d}:{s:06.3f}"