from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QLineEdit, QPushButton, QTextEdit, QDateEdit,
							 QTimeEdit, QCheckBox, QListWidget, QTabWidget,
							 QComboBox, QSlider, QPlainTextEdit, QProgressBar,
							 QGridLayout, QSplitter, QSpinBox, QFileDialog,
							 QListWidgetItem, QSizePolicy)
from PyQt6.QtCore import Qt, QDate, QTime, QDateTime, QSize
from PyQt6.QtGui import QPixmap
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter

class AspectFitLabel(QLabel):
	"""QLabel, das sein Pixmap seitenverhältnistreu in die Label-Größe
	einpasst und sich bei Resizes automatisch nachskaliert."""

	def __init__(self, text="", parent=None):
		super().__init__(text, parent)
		self._src = QPixmap()

	def setPixmap(self, pixmap):
		self._src = QPixmap(pixmap)
		self._fit()

	def clear(self):
		self._src = QPixmap()
		super().clear()

	def resizeEvent(self, event):
		super().resizeEvent(event)
		self._fit()

	def _fit(self):
		if self._src.isNull():
			return
		w, h = self.width(), self.height()
		if w <= 0 or h <= 0:
			return
		super().setPixmap(self._src.scaled(
			QSize(w, h), Qt.AspectRatioMode.KeepAspectRatio,
			Qt.TransformationMode.SmoothTransformation))


