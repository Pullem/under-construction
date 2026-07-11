import math
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QPushButton, QCheckBox, QRadioButton, QButtonGroup,
							 QGroupBox, QGridLayout, QStyle)
from PyQt6.QtCore import Qt, pyqtSignal, QProcess, QByteArray, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPixmap, QPolygonF


class TrimWidget(QWidget):
	trim_changed = pyqtSignal(int, int)  # start_frame, end_frame

	def __init__(self, parent=None):
		super().__init__(parent)
		self._filepath = ""
		self._fps = 25.0
		self._total_frames = 0
		self._start_frame = 0
		self._end_frame = 0
		self._keyframes = []
		self._snap_to_keyframe = True
		self._mode = "stream_copy"  # oder "ffv1"

		self._dragging = None  # "in" oder "out"
		self._preview_start = None
		self._preview_end = None
		self._preview_procs = []

		self._build_ui()
		self.setMinimumHeight(260)

	def _build_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(4, 4, 4, 4)
		layout.setSpacing(6)

		# Radio-Buttons
		mode_layout = QHBoxLayout()
		self._mode_group = QButtonGroup(self)
		self._rb_streamcopy = QRadioButton("Stream Copy (lossless)")
		self._rb_ffv1 = QRadioButton("FFV1 Re-encode")
		self._mode_group.addButton(self._rb_streamcopy, 0)
		self._mode_group.addButton(self._rb_ffv1, 1)
		self._rb_streamcopy.setChecked(True)
		self._rb_streamcopy.toggled.connect(self._on_mode_changed)
		mode_layout.addWidget(self._rb_streamcopy)
		mode_layout.addWidget(self._rb_ffv1)
		mode_layout.addStretch()
		layout.addLayout(mode_layout)

		# Preview-Zeile (oberhalb Timeline)
		preview_row = QHBoxLayout()
		preview_row.setSpacing(20)

		preview_col_start = QVBoxLayout()
		preview_col_start.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self._lbl_preview_title_start = QLabel("Start")
		self._lbl_preview_title_start.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self._lbl_preview_title_start.setStyleSheet("color: #4FC3F7; font-size: 8pt;")
		preview_col_start.addWidget(self._lbl_preview_title_start)
		self._preview_start_label = QLabel()
		self._preview_start_label.setFixedSize(768, 576)
		self._preview_start_label.setStyleSheet("background: #111; border: 1px solid #4FC3F7;")
		preview_col_start.addWidget(self._preview_start_label, alignment=Qt.AlignmentFlag.AlignCenter)
		preview_row.addLayout(preview_col_start)

		preview_row.addStretch()

		preview_col_end = QVBoxLayout()
		preview_col_end.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self._lbl_preview_title_end = QLabel("Ende")
		self._lbl_preview_title_end.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self._lbl_preview_title_end.setStyleSheet("color: #FF7043; font-size: 8pt;")
		preview_col_end.addWidget(self._lbl_preview_title_end)
		self._preview_end_label = QLabel()
		self._preview_end_label.setFixedSize(768, 576)
		self._preview_end_label.setStyleSheet("background: #111; border: 1px solid #FF7043;")
		preview_col_end.addWidget(self._preview_end_label, alignment=Qt.AlignmentFlag.AlignCenter)
		preview_row.addLayout(preview_col_end)

		layout.addLayout(preview_row)

		# Zeit-Label über der Timeline
		self._time_label = QLabel("—")
		self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self._time_label.setStyleSheet("color: #aaa; font-family: Consolas; font-size: 9pt;")
		layout.addWidget(self._time_label)

		# Timeline-Bar (wird in paintEvent gemalt)
		self._timeline_bar = _TimelineBar(self)
		self._timeline_bar.setMinimumHeight(50)
		self._timeline_bar.trim_changed.connect(self._on_bar_trim_changed)
		layout.addWidget(self._timeline_bar, 1)

		# Info-Zeile
		info_layout = QHBoxLayout()
		self._info_start = QLabel("Start: —")
		self._info_start.setStyleSheet("color: #4FC3F7; font-family: Consolas; font-size: 9pt;")
		info_layout.addWidget(self._info_start)
		self._info_end = QLabel("Ende: —")
		self._info_end.setStyleSheet("color: #FF7043; font-family: Consolas; font-size: 9pt;")
		info_layout.addWidget(self._info_end)
		self._info_dur = QLabel("Dauer: —")
		self._info_dur.setStyleSheet("color: #8f8; font-family: Consolas; font-size: 9pt;")
		info_layout.addWidget(self._info_dur)
		self._info_kf = QLabel("")
		self._info_kf.setStyleSheet("color: #ffcc00; font-family: Consolas; font-size: 9pt;")
		info_layout.addWidget(self._info_kf)
		info_layout.addStretch()
		layout.addLayout(info_layout)

		# Navigations-Buttons
		nav_layout = QHBoxLayout()
		self._btn_prev_frame = QPushButton("◄ Vorheriges Bild")
		self._btn_prev_frame.clicked.connect(lambda: self._nudge_start(-1))
		nav_layout.addWidget(self._btn_prev_frame)
		self._btn_next_frame = QPushButton("Nächstes Bild ►")
		self._btn_next_frame.clicked.connect(lambda: self._nudge_start(1))
		nav_layout.addWidget(self._btn_next_frame)
		nav_layout.addSpacing(10)
		self._btn_prev_kf = QPushButton("◄ Vorheriger K-Frame")
		self._btn_prev_kf.clicked.connect(lambda: self._snap_to_nearest_kf(-1))
		nav_layout.addWidget(self._btn_prev_kf)
		self._btn_next_kf = QPushButton("Nächster K-Frame ►")
		self._btn_next_kf.clicked.connect(lambda: self._snap_to_nearest_kf(1))
		nav_layout.addWidget(self._btn_next_kf)
		nav_layout.addSpacing(10)
		self._cb_snap = QCheckBox("Snap K-Frame")
		self._cb_snap.setChecked(True)
		self._cb_snap.toggled.connect(lambda checked: setattr(self, '_snap_to_keyframe', checked))
		nav_layout.addWidget(self._cb_snap)
		nav_layout.addStretch()
		layout.addLayout(nav_layout)

	def load_file(self, filepath):
		self._filepath = filepath
		if not filepath or not Path(filepath).exists():
			return
		self._fps = self._detect_framerate(filepath)
		self._total_frames = self._detect_total_frames(filepath)
		self._keyframes = self._detect_keyframes(filepath)
		self._start_frame = 0
		self._end_frame = self._total_frames - 1 if self._total_frames > 0 else 0
		self._update_info()
		self._timeline_bar.set_data(self)
		self._timeline_bar.update()
		self._request_preview(self._start_frame, "start")
		self._request_preview(self._end_frame, "end")

	def set_mode(self, mode):
		if mode == "stream_copy":
			self._rb_streamcopy.setChecked(True)
		elif mode == "ffv1":
			self._rb_ffv1.setChecked(True)

	def get_trim_mode(self):
		return self._mode

	def get_start_timecode(self):
		return self._frames_to_tc(self._start_frame)

	def get_end_timecode(self):
		return self._frames_to_tc(self._end_frame)

	def get_start_frame(self):
		return self._start_frame

	def get_end_frame(self):
		return self._end_frame

	def _on_mode_changed(self):
		self._mode = "ffv1" if self._rb_ffv1.isChecked() else "stream_copy"

	def _on_bar_trim_changed(self, start, end):
		self._start_frame = start
		self._end_frame = end
		self._update_info()
		self._request_preview(start, "start")
		self._request_preview(end, "end")
		self.trim_changed.emit(start, end)

	def _nudge_start(self, delta):
		nf = max(0, min(self._total_frames - 1, self._start_frame + delta))
		if nf != self._start_frame:
			self._on_bar_trim_changed(nf, self._end_frame)
			self._timeline_bar.update()

	def _snap_to_nearest_kf(self, direction):
		if not self._keyframes:
			return
		ref = self._start_frame if direction < 0 else self._end_frame
		candidates = [k for k in self._keyframes if (k < ref if direction < 0 else k > ref)]
		if not candidates:
			return
		target = max(candidates) if direction < 0 else min(candidates)
		if direction < 0:
			self._on_bar_trim_changed(target, self._end_frame)
		else:
			self._on_bar_trim_changed(self._start_frame, target)
		self._timeline_bar.update()

	def _update_info(self):
		if self._total_frames <= 0:
			return
		tc_s = self._frames_to_tc(self._start_frame)
		tc_e = self._frames_to_tc(self._end_frame)
		diff = max(0, self._end_frame - self._start_frame)
		tc_d = self._frames_to_tc(diff)
		self._info_start.setText(f"Start: {tc_s}")
		self._info_end.setText(f"Ende: {tc_e}")
		self._info_dur.setText(f"Dauer: {tc_d}")
		self._info_kf.setText(f"Keyframes: {len(self._keyframes)}")
		self._time_label.setText(f"{tc_s}  →  {tc_e}   [{diff} Frames @ {self._fps:.2f} fps]")

	def _frames_to_tc(self, frames):
		if self._fps <= 0:
			return "00:00:00:00"
		total_s = frames / self._fps
		h = int(total_s // 3600)
		r = total_s - h * 3600
		m = int(r // 60)
		s = int(r % 60)
		f = int(round((r - int(r)) * self._fps))
		if f >= int(self._fps):
			f = 0
			s += 1
		return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

	def _detect_framerate(self, filepath):
		try:
			import subprocess
			from ..model.base import BASE_DIR
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
				return float(num) / float(den)
			elif out:
				return float(out)
		except Exception:
			pass
		return 25.0

	def _detect_total_frames(self, filepath):
		try:
			import subprocess
			from ..model.base import BASE_DIR
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-select_streams", "v:0",
				 "-show_entries", "stream=nb_frames",
				 "-of", "csv=p=0", filepath],
				capture_output=True, text=True, timeout=15
			)
			out = r.stdout.strip()
			if out:
				return int(out)
		except Exception:
			pass
		# Fallback: Dauer * fps
		try:
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-show_entries", "format=duration",
				 "-of", "csv=p=0", filepath],
				capture_output=True, text=True, timeout=15
			)
			dur = r.stdout.strip()
			if dur:
				return int(float(dur) * self._fps)
		except Exception:
			pass
		return 0

	def _detect_keyframes(self, filepath):
		try:
			import subprocess
			from ..model.base import BASE_DIR
			r = subprocess.run(
				[str(BASE_DIR / "ffprobe.exe"), "-v", "error",
				 "-select_streams", "v:0",
				 "-show_frames", "-of", "csv=pict_type", filepath],
				capture_output=True, text=True, timeout=120
			)
			types = [line.strip() for line in r.stdout.split("\n") if line.strip()]
			return [i for i, pt in enumerate(types) if pt == "I"]
		except Exception:
			return []

	def _request_preview(self, frame, target):
		if not self._filepath or self._fps <= 0:
			return
		# Alte Prozesse für dieses Target killen
		self._preview_procs = [p for p in self._preview_procs if p.property("target") != target]
		ts = frame / self._fps
		from ..model.base import BASE_DIR
		proc = QProcess()
		proc.setProperty("target", target)
		proc.setProperty("frame", frame)
		cmd = [
			str(BASE_DIR / "ffmpeg.exe"),
			"-i", self._filepath,
			"-ss", str(ts),
			"-vframes", "1",
			"-f", "image2pipe",
			"-vcodec", "bmp", "-"
		]
		proc.readyReadStandardOutput.connect(lambda: self._on_preview_ready(proc, target))
		proc.finished.connect(lambda: self._on_preview_finished(proc, target))
		self._preview_procs.append(proc)
		proc.start(cmd[0], cmd[1:])

	def _on_preview_ready(self, proc, target):
		if not proc.property("_buffer"):
			proc.setProperty("_buffer", QByteArray())
		buf = proc.property("_buffer")
		buf.append(proc.readAllStandardOutput())
		proc.setProperty("_buffer", buf)

	def _on_preview_finished(self, proc, target):
		buf = proc.property("_buffer") or QByteArray()
		if buf.size() < 100:
			if proc in self._preview_procs:
				self._preview_procs.remove(proc)
			return
		pix = QPixmap()
		if pix.loadFromData(buf.data(), "BMP"):
			pix = pix.scaled(768, 576, Qt.AspectRatioMode.KeepAspectRatio,
							 Qt.TransformationMode.SmoothTransformation)
			if target == "start":
				self._preview_start_label.setPixmap(pix)
			else:
				self._preview_end_label.setPixmap(pix)
		if proc in self._preview_procs:
			self._preview_procs.remove(proc)

	def set_start_end_from_tc(self, start_tc, end_tc):
		sf = self._tc_to_frames(start_tc)
		ef = self._tc_to_frames(end_tc)
		if sf >= 0 and ef > sf and ef < self._total_frames:
			self._start_frame = sf
			self._end_frame = ef
			self._update_info()
			self._timeline_bar.update()

	def _tc_to_frames(self, tc):
		try:
			parts = [int(x) for x in tc.split(":")]
			if len(parts) == 4:
				h, m, s, f = parts
				return int(h * 3600 * self._fps + m * 60 * self._fps + s * self._fps + f)
		except (ValueError, AttributeError):
			pass
		return -1


