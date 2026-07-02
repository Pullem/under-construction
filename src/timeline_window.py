from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene,
							 QGraphicsRectItem, QGraphicsLineItem,
							 QGraphicsSimpleTextItem, QLabel, QHBoxLayout, QWidget)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter


_LANE_NAMES = {0: "Foto", 1: "Video", 2: "Sonstige"}
_LANE_COLORS = {"Foto": QColor("#4FC3F7"), "Video": QColor("#66BB6A"), "Sonstige": QColor("#9E9E9E")}


def _guess_media_type(filename):
	name = filename.lower()
	if name.endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")):
		return "Foto"
	if name.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm", ".mts")):
		return "Video"
	return "Sonstige"


def _extract_timestamp(metadata, exif):
	def _parse(val):
		if not val:
			return None
		try:
			val = str(val).replace("T", " ").split(".")[0].split("+")[0].split("Z")[0].strip()
			for fmt in ("%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M:%S",
						"%d.%m.%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
				try:
					return datetime.strptime(val[:19], fmt)
				except ValueError:
					continue
		except Exception:
			pass
		return None

	# 1. MediaInfo-Tracks (Priorität General > Video > Audio > Other)
	if isinstance(metadata, dict):
		for track_name in ("General", "Video", "Audio", "Other"):
			track = metadata.get(track_name)
			if isinstance(track, dict):
				for key in ("encoded_date", "tagged_date"):
					ts = _parse(track.get(key))
					if ts:
						return ts

	# 2. ExifTool-Daten
	if isinstance(exif, dict):
		for key in ("mediacreatedate", "MediaCreateDate",
					"QuickTime:mediacreatedate", "QuickTime:MediaCreateDate",
					"datetimeoriginal", "DateTimeOriginal",
					"EXIF:datetimeoriginal", "EXIF:DateTimeOriginal",
					"timestamp", "Timestamp",
					"MakerNotes:timestamp", "MakerNotes:Timestamp"):
			ts = _parse(exif.get(key))
			if ts:
				return ts

	# 3. Fallback: weitere MediaInfo-Datumsfelder
	if isinstance(metadata, dict):
		for track_name in ("General", "Video", "Audio", "Other"):
			track = metadata.get(track_name)
			if isinstance(track, dict):
				for key in ("file_creation_date", "file_creation_date_local",
							"creation_date", "TrackCreateDate", "MediaCreateDate"):
					ts = _parse(track.get(key))
					if ts:
						return ts

	# 4. Fallback: weitere ExifTool-Datumsfelder
	if isinstance(exif, dict):
		for key in ("CreateDate", "com.apple.quicktime.creationdate",
					"Creation Date", "File Modification Date/Time",
					"TrackCreateDate", "QuickTime:TrackCreateDate"):
			ts = _parse(exif.get(key))
			if ts:
				return ts

	return None


class TimelineWidget(QWidget):
	def __init__(self, parent=None):
		super().__init__(parent)
		self._media_files = []
		self._case_data = {}
		self._offset_hours = 0

		layout = QVBoxLayout(self)
		layout.setContentsMargins(0, 0, 0, 0)

		self._info_layout = QHBoxLayout()
		self._lbl_info = QLabel()
		self._lbl_count = QLabel()
		self._info_layout.addWidget(self._lbl_info)
		self._info_layout.addStretch()
		self._info_layout.addWidget(self._lbl_count)
		layout.addLayout(self._info_layout)

		self._scene = QGraphicsScene()
		self._view = QGraphicsView(self._scene)
		self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
		self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
		self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
		self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
		self._view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
		layout.addWidget(self._view, 1)

		self._legend_widget = QLabel()
		self._legend_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
		layout.addWidget(self._legend_widget)

	def refresh(self, media_files, case_data, offset_hours=0):
		self._media_files = media_files
		self._case_data = case_data or {}
		self._offset_hours = offset_hours
		self._render()

	def _render(self):
		self._scene.clear()
		items = []
		ts_min, ts_max = None, None

		incident_at = self._case_data.get("incident_at")
		incident_until = self._case_data.get("incident_until")
		info_parts = []
		if incident_at:
			info_parts.append(f"Tatzeit von: {incident_at}")
		if incident_until:
			info_parts.append(f"Tatzeit bis: {incident_until}")
		self._lbl_info.setText(" | ".join(info_parts))

		for f in self._media_files:
			meta = f.get("metadata", {})
			exif = f.get("exif_metadata", {})
			ts = _extract_timestamp(meta, exif)
			if ts and self._offset_hours:
				ts += timedelta(hours=self._offset_hours)
			mtype = _guess_media_type(f.get("file_name", ""))
			if ts:
				if ts_min is None or ts < ts_min:
					ts_min = ts
				if ts_max is None or ts > ts_max:
					ts_max = ts
				items.append((ts, mtype, f.get("file_name", "")))

		self._lbl_count.setText(f"{len(self._media_files)} Mediendateien")

		if not items:
			self._scene.addText("Keine Mediendateien mit Zeitstempeln gefunden.")
			return

		if ts_min == ts_max:
			ts_min -= timedelta(hours=1)
			ts_max += timedelta(hours=1)

		span = (ts_max - ts_min).total_seconds()
		margin = span * 0.05
		ts_start = ts_min - timedelta(seconds=margin)
		ts_end = ts_max + timedelta(seconds=margin)
		total_sec = (ts_end - ts_start).total_seconds()

		chart_w = 900.0
		lane_h = 80.0
		top_margin = 60.0
		lane_labels_w = 100.0

		def x_pos(ts):
			return lane_labels_w + ((ts - ts_start).total_seconds() / total_sec) * chart_w

		lanes = {"Foto": 0, "Video": 1, "Sonstige": 2}
		for mtype, lane in lanes.items():
			y = top_margin + lane * lane_h
			bg = QGraphicsRectItem(QRectF(0, y, lane_labels_w + chart_w, lane_h))
			bg.setBrush(QBrush(QColor("#2a2a2a" if lane % 2 == 0 else "#222222")))
			bg.setPen(QPen(Qt.PenStyle.NoPen))
			self._scene.addItem(bg)

			label = QGraphicsSimpleTextItem(mtype)
			label.setPos(4, y + lane_h / 2 - 8)
			label.setBrush(QBrush(QColor("#888888")))
			f = QFont("Segoe UI", 9)
			f.setBold(True)
			label.setFont(f)
			self._scene.addItem(label)

		crime_at = incident_at
		crime_until = incident_until
		if crime_at and isinstance(crime_at, str):
			try:
				crime_at = datetime.strptime(crime_at[:19], "%Y-%m-%d %H:%M:%S")
				if self._offset_hours:
					crime_at += timedelta(hours=self._offset_hours)
			except ValueError:
				crime_at = None
		if crime_until and isinstance(crime_until, str):
			try:
				crime_until = datetime.strptime(crime_until[:19], "%Y-%m-%d %H:%M:%S")
				if self._offset_hours:
					crime_until += timedelta(hours=self._offset_hours)
			except ValueError:
				crime_until = None

		if crime_at:
			x1 = x_pos(crime_at)
			x2 = x_pos(crime_until) if crime_until else x1 + 20
			band = QGraphicsRectItem(QRectF(x1, top_margin, x2 - x1, lane_h * len(lanes)))
			band.setBrush(QBrush(QColor(255, 50, 50, 30)))
			band.setPen(QPen(QColor(255, 50, 50, 120), 1, Qt.PenStyle.DashLine))
			band.setZValue(-1)
			self._scene.addItem(band)
			# vertikale rote Linie am Tatzeit-Beginn
			line = QGraphicsLineItem(x1, top_margin, x1, top_margin + lane_h * len(lanes))
			line.setPen(QPen(QColor(255, 30, 30), 2))
			line.setZValue(1)
			self._scene.addItem(line)

		dot_size = 12.0
		for ts, mtype, fname in items:
			lane = lanes.get(mtype, 2)
			y = top_margin + lane * lane_h + lane_h / 2 - dot_size / 2
			x = x_pos(ts)
			dot = QGraphicsRectItem(QRectF(x - dot_size / 2, y, dot_size, dot_size))
			color = _LANE_COLORS.get(mtype, QColor("#9E9E9E"))
			dot.setBrush(QBrush(color))
			dot.setPen(QPen(QColor("#ffffff"), 1))
			dot.setToolTip(f"{fname}\n{ts}")
			self._scene.addItem(dot)

		num_ticks = max(5, int(chart_w / 120))
		step = total_sec / num_ticks
		for i in range(num_ticks + 1):
			t = ts_start + timedelta(seconds=i * step)
			x = x_pos(t)
			line = QGraphicsLineItem(x, top_margin, x, top_margin + lane_h * len(lanes))
			line.setPen(QPen(QColor("#444444"), 0.5))
			line.setZValue(-2)
			self._scene.addItem(line)
			label = QGraphicsSimpleTextItem(t.strftime("%d.%m.%Y\n%H:%M"))
			label.setPos(x - 25, top_margin + lane_h * len(lanes) + 4)
			label.setBrush(QBrush(QColor("#888888")))
			f = QFont("Segoe UI", 7)
			label.setFont(f)
			self._scene.addItem(label)

		self._scene.setSceneRect(0, 0, lane_labels_w + chart_w, top_margin + lane_h * len(lanes) + 50)
		self._legend_widget.setText(
			"<span style='color:#4FC3F7;'>\u25a0 Foto</span> &nbsp;"
			"<span style='color:#66BB6A;'>\u25a0 Video</span> &nbsp;"
			"<span style='color:#9E9E9E;'>\u25a0 Sonstige</span> &nbsp;"
			"<span style='color:#ff3232;'>\u2588 Tatzeit</span>"
		)


class TimelineWindow(QDialog):
	def __init__(self, media_files, case_data, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Forensische Zeitachsen-Analyse")
		self.resize(1100, 600)
		layout = QVBoxLayout(self)
		self._widget = TimelineWidget()
		layout.addWidget(self._widget)
		self._widget.refresh(media_files, case_data)