class AnalysisTabWidget(QWidget):
	"""pyqtgraph-basiertes Ergebnis-Panel für eine Bild-Analyse.

	Oben: Karten-Widget (GraphicsLayoutWidget) mit 1–2 Subplots
	(ImageItem + HistogramLUTItem als Farbskala). Unten: Verteilungs-Plot
	(PlotWidget, Vector-Text wie das Histogramm/Gamma-Fenster). Export der
	Panels als hochauflösende PNGs via pyqtgraph ImageExporter.
	"""

	EXPORT_MAP_WIDTH = 2700
	EXPORT_HIST_WIDTH = 2200

	def __init__(self, mode, parent=None):
		super().__init__(parent)
		self.mode = mode
		self._images = []
		self._luts = []
		self._plots = []
		self._cmaps = []

		self.map_widget = pg.GraphicsLayoutWidget()
		self.map_widget.setBackground("#111111")
		self.map_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
		self.map_widget.setMinimumSize(0, 0)

		if mode == "ela":
			self._add_subplot("hot", lock_aspect=True)
		elif mode == "copymove":
			self._add_subplot(None, lock_aspect=True)
		elif mode == "resample":
			self._add_subplot("coolwarm", lock_aspect=True)
			self._add_subplot("plasma", lock_aspect=False)
		elif mode == "jpeggrid":
			self._add_subplot("inferno", lock_aspect=False)
			self._add_subplot(None, lock_aspect=True)

		self.hist_widget = pg.PlotWidget()
		self.hist_widget.setBackground("#111111")
		self.hist_widget.showGrid(x=False, y=True, alpha=0.15)
		self.hist_widget.getAxis("bottom").setPen(pg.mkPen("#444"))
		self.hist_widget.getAxis("left").setPen(pg.mkPen("#444"))
		self.hist_widget.getAxis("bottom").setTextPen(pg.mkPen("#aaa"))
		self.hist_widget.getAxis("left").setTextPen(pg.mkPen("#aaa"))
		self.hist_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
		self.hist_widget.setMinimumSize(0, 0)
		self._hist_curve = self.hist_widget.plot([], [], pen=pg.mkPen("#0f0", width=1.2))
		self._hist_marker = pg.InfiniteLine(
			angle=90, pen=pg.mkPen("#ff9900", style=Qt.PenStyle.DashLine))
		self._hist_marker.setVisible(False)
		self.hist_widget.addItem(self._hist_marker)

		lay = QVBoxLayout(self)
		lay.setContentsMargins(2, 2, 2, 2)
		lay.addWidget(self.map_widget, 1)
		lay.addWidget(self.hist_widget, 1)

	# ---- Aufbau ----

	def _add_subplot(self, cmap_name, lock_aspect):
		col = len(self._images) * 2
		pi = self.map_widget.addPlot(row=0, col=col)
		vb = pi.getViewBox()
		vb.setAspectLocked(lock_aspect)
		vb.setBackgroundColor("#111111")
		vb.invertY(True)
		pi.hideButtons()
		pi.setMenuEnabled(False)
		for ax in ("left", "bottom", "right", "top"):
			pi.showAxis(ax, False)
		img = pg.ImageItem()
		img.setOpts(axisOrder="row-major")
		img.setAutoDownsample(True)
		pi.addItem(img)
		lut = None
		if cmap_name:
			lut = pg.HistogramLUTItem()
			lut.setImageItem(img)
			self.map_widget.addItem(lut, row=0, col=col + 1)
		self._plots.append(pi)
		self._images.append(img)
		self._luts.append(lut)
		self._cmaps.append(cmap_name)

	# ---- Befüllung ----

	def show_result(self, data):
		if data is None:
			return
		handler = getattr(self, f"_show_{self.mode}", None)
		if handler:
			handler(data)

	def _set_image(self, index, data, vmin, vmax):
		img = self._images[index]
		img.setVisible(True)
		img.setImage(data, autoLevels=True)
		img.setLevels([vmin, vmax])
		lut = self._luts[index]
		if lut is not None:
			lut.gradient.setColorMap(pg.colormap.getFromMatplotlib(self._cmaps[index]))
			lut.setLevels(vmin, vmax)
			lut.setHistogramRange(vmin, vmax)
		self._set_plot_title(index, "")

	def _set_plot_title(self, index, text):
		self._plots[index].setTitle(text, color="#888", size="10pt") if text \
			else self._plots[index].setTitle("")

	def _set_placeholder(self, index, text):
		self._images[index].setVisible(False)
		self._set_plot_title(index, text)

	def _set_histogram(self, x, y, title, xlabel, ylabel, marker=None):
		self.hist_widget.setTitle(title, color="#ccc", size="10pt")
		self.hist_widget.setLabel("bottom", xlabel, color="#aaa", fontsize=9)
		self.hist_widget.setLabel("left", ylabel, color="#aaa", fontsize=9)
		self._hist_curve.setData(x, y)
		if marker is not None:
			self._hist_marker.setValue(marker)
			self._hist_marker.setVisible(True)
		else:
			self._hist_marker.setVisible(False)

	def _set_hist_placeholder(self, title="–"):
		self._hist_curve.setData([], [])
		self._hist_marker.setVisible(False)
		self.hist_widget.setTitle(title, color="#888", size="10pt")

	def _show_ela(self, data):
		diff = data["diff"]
		vmax = float(max(np.percentile(diff.ravel(), 99.9), 1.0))
		self._set_image(0, diff, 0, vmax)
		self._set_plot_title(0, "ELA-Fehlermap")
		vals, edges = np.histogram(diff.ravel(), bins=256, range=(0, vmax))
		self._set_histogram(edges[:-1], vals, "ELA-Histogramm",
							"Fehler-Level", "Pixel")

	def _show_copymove(self, data):
		vis = data.get("vis")
		if vis is None:
			self._set_placeholder(0, "Keine konsistente Transformationsgruppe gefunden")
			self._set_hist_placeholder("Copy-Move: keine Histogramm-Analyse")
			return
		self._set_image(0, vis, 0, 255)
		self._set_plot_title(0, "Copy-Move-Regionen")
		self._set_hist_placeholder("Copy-Move-Visualisierung")

	def _show_resample(self, data):
		self._set_image(0, data["res"], -data["v_lim"], data["v_lim"])
		self._set_plot_title(0, "Resampling-Residual")
		noise_map = data["noise_map"]
		nm = np.nan_to_num(noise_map, nan=0.0)
		self._set_image(1, nm, 0.0, data["noise_vmax"])
		self._set_plot_title(1, "Rausch-Karte")
		valid = noise_map[~np.isnan(noise_map)]
		vals, edges = np.histogram(valid, bins=40)
		self._set_histogram(edges[:-1], vals, "Rausch-Verteilung über Bildblöcke",
							"Rauschniveau (Std-Abweichung)", "Anzahl Blöcke",
							marker=data.get("sigma_noise", 0.0))

	def _show_jpeggrid(self, data):
		block = data.get("block")
		if block is None or not block.size:
			self._set_placeholder(0, "Kein JPEG-Blockraster erkannt")
			self._set_placeholder(1, "–")
			self._set_hist_placeholder("Kein JPEG-Blockraster erkannt")
			return
		self._set_image(0, block, 0.0, data["block_vmax"])
		self._set_plot_title(0, "JPEG-Blockraster")
		overlay = data.get("overlay")
		alpha = data.get("alpha")
		if overlay is not None and alpha is not None:
			rgba = np.dstack([
				(np.clip(overlay, 0, 1) * 255).astype(np.uint8),
				(np.clip(alpha, 0, 1) * 255).astype(np.uint8)])
			self._set_image(1, rgba, 0, 255)
			self._set_plot_title(1, "Grid-Overlay")
		else:
			self._set_placeholder(1, "Kein Grid-Overlay")
		vals, edges = np.histogram(block.ravel(), bins=60)
		self._set_histogram(edges[:-1], vals, "Blockiness-Verteilung",
							"Blockiness", "Anzahl Zellen",
							marker=data.get("block_mean", 0.0))

	# ---- Export ----

	def export_analysis(self, stem, exports_dir):
		exports_dir = Path(exports_dir)
		exports_dir.mkdir(parents=True, exist_ok=True)
		if self.mode == "copymove":
			path = exports_dir / f"{stem}_copymove.png"
			self._export_widget(self.map_widget, path, self.EXPORT_MAP_WIDTH)
			return str(path), None
		errormap_path = exports_dir / f"{stem}_{self.mode}_errormap.png"
		hist_path = exports_dir / f"{stem}_{self.mode}_histogram.png"
		self._export_widget(self.map_widget, errormap_path, self.EXPORT_MAP_WIDTH)
		self._export_widget(self.hist_widget, hist_path, self.EXPORT_HIST_WIDTH)
		return str(errormap_path), str(hist_path)

	def _export_widget(self, widget, path, width):
		item = widget.plotItem if isinstance(widget, pg.PlotWidget) else widget.ci
		if widget.width() <= 0 or widget.height() <= 0:
			widget.resize(800, 400)
		exporter = ImageExporter(item)
		exporter.params["width"] = width
		exporter.export(str(path))