class _TimelineBar(QWidget):
	trim_changed = pyqtSignal(int, int)

	def __init__(self, parent=None):
		super().__init__(parent)
		self._owner = None
		self._dragging = None
		self._margin = 5
		self.setMouseTracking(True)
		self.setCursor(Qt.CursorShape.PointingHandCursor)

	def set_data(self, owner):
		self._owner = owner

	def paintEvent(self, event):
		if not self._owner or self._owner._total_frames <= 0:
			return
		p = QPainter(self)
		p.setRenderHint(QPainter.RenderHint.Antialiasing)

		w = self.width() - self._margin * 2
		h = self.height()
		y_bar = h // 2 - 12
		bar_h = 24

		o = self._owner
		total = o._total_frames
		s_frame = o._start_frame
		e_frame = o._end_frame
		kfs = o._keyframes

		def frame_to_x(f):
			return self._margin + (f / max(1, total)) * w

		# Hintergrund-Balken
		p.fillRect(self._margin, y_bar, w, bar_h, QColor("#333"))

		# Keyframe-Ticks
		if kfs:
			p.setPen(QPen(QColor("#ffcc00"), 2))
			for kf in kfs:
				if 0 <= kf < total:
					x = frame_to_x(kf)
					p.drawLine(int(x), int(y_bar - 4), int(x), int(y_bar + bar_h + 4))

		# Selektion (grün)
		if s_frame < e_frame:
			x1 = frame_to_x(s_frame)
			x2 = frame_to_x(e_frame)
			p.fillRect(int(x1), y_bar, max(1, int(x2 - x1)), bar_h, QColor(42, 122, 42, 180))

		# Marker-Dreiecke
		self._draw_marker(p, frame_to_x(s_frame), y_bar, bar_h, QColor("#4FC3F7"), up=True)
		self._draw_marker(p, frame_to_x(e_frame), y_bar, bar_h, QColor("#FF7043"), up=False)

		p.end()

	def _draw_marker(self, painter, x, y, h, color, up=True):
		painter.setBrush(color)
		painter.setPen(QPen(Qt.PenStyle.NoPen))
		if up:
			tri = QPolygonF([
				QPointF(x - 6, y), QPointF(x + 6, y), QPointF(x, y - 10)
			])
		else:
			tri = QPolygonF([
				QPointF(x - 6, y + h), QPointF(x + 6, y + h), QPointF(x, y + h + 10)
			])
		painter.drawPolygon(tri)

	def mousePressEvent(self, event):
		if not self._owner or self._owner._total_frames <= 0:
			return
		frame = self._x_to_frame(event.position().x())
		s_f = self._owner._start_frame
		e_f = self._owner._end_frame
		# Prüfe Distanz zu In/Out
		dist_s = abs(frame - s_f)
		dist_e = abs(frame - e_f)
		if dist_s < dist_e and dist_s < max(5, self._owner._total_frames * 0.01):
			self._dragging = "in"
		elif dist_e < max(5, self._owner._total_frames * 0.01):
			self._dragging = "out"

	def mouseMoveEvent(self, event):
		if not self._dragging or not self._owner:
			return
		frame = self._x_to_frame(event.position().x())
		frame = max(0, min(self._owner._total_frames - 1, frame))
		if self._owner._snap_to_keyframe and self._owner._keyframes:
			frame = self._snap(frame)
		if self._dragging == "in" and frame < self._owner._end_frame:
			self._owner._start_frame = frame
		elif self._dragging == "out" and frame > self._owner._start_frame:
			self._owner._end_frame = frame
		self._owner._update_info()
		self.update()

	def mouseReleaseEvent(self, event):
		if self._dragging:
			self._dragging = None
			self.trim_changed.emit(self._owner._start_frame, self._owner._end_frame)
			self._owner._request_preview(self._owner._start_frame, "start")
			self._owner._request_preview(self._owner._end_frame, "end")

	def _x_to_frame(self, x):
		w = self.width() - self._margin * 2
		if w <= 0:
			return 0
		return int((x - self._margin) / w * self._owner._total_frames)

	def _snap(self, frame):
		if not self._owner._keyframes:
			return frame
		return min(self._owner._keyframes, key=lambda kf: abs(kf - frame))
