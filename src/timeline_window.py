import os
import math
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QGraphicsView, QGraphicsScene,
							 QGraphicsRectItem, QGraphicsLineItem, QGraphicsPixmapItem,
							 QGraphicsSimpleTextItem, QLabel, QHBoxLayout, QWidget)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QPixmap


_LANE_COLORS = {"Foto": QColor("#4FC3F7"), "Sonstige": QColor("#9E9E9E")}

# Obergrenzen, damit sehr lange Zeiträume die Szene nicht sprengen
_MAX_CHART_WIDTH = 80_000.0
_MAX_TICKS = 150
_MAX_LABELS = 40
_MAX_PIXMAP_ITEMS = 500


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

	if isinstance(metadata, dict):
		for track_name in ("General", "Video", "Audio", "Other"):
			track = metadata.get(track_name)
			if isinstance(track, dict):
				for key in ("encoded_date", "tagged_date"):
					ts = _parse(track.get(key))
					if ts:
						return ts

	if isinstance(exif, dict):
		for key in ("mediacreatedate", "MediaCreateDate",
					"QuickTime:mediacreatedate", "QuickTime:MediaCreateDate",
					"datetimeoriginal", "DateTimeOriginal",
					"EXIF:datetimeoriginal", "EXIF:DateTimeOriginal",
					"timestamp", "Timestamp",
					"MakerNotes:timestamp", "MakerNotes:Timestamp",
					"File:FileCreateDate",
					"File:FileModifyDate"):
			ts = _parse(exif.get(key))
			if ts:
				return ts

	if isinstance(metadata, dict):
		for track_name in ("General", "Video", "Audio", "Other"):
			track = metadata.get(track_name)
			if isinstance(track, dict):
				for key in ("file_creation_date", "file_creation_date_local",
							"creation_date", "TrackCreateDate", "MediaCreateDate",
							"file_modified_date", "file_modified_date_local"):
					ts = _parse(track.get(key))
					if ts:
						return ts

	if isinstance(exif, dict):
		for key in ("CreateDate", "com.apple.quicktime.creationdate",
					"Creation Date", "File Modification Date/Time",
					"TrackCreateDate", "QuickTime:TrackCreateDate",
					"File:FileAccessDate"):
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
		self._zoom_pct = 100
		self._open_video_requested = None

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

	def refresh(self, media_files, case_data, offset_hours=0, zoom_pct=100):
		hbar = self._view.horizontalScrollBar()
		old_ratio = 0.5
		if hbar.maximum() > 0:
			old_ratio = hbar.value() / max(1, hbar.maximum())

		self._media_files = media_files
		self._case_data = case_data or {}
		self._offset_hours = offset_hours
		self._zoom_pct = zoom_pct
		self._render()

		hbar = self._view.horizontalScrollBar()
		if hbar.maximum() > 0:
			hbar.setValue(int(old_ratio * hbar.maximum()))

	def _render(self):
		self._scene.clear()
		raw_px_per_sec = 2.0 * (self._zoom_pct / 100.0)
		lane_h = 80.0
		ruler_h = 30.0
		lane_labels_w = 120.0
		thumb_max_w = 120.0
		thumb_max_h = lane_h - 8

		incident_at = self._case_data.get("incident_at")
		incident_until = self._case_data.get("incident_until")
		info_parts = []
		if incident_at:
			info_parts.append(f"Tatzeit von: {incident_at}")
		if incident_until:
			info_parts.append(f"Tatzeit bis: {incident_until}")
		self._lbl_info.setText(" | ".join(info_parts))
		self._lbl_count.setText(f"{len(self._media_files)} Mediendateien")

		# Kategorisieren + Zeitstempel extrahieren
		fotos = []
		videos = []
		sonstige = []
		ts_min, ts_max = None, None

		for f in self._media_files:
			meta = f.get("metadata", {})
			exif = f.get("exif_metadata", {})
			ts = _extract_timestamp(meta, exif)
			if ts and self._offset_hours:
				ts += timedelta(hours=self._offset_hours)
			mtype = _guess_media_type(f.get("file_name", ""))
			f["_ts"] = ts
			if not ts:
				continue
			if ts_min is None or ts < ts_min:
				ts_min = ts
			if ts_max is None or ts > ts_max:
				# Für Videos Endzeit berücksichtigen
				dur = f.get("_duration_sec", 0)
				ts_end = ts + timedelta(seconds=dur) if dur else ts
				if ts_max is None or ts_end > ts_max:
					ts_max = ts_end
			if mtype == "Foto":
				fotos.append(f)
			elif mtype == "Video":
				videos.append(f)
			else:
				sonstige.append(f)

		if not fotos and not videos and not sonstige:
			self._scene.addText("Keine Mediendateien mit Zeitstempeln gefunden.")
			return

		if ts_min is None or ts_max is None:
			self._scene.addText("Keine Mediendateien mit Zeitstempeln gefunden.")
			return

		if ts_min == ts_max:
			ts_min -= timedelta(hours=1)
			ts_max += timedelta(hours=1)

		span = (ts_max - ts_min).total_seconds()
		margin = span * 0.03
		ts_start = ts_min - timedelta(seconds=margin)
		ts_end = ts_max + timedelta(seconds=margin)
		total_sec = (ts_end - ts_start).total_seconds()

		chart_total_x = total_sec * raw_px_per_sec
		if chart_total_x > _MAX_CHART_WIDTH:
			chart_total_x = _MAX_CHART_WIDTH
		px_per_sec = chart_total_x / total_sec

		def x_pos(ts):
			rel = (ts - ts_start).total_seconds() / total_sec
			return lane_labels_w + rel * chart_total_x

		# Lane-Liste aufbauen
		lane_configs = []
		lane_configs.append(("Foto", fotos, "foto"))
		vid_lane_idx = 1
		for v in videos:
			name = v.get("file_name", f"Video {vid_lane_idx}")
			lane_configs.append((name, [v], "video"))
			vid_lane_idx += 1
		lane_configs.append(("Sonstige", sonstige, "sonstige"))

		num_lanes = len(lane_configs)
		scene_h = ruler_h + num_lanes * lane_h + 50
		scene_w = lane_labels_w + chart_total_x

		# Hintergrund der Spuren
		for i, (label, _, ltype) in enumerate(lane_configs):
			y = ruler_h + i * lane_h
			bg = QGraphicsRectItem(QRectF(0, y, scene_w, lane_h))
			bg.setBrush(QBrush(QColor("#2a2a2a" if i % 2 == 0 else "#222222")))
			bg.setPen(QPen(Qt.PenStyle.NoPen))
			self._scene.addItem(bg)

			lt = QGraphicsSimpleTextItem(label)
			lt.setPos(4, y + lane_h / 2 - 8)
			lt.setBrush(QBrush(QColor("#888888")))
			f = QFont("Segoe UI", 8)
			f.setBold(True)
			lt.setFont(f)
			self._scene.addItem(lt)

		# Tatzeit-Bereich
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
			band = QGraphicsRectItem(QRectF(x1, ruler_h, x2 - x1, num_lanes * lane_h))
			band.setBrush(QBrush(QColor(255, 50, 50, 30)))
			band.setPen(QPen(QColor(255, 50, 50, 120), 1, Qt.PenStyle.DashLine))
			band.setZValue(-1)
			self._scene.addItem(band)
			line = QGraphicsLineItem(x1, ruler_h, x1, ruler_h + num_lanes * lane_h)
			line.setPen(QPen(QColor(255, 30, 30), 2))
			line.setZValue(1)
			self._scene.addItem(line)

		# Fotos und Sonstige als Punkte/Thumbnails zeichnen
		pixmap_items = 0
		for i, (label, items, ltype) in enumerate(lane_configs):
			y = ruler_h + i * lane_h
			for f in items:
				ts = f.get("_ts")
				if not ts:
					continue
				x = x_pos(ts)
				if ltype == "foto":
					thumbs = f.get("_thumbnails", [])
					if thumbs and pixmap_items < _MAX_PIXMAP_ITEMS:
						tp = thumbs[0]["path"]
						if os.path.exists(tp):
							pix = QPixmap(tp)
							if not pix.isNull():
								scale = min(thumb_max_w / pix.width(), thumb_max_h / pix.height(), 1.0)
								pw = int(pix.width() * scale)
								ph = int(pix.height() * scale)
								item = QGraphicsPixmapItem(pix.scaled(pw, ph, Qt.AspectRatioMode.KeepAspectRatio))
								item.setPos(x - pw / 2, y + (lane_h - ph) / 2)
								item.setToolTip(f"{f.get('file_name','')}\n{ts}")
								self._scene.addItem(item)
								pixmap_items += 1
								continue
					dot = QGraphicsRectItem(QRectF(x - 5, y + lane_h / 2 - 5, 10, 10))
					dot.setBrush(QBrush(_LANE_COLORS.get("Foto", QColor("#4FC3F7"))))
					dot.setPen(QPen(QColor("#ffffff"), 1))
					dot.setToolTip(f"{f.get('file_name','')}\n{ts}")
					self._scene.addItem(dot)
				elif ltype == "sonstige":
					dot = QGraphicsRectItem(QRectF(x - 5, y + lane_h / 2 - 5, 10, 10))
					dot.setBrush(QBrush(_LANE_COLORS.get("Sonstige", QColor("#9E9E9E"))))
					dot.setPen(QPen(QColor("#ffffff"), 1))
					dot.setToolTip(f"{f.get('file_name','')}\n{ts}")
					self._scene.addItem(dot)

		# Video-Filmstreifen zeichnen
		for i, (label, items, ltype) in enumerate(lane_configs):
			if ltype != "video" or not items:
				continue
			y = ruler_h + i * lane_h
			dur = items[0].get("_duration_sec", 0)
			ts = items[0].get("_ts")
			if dur <= 0 or not ts:
				continue
			ts_end = ts + timedelta(seconds=dur)
			x_start = x_pos(ts)
			x_end = x_pos(ts_end)

			# Hintergrund-Balken für die Videodauer
			bar = QGraphicsRectItem(QRectF(x_start, y, x_end - x_start, lane_h))
			bar.setBrush(QBrush(QColor(102, 187, 106, 40)))
			bar.setPen(QPen(QColor("#66BB6A"), 1))
			self._scene.addItem(bar)

			# Thumbnails im Filmstreifen
			thumbs = items[0].get("_thumbnails", [])
			thumb_gap_px = 40.0 * (self._zoom_pct / 100.0)
			last_x = -9999
			for t in thumbs:
				tx = x_start + t["time_sec"] * px_per_sec
				if tx < x_start - 5 or tx > x_end + 5:
					continue
				if tx - last_x < thumb_gap_px:
					continue
				last_x = tx
				tp = t["path"]
				if not os.path.exists(tp):
					continue
				pix = QPixmap(tp)
				if pix.isNull():
					continue
				if pixmap_items >= _MAX_PIXMAP_ITEMS:
					break
				pixmap_items += 1
				scale = min(thumb_max_w / pix.width(), thumb_max_h / pix.height(), 1.0)
				pw = int(pix.width() * scale)
				ph = int(pix.height() * scale)
				pitem = QGraphicsPixmapItem(pix.scaled(pw, ph, Qt.AspectRatioMode.KeepAspectRatio))
				pitem.setPos(tx - pw / 2, y + (lane_h - ph) / 2)
				pitem.setToolTip(f"{items[0].get('file_name','')}\n{timedelta(seconds=int(t['time_sec']))}")
				self._scene.addItem(pitem)

		# Zeitraster oben
		ruler_y = 0
		ruler_bg = QGraphicsRectItem(QRectF(0, 0, scene_w, ruler_h))
		ruler_bg.setBrush(QBrush(QColor("#1a1a1a")))
		ruler_bg.setPen(QPen(Qt.PenStyle.NoPen))
		self._scene.addItem(ruler_bg)

		num_ticks = max(10, min(_MAX_TICKS, int(chart_total_x / 100)))
		step = total_sec / num_ticks
		label_every = max(1, math.ceil(num_ticks / _MAX_LABELS))
		for i in range(num_ticks + 1):
			t = ts_start + timedelta(seconds=i * step)
			x = x_pos(t)
			line = QGraphicsLineItem(x, ruler_h, x, ruler_h + num_lanes * lane_h)
			line.setPen(QPen(QColor("#444444"), 0.5))
			line.setZValue(-2)
			self._scene.addItem(line)
			# Tick auf dem Ruler
			tick = QGraphicsLineItem(x, ruler_y + ruler_h - 6, x, ruler_y + ruler_h)
			tick.setPen(QPen(QColor("#aaaaaa"), 1))
			self._scene.addItem(tick)
			if i % label_every == 0 or i == num_ticks:
				label = QGraphicsSimpleTextItem(t.strftime("%d.%m.%Y\n%H:%M"))
				label.setPos(x - 30, ruler_y + 2)
				label.setBrush(QBrush(QColor("#aaaaaa")))
				f = QFont("Segoe UI", 7)
				label.setFont(f)
				self._scene.addItem(label)

		self._scene.setSceneRect(0, 0, scene_w, scene_h)
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