from .hex_view import HexViewWidget
from .trim_widget import TrimWidget
from .ffmpeg_presets import (preset_trim, preset_frames, preset_audio,
	preset_timecode, preset_container, preset_hash, preset_custom,
	preset_bitstream)


def build_case_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	title = QLabel("<b>Fallübersicht</b>")
	layout.addWidget(title)

	view.lbl_case_name = QLabel("Aktueller Fall: —")
	layout.addWidget(view.lbl_case_name)

	layout.addSpacing(20)
	layout.addWidget(QLabel("<b>Fallneuanlage</b>"))

	view.txt_case_name = QLineEdit()
	view.txt_case_name.setPlaceholderText("Fallname")
	layout.addWidget(view.txt_case_name)

	view.txt_case_desc = QTextEdit()
	view.txt_case_desc.setPlaceholderText("Beschreibung")
	view.txt_case_desc.setMaximumHeight(80)
	layout.addWidget(view.txt_case_desc)

	# ---- Tatzeit ----
	tatzeit_layout = QHBoxLayout()
	tatzeit_layout.addWidget(QLabel("Tatzeit:"))
	first_of_month = QDate.currentDate().addDays(-QDate.currentDate().day() + 1)
	view.d_incident = QDateEdit(first_of_month)
	view.d_incident.setCalendarPopup(True)
	view.d_incident.setDisplayFormat("dd.MM.yyyy")
	tatzeit_layout.addWidget(view.d_incident)
	view.t_incident = QTimeEdit(QTime(0, 0))
	view.t_incident.setDisplayFormat("HH:mm")
	tatzeit_layout.addWidget(view.t_incident)
	view.chk_bis = QCheckBox("Bis:")
	view.chk_bis.toggled.connect(view._on_bis_toggled)
	tatzeit_layout.addWidget(view.chk_bis)
	view.d_incident_until = QDateEdit(first_of_month)
	view.d_incident_until.setCalendarPopup(True)
	view.d_incident_until.setDisplayFormat("dd.MM.yyyy")
	view.d_incident_until.setVisible(False)
	tatzeit_layout.addWidget(view.d_incident_until)
	view.t_incident_until = QTimeEdit(QTime(0, 0))
	view.t_incident_until.setDisplayFormat("HH:mm")
	view.t_incident_until.setVisible(False)
	tatzeit_layout.addWidget(view.t_incident_until)
	tatzeit_layout.addStretch()
	layout.addLayout(tatzeit_layout)

	btn_create = QPushButton("Fall erstellen")
	btn_create.clicked.connect(view._on_create_case)
	layout.addWidget(btn_create)

	layout.addSpacing(20)
	layout.addWidget(QLabel("<b>Fallexplorer</b>"))

	view.case_list = QListWidget()
	view.case_list.itemDoubleClicked.connect(view._on_case_selected)
	layout.addWidget(view.case_list, 1)

	btn_open = QPushButton("Ausgewählten Fall öffnen")
	btn_open.clicked.connect(view._on_case_selected)
	layout.addWidget(btn_open)

	view.nav_bar.addTab("Fallübersicht")
	view.content_stack.addWidget(widget)


def build_import_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel("<b>Medien Import</b>"))
	layout.addSpacing(10)
	layout.addWidget(QLabel("Importieren Sie Videodateien und Fotos\nmit Lieferantenangaben in den aktuellen Fall."))
	layout.addSpacing(10)

	btn_import = QPushButton("Import-Dialog öffnen")
	btn_import.setMinimumHeight(80)
	btn_import.clicked.connect(view.import_media_requested.emit)
	layout.addWidget(btn_import)

	layout.addStretch()

	view.nav_bar.addTab("Import")
	view.content_stack.addWidget(widget)


def build_metadata_tab(view):
	widget = QWidget()
	layout = QHBoxLayout(widget)

	left = QVBoxLayout()
	view.search_bar = QLineEdit()
	view.search_bar.setPlaceholderText("Dateiliste filtern...")
	view.search_bar.setClearButtonEnabled(True)
	view.file_list = QListWidget()
	view.btn_scan = QPushButton("Watchfolder scannen")
	view.btn_scan.setToolTip("Scannt den Eingabeordner nach Mediendateien")

	left.addWidget(QLabel("Mediendateien"))
	left.addWidget(view.search_bar)
	left.addWidget(view.file_list, 1)
	left.addWidget(view.btn_scan)

	right = QVBoxLayout()
	view.thumb_label = QLabel("Vorschau")
	view.thumb_label.setFixedSize(320, 180)
	view.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
	view.thumb_label.setStyleSheet("border: 2px solid #333; background: black;")

	view.tabs = QTabWidget()
	view.tabs.setDocumentMode(True)

	right.addWidget(view.thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)
	view.meta_search_bar = QLineEdit()
	view.meta_search_bar.setPlaceholderText("In Metadaten suchen...")
	view.meta_search_bar.setClearButtonEnabled(True)
	right.addWidget(view.meta_search_bar)
	right.addWidget(view.tabs, 1)

	layout.addLayout(left, 1)
	layout.addLayout(right, 3)

	view.btn_scan.clicked.connect(view.scan_requested.emit)
	view.search_bar.textChanged.connect(view.search_changed.emit)
	view.meta_search_bar.textChanged.connect(view._on_meta_search)
	view.file_list.itemClicked.connect(
		lambda item: view.file_selected.emit(item.text())
	)

	view.nav_bar.addTab("Metadaten")
	view.content_stack.addWidget(widget)


def build_media_tab(view, name, prefix, is_video):
	"""Build a combined analysis + processing tab.

	Args:
		view: The view object to attach widgets to.
		name: Display name ("Videos" or "Bilder")
		prefix: Widget name prefix ("video" or "bild")
		is_video: True for full video features, False for image-only
	"""
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel(f"<b>{name}</b>"))
	layout.addSpacing(8)

	# Dateiauswahl (beide Tabs)
	file_layout = QHBoxLayout()
	file_layout.addWidget(QLabel("Datei:"))
	file_label = QLabel("–")
	file_label.setStyleSheet("color: #aaa;")
	setattr(view, f"{prefix}_file_label", file_label)
	file_layout.addWidget(file_label, 1)
	setattr(view, f"{prefix}_input_path", "")
	btn_browse = QPushButton("Durchsuchen")
	btn_browse.clicked.connect(view._on_ffmpeg_browse)
	setattr(view, f"{prefix}_btn_browse", btn_browse)
	file_layout.addWidget(btn_browse)
	layout.addLayout(file_layout)

	# Preset-Buttons (nur Videos)
	if is_video:
		layout.addWidget(QLabel("Presets:"))
		preset_grid = QGridLayout()
		presets = [
			(0, 0, "Trim", lambda: preset_trim(view)),
			(0, 1, "Frames", lambda: preset_frames(view)),
			(0, 2, "Audio", lambda: preset_audio(view)),
			(0, 3, "Timecode", lambda: preset_timecode(view)),
			(1, 0, "Container", lambda: preset_container(view)),
			(1, 1, "Hash", lambda: preset_hash(view)),
			(1, 2, "Custom", lambda: preset_custom(view)),
			(1, 3, "Bitstream", lambda: preset_bitstream(view)),
		]
		for row, col, title, cb in presets:
			btn = QPushButton(title)
			btn.clicked.connect(cb)
			preset_grid.addWidget(btn, row, col)
		layout.addLayout(preset_grid)

	# Parameter (nur Videos)
	if is_video:
		params_group = QWidget()
		params_group.setStyleSheet("QWidget#ffmpeg_params { border: 1px solid #444; padding: 6px; }")
		params_group.setObjectName("ffmpeg_params")
		param_layout = QHBoxLayout(params_group)

		param_layout.addWidget(QLabel("Start:"))
		start = QTimeEdit(QTime(0, 0))
		start.setDisplayFormat("HH:mm:ss")
		setattr(view, f"{prefix}_start", start)
		param_layout.addWidget(start)

		param_layout.addWidget(QLabel("Ende:"))
		end = QTimeEdit(QTime(0, 0))
		end.setDisplayFormat("HH:mm:ss")
		end.setSpecialValueText("–")
		end.clear()
		setattr(view, f"{prefix}_end", end)
		param_layout.addWidget(end)

		param_layout.addWidget(QLabel("Format:"))
		fmt_combo = QComboBox()
		fmt_combo.addItem("FFV1 (lossless)", "ffv1")
		fmt_combo.addItem("H.264 CRF 18", "h264_crf18")
		fmt_combo.addItem("H.264 CRF 10", "h264_crf10")
		setattr(view, f"{prefix}_format", fmt_combo)
		param_layout.addWidget(fmt_combo)

		param_layout.addWidget(QLabel("Filter:"))
		filter_edit = QLineEdit()
		filter_edit.setPlaceholderText("z.B. scale=1280:720,eq=brightness=0.2")
		setattr(view, f"{prefix}_filter", filter_edit)
		param_layout.addWidget(filter_edit, 1)

		layout.addWidget(params_group)
		setattr(view, f"{prefix}_params_group", params_group)

	# Lossless Trim Widget (nur Videos, initial versteckt)
	if is_video:
		trim_widget = TrimWidget()
		trim_widget.setVisible(False)
		setattr(view, f"{prefix}_trim_widget", trim_widget)
		layout.addWidget(trim_widget)

	# Encoded date / time info + UTC-Offset (nur Videos)
	if is_video:
		date_layout = QHBoxLayout()
		date_layout.addWidget(QLabel("encoded:"))
		encoded_label = QLabel("–")
		encoded_label.setStyleSheet("color: #888;")
		setattr(view, f"{prefix}_encoded_label", encoded_label)
		date_layout.addWidget(encoded_label)
		utc_combo = QComboBox()
		utc_combo.addItem("UTC+1", 1)
		utc_combo.addItem("UTC+2", 2)
		setattr(view, f"{prefix}_utc_combo", utc_combo)
		date_layout.addWidget(utc_combo)
		date_layout.addSpacing(20)
		date_layout.addWidget(QLabel("TC-Pos:"))
		tc_pos = QComboBox()
		tc_pos.addItem("oben", "10")
		tc_pos.addItem("unten", "main_h-text_h-10")
		setattr(view, f"{prefix}_tc_pos", tc_pos)
		date_layout.addWidget(tc_pos)
		date_layout.addStretch()
		layout.addLayout(date_layout)

	# ffprobe-Analyse-Buttons + Ergebnis (links im Splitter)
	splitter = QSplitter(Qt.Orientation.Horizontal)

	left_widget = QWidget()
	left_layout = QVBoxLayout(left_widget)
	left_layout.setContentsMargins(0, 0, 4, 0)
	if is_video:
		left_layout.addWidget(QLabel("<b>Analysen</b>"))
	else:
		layout.addWidget(QLabel("<b>Analysen</b>"))

	if is_video:
		analyses = [
			("streams", "Stream-Übersicht"),
			("pts_dts", "PTS/DTS-Check"),
			("frame_dist", "Frame-Verteilung"),
			("freeze", "Freeze-Detect"),
			("blackdetect", "Black-Detect"),
			("scenedetect", "Scene-Detect"),
			("silencedetect", "Silence-Detect"),
			("bitrate", "Bitrate-Check"),
			("quickcheck", "Quick-Check"),
		]
	else:
		analyses = [
			("streams", "Stream-Übersicht"),
			("quickcheck", "Quick-Check"),
			("ela", "ELA-Analyse"),
			("copymove", "Copy-Move"),
			("resample", "Resampling/Rauschen"),
			("jpeggrid", "JPEG Grid"),
		]

	analysis_toolbar = QHBoxLayout()
	for mode, title in analyses:
		btn = QPushButton(title)
		btn.clicked.connect(lambda checked, m=mode: view._on_ffprobe_analyse(m))
		setattr(view, f"{prefix}_btn_{mode}", btn)
		analysis_toolbar.addWidget(btn, 1 if not is_video else 0)

	if not is_video:
		analysis_toolbar.addStretch()
		analysis_toolbar.addWidget(QLabel("Empfindlichkeit:"))
		sens = QComboBox()
		sens.addItem("Standard", "standard")
		sens.addItem("Empfindlich", "empfindlich")
		sens.addItem("Sehr empfindlich", "sehr_empfindlich")
		sens.currentIndexChanged.connect(view._on_sensitivity_changed)
		setattr(view, f"{prefix}_sensitivity", sens)
		analysis_toolbar.addWidget(sens)

	if not is_video:
		layout.addLayout(analysis_toolbar)
	else:
		left_layout.addLayout(analysis_toolbar)

	# Plugin-Buttons (zweite Reihe)
	plugin_toolbar = QHBoxLayout()
	plugin_toolbar.setSpacing(4)
	if is_video:
		plugin_items = [(f"v{i}", f"Dummy V{i}") for i in range(1, 7)]
	else:
		plugin_items = [("histogramm", "Histogramm/Gamma")] + \
			[(f"b{i}", f"Dummy B{i}") for i in range(2, 9)]
	for mode, title in plugin_items:
		btn = QPushButton(title)
		btn.setStyleSheet("border: 1px solid #555;")
		btn.clicked.connect(lambda checked, m=mode: view._on_plugin_btn_clicked(m))
		setattr(view, f"{prefix}_pbtn_{mode}", btn)
		plugin_toolbar.addWidget(btn, 1 if not is_video else 0)
	if not is_video:
		layout.addLayout(plugin_toolbar)
	else:
		left_layout.addLayout(plugin_toolbar)

	analysis_result = QPlainTextEdit()
	analysis_result.setReadOnly(True)
	analysis_result.setStyleSheet("background: #111; color: #0f0; font-family: Consolas; font-size: 9pt;")
	setattr(view, f"{prefix}_result", analysis_result)

	if is_video:
		left_layout.addWidget(analysis_result, 3)
	else:
		# Bilder: großes Ergebnis-Display links (ELA/Copy-Move/…), Terminal rechts
		result_tabs = QTabWidget()
		result_tabs.setDocumentMode(True)

		tab_modes = [
			("ela", "ELA"),
			("copymove", "Copy-Move"),
			("resample", "Resampling/Rauschen"),
			("jpeggrid", "JPEG Grid"),
		]
		for tab_mode, tab_title in tab_modes:
			tab_w = AnalysisTabWidget(tab_mode)
			tab_w.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
			tab_w.setMinimumSize(0, 0)
			setattr(view, f"{prefix}_tab_{tab_mode}", tab_w)
			setattr(view, f"{prefix}_tab_{tab_mode}_error_map", tab_w.map_widget)
			setattr(view, f"{prefix}_tab_{tab_mode}_histogram", tab_w.hist_widget)
			result_tabs.addTab(tab_w, tab_title)

		setattr(view, f"{prefix}_result_tabs", result_tabs)
		result_tabs.tabBar().setVisible(False)
		left_layout.addWidget(result_tabs, 1)

	splitter.addWidget(left_widget)

	# Rechte Seite: ffmpeg-Controls (Videos) oder ELA-Vorschau (Bilder)
	if is_video:
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)
		right_layout.setContentsMargins(4, 0, 0, 0)

		run_layout = QHBoxLayout()
		btn_run = QPushButton("▶ Ausführen")
		btn_run.setMinimumHeight(36)
		btn_run.clicked.connect(view._on_ffmpeg_run)
		setattr(view, f"{prefix}_btn_run", btn_run)
		run_layout.addWidget(btn_run)

		btn_abort = QPushButton("✕ Abbrechen")
		btn_abort.setMinimumHeight(36)
		btn_abort.setEnabled(False)
		btn_abort.clicked.connect(view._on_ffmpeg_abort)
		btn_abort.setStyleSheet("color: #ff6666;")
		setattr(view, f"{prefix}_btn_abort", btn_abort)
		run_layout.addWidget(btn_abort)

		run_layout.addStretch()
		out_label = QLabel("")
		setattr(view, f"{prefix}_out_label", out_label)
		run_layout.addWidget(out_label)
		right_layout.addLayout(run_layout)

		ffmpeg_log = QPlainTextEdit()
		ffmpeg_log.setReadOnly(True)
		ffmpeg_log.setMaximumBlockCount(1000)
		ffmpeg_log.setStyleSheet("background: #111; color: #0f0; font-family: Consolas; font-size: 9pt;")
		setattr(view, f"{prefix}_log", ffmpeg_log)
		right_layout.addWidget(ffmpeg_log, 1)

		progress = QProgressBar()
		progress.setTextVisible(True)
		setattr(view, f"{prefix}_progress", progress)
		right_layout.addWidget(progress)

		splitter.addWidget(right_widget)
		splitter.setStretchFactor(0, 1)
		splitter.setStretchFactor(1, 2)
	else:
		right_widget = QWidget()
		right_layout = QVBoxLayout(right_widget)
		right_layout.setContentsMargins(4, 0, 0, 0)
		right_layout.addWidget(QLabel("<b>Terminal</b>"))
		right_layout.addWidget(analysis_result, 1)

		splitter.addWidget(right_widget)
		splitter.setStretchFactor(0, 3)
		splitter.setStretchFactor(1, 1)

	layout.addWidget(splitter, 1)

	view.nav_bar.addTab(name)
	view.content_stack.addWidget(widget)


def build_videos_tab(view):
	build_media_tab(view, "Videos", "video", True)


def build_bilder_tab(view):
	build_media_tab(view, "Bilder", "bild", False)


def active_media_prefix(view):
	idx = view.nav_bar.currentIndex()
	if idx == 3:   # Videos
		return "video"
	elif idx == 4: # Bilder
		return "bild"
	return "video"


def build_settings_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel("<b>Einstellungen</b>"))
	layout.addSpacing(20)

	layout.addWidget(QLabel("Datenbank-Benutzer:"))
	view.lbl_db_user = QLabel("—")
	view.lbl_db_user.setStyleSheet("background-color: #2d2d2d; color: #ccc; padding: 6px; border: 1px solid #444;")
	layout.addWidget(view.lbl_db_user)

	layout.addWidget(QLabel("Datenbank-Passwort:"))
	pw_layout = QHBoxLayout()
	view.lbl_db_password = QLabel("—")
	view.lbl_db_password.setStyleSheet("background-color: #2d2d2d; color: #ccc; padding: 6px; border: 1px solid #444;")
	view.lbl_db_password.setMinimumWidth(200)
	view.lbl_db_password.setWordWrap(True)
	pw_layout.addWidget(view.lbl_db_password, 1)
	view._pw_visible = False
	view.btn_toggle_pw = QPushButton("\U0001F441")
	view.btn_toggle_pw.setFixedWidth(36)
	view.btn_toggle_pw.setCheckable(True)
	view.btn_toggle_pw.toggled.connect(view._toggle_password_visible)
	pw_layout.addWidget(view.btn_toggle_pw)
	layout.addLayout(pw_layout)

	layout.addWidget(QLabel("MariaDB-Root-Passwort:"))
	root_pw_layout = QHBoxLayout()
	view.lbl_root_password = QLabel("—")
	view.lbl_root_password.setStyleSheet("background-color: #2d2d2d; color: #ccc; padding: 6px; border: 1px solid #444;")
	view.lbl_root_password.setMinimumWidth(200)
	view.lbl_root_password.setWordWrap(True)
	root_pw_layout.addWidget(view.lbl_root_password, 1)
	view._root_pw_visible = False
	view.btn_toggle_root_pw = QPushButton("\U0001F441")
	view.btn_toggle_root_pw.setFixedWidth(36)
	view.btn_toggle_root_pw.setCheckable(True)
	view.btn_toggle_root_pw.toggled.connect(view._toggle_root_pw_visible)
	root_pw_layout.addWidget(view.btn_toggle_root_pw)
	layout.addLayout(root_pw_layout)

	layout.addSpacing(10)
	layout.addWidget(QLabel("Neues Datenbank-Passwort festlegen (optional):"))
	new_pw_layout = QHBoxLayout()
	view.txt_new_db_password = QLineEdit()
	view.txt_new_db_password.setEchoMode(QLineEdit.EchoMode.Password)
	view.txt_new_db_password.setPlaceholderText("leer lassen = kein Update")
	new_pw_layout.addWidget(view.txt_new_db_password)
	view.btn_toggle_new_pw = QPushButton("\U0001F441")
	view.btn_toggle_new_pw.setFixedWidth(36)
	view.btn_toggle_new_pw.setCheckable(True)
	view.btn_toggle_new_pw.toggled.connect(view._toggle_new_pw_visible)
	new_pw_layout.addWidget(view.btn_toggle_new_pw)
	layout.addLayout(new_pw_layout)

	layout.addSpacing(20)
	layout.addWidget(QLabel("Basisordner für neue Fälle:"))
	folder_layout = QHBoxLayout()
	view.txt_case_root = QLineEdit()
	folder_layout.addWidget(view.txt_case_root)
	btn_browse = QPushButton("…")
	btn_browse.setFixedWidth(40)
	btn_browse.clicked.connect(view._on_browse_case_root)
	folder_layout.addWidget(btn_browse)
	layout.addLayout(folder_layout)

	layout.addSpacing(15)
	layout.addWidget(QLabel("<b>Zeitzone (automatisch erkannt)</b>"))
	view.lbl_tz_info = QLabel("–")
	view.lbl_tz_info.setStyleSheet("color: #8f8; font-weight: bold; padding-left: 8px;")
	layout.addWidget(view.lbl_tz_info)

	layout.addSpacing(10)
	btn_save = QPushButton("Einstellungen speichern")
	btn_save.clicked.connect(view._on_save_settings)
	layout.addWidget(btn_save)

	layout.addStretch()

	view.nav_bar.addTab("Einstellungen")
	view.content_stack.addWidget(widget)


def build_hex_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel("<b>Hex-Viewer</b>"))
	layout.addSpacing(8)

	# Toolbar Zeile 1: Datei + Schrift + Offset
	toolbar = QHBoxLayout()
	view.hex_file_label = QLabel("–")
	view.hex_file_label.setStyleSheet("color: #aaa;")
	toolbar.addWidget(view.hex_file_label, 1)

	toolbar.addWidget(QLabel("Schrift:"))
	view.hex_font_spin = QSpinBox()
	view.hex_font_spin.setRange(6, 24)
	view.hex_font_spin.setValue(9)
	view.hex_font_spin.setFixedWidth(50)
	view.hex_font_spin.valueChanged.connect(view._on_hex_font_size)
	toolbar.addWidget(view.hex_font_spin)

	view.hex_open_btn = QPushButton("Öffnen")
	view.hex_open_btn.clicked.connect(view._on_hex_open)
	toolbar.addWidget(view.hex_open_btn)

	view.hex_goto_input = QLineEdit()
	view.hex_goto_input.setPlaceholderText("Offset (hex)")
	view.hex_goto_input.setFixedWidth(110)
	toolbar.addWidget(view.hex_goto_input)

	view.hex_goto_btn = QPushButton("Gehe zu")
	view.hex_goto_btn.clicked.connect(view._on_hex_goto)
	toolbar.addWidget(view.hex_goto_btn)

	layout.addLayout(toolbar)

	# Toolbar Zeile 2: Suche
	search_bar = QHBoxLayout()
	search_bar.addWidget(QLabel("Suche:"))
	view.hex_search_input = QLineEdit()
	view.hex_search_input.setPlaceholderText("Hex (z.B. 00FF) / ASCII / Text")
	view.hex_search_input.returnPressed.connect(view._on_hex_search)
	search_bar.addWidget(view.hex_search_input, 1)
	view.hex_search_mode = QComboBox()
	view.hex_search_mode.addItem("Hex", "hex")
	view.hex_search_mode.addItem("ASCII", "ascii")
	view.hex_search_mode.addItem("Text", "text")
	view.hex_search_mode.setFixedWidth(80)
	search_bar.addWidget(view.hex_search_mode)
	view.hex_search_btn = QPushButton("Suchen")
	view.hex_search_btn.clicked.connect(view._on_hex_search)
	search_bar.addWidget(view.hex_search_btn)
	view.hex_search_prev = QPushButton("▲")
	view.hex_search_prev.setFixedWidth(30)
	view.hex_search_prev.clicked.connect(view._on_hex_search_prev)
	search_bar.addWidget(view.hex_search_prev)
	view.hex_search_next = QPushButton("▼")
	view.hex_search_next.setFixedWidth(30)
	view.hex_search_next.clicked.connect(view._on_hex_search_next)
	search_bar.addWidget(view.hex_search_next)
	view.hex_search_status = QLabel("")
	view.hex_search_status.setStyleSheet("color: #888;")
	search_bar.addWidget(view.hex_search_status)
	search_bar.addStretch()
	layout.addLayout(search_bar)

	view.hex_viewer = HexViewWidget()
	view.hex_viewer.setStyleSheet("border: 1px solid #333;")
	view.hex_viewer.search_moved.connect(view._on_hex_search_moved)
	layout.addWidget(view.hex_viewer, 1)

	view.hex_status = QLabel("–")
	view.hex_status.setStyleSheet("color: #888;")
	layout.addWidget(view.hex_status)

	view.nav_bar.addTab("Hex-Viewer")
	view.content_stack.addWidget(widget)


def build_analysis_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel("<b>Auswertung</b>"))
	layout.addSpacing(10)

	toolbar = QHBoxLayout()
	btn_timeline = QPushButton("Zeitachsen-Analyse")
	btn_timeline.clicked.connect(view.open_timeline_requested.emit)
	toolbar.addWidget(btn_timeline)

	toolbar.addStretch()

	toolbar.addWidget(QLabel("Zoom:"))
	view.slider_zoom = QSlider(Qt.Orientation.Horizontal)
	view.slider_zoom.setRange(25, 400)
	view.slider_zoom.setValue(100)
	view.slider_zoom.setFixedWidth(120)
	view.slider_zoom.setTickPosition(QSlider.TickPosition.TicksBelow)
	view.slider_zoom.setTickInterval(75)
	view.slider_zoom.valueChanged.connect(view.open_timeline_requested.emit)
	toolbar.addWidget(view.slider_zoom)
	view.lbl_zoom = QLabel("100%")
	view.slider_zoom.valueChanged.connect(lambda v: view.lbl_zoom.setText(f"{v}%"))
	toolbar.addWidget(view.lbl_zoom)

	toolbar.addStretch()

	toolbar.addWidget(QLabel("Offset:"))
	view.cbo_offset = QComboBox()
	view.cbo_offset.addItem("Winter UTC+1", 1)
	view.cbo_offset.addItem("Sommer UTC+2", 2)
	view.cbo_offset.currentIndexChanged.connect(view.open_timeline_requested.emit)
	toolbar.addWidget(view.cbo_offset)

	layout.addLayout(toolbar)

	from ..timeline_window import TimelineWidget
	view.timeline_widget = TimelineWidget()
	layout.addWidget(view.timeline_widget, 1)

	view.nav_bar.addTab("Auswertung")
	view.content_stack.addWidget(widget)

	view._is_analysis_built = True


def build_placeholder_tab(view, title):
	widget = QWidget()
	layout = QVBoxLayout(widget)
	label = QLabel(f"{title}\n\nNoch nicht implementiert")
	label.setAlignment(Qt.AlignmentFlag.AlignCenter)
	layout.addWidget(label)
	view.nav_bar.addTab(title)
	view.content_stack.addWidget(widget)
