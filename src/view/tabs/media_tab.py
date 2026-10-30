"""Tab: Videos / Bilder (gemeinsame build_media_tab + Builders)."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QPushButton, QGridLayout, QComboBox, QTimeEdit,
							 QLineEdit, QPlainTextEdit, QSplitter, QTabWidget,
							 QProgressBar, QSizePolicy)
from PyQt6.QtCore import Qt, QTime

from .widgets import AnalysisTabWidget
from ..trim_widget import TrimWidget
from ..ffmpeg_presets import (preset_trim, preset_frames, preset_audio,
	preset_timecode, preset_container, preset_hash, preset_custom,
	preset_bitstream)


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
	file_label.setStyleSheet("color: #b0b0b0;")
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
		params_group.setStyleSheet("QWidget#ffmpeg_params { border: 1px solid #3c3c3c; border-radius: 6px; padding: 8px; }")
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
		encoded_label.setStyleSheet("color: #9a9a9a;")
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
			("noise", "Rauschprofil"),
			("sharpness", "Schärfe"),
			("motion", "Bewegung"),
			("stabilizer", "Stabilizer"),
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
		btn.setObjectName("btnAnalysis")
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
		btn.setStyleSheet("border: 1px solid #4a4a4a;")
		btn.clicked.connect(lambda checked, m=mode: view._on_plugin_btn_clicked(m))
		setattr(view, f"{prefix}_pbtn_{mode}", btn)
		plugin_toolbar.addWidget(btn, 1 if not is_video else 0)
	if not is_video:
		layout.addLayout(plugin_toolbar)
	else:
		left_layout.addLayout(plugin_toolbar)

	analysis_result = QPlainTextEdit()
	analysis_result.setReadOnly(True)
	analysis_result.setStyleSheet(
		"background-color: #0d0d0d; color: #4ec94e; font-family: Consolas; font-size: 9pt; "
		"border: 1px solid #333333; border-radius: 4px; padding: 6px; "
		"selection-background-color: #1e4d2b; selection-color: #e8ffe8;"
	)
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
		btn_run.setObjectName("btnPrimary")
		setattr(view, f"{prefix}_btn_run", btn_run)
		run_layout.addWidget(btn_run)

		btn_abort = QPushButton("✕ Abbrechen")
		btn_abort.setMinimumHeight(36)
		btn_abort.setEnabled(False)
		btn_abort.clicked.connect(view._on_ffmpeg_abort)
		btn_abort.setStyleSheet(
			"QPushButton { color: #ff8a80; } QPushButton:disabled { color: #8a5a5a; }"
		)
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
		ffmpeg_log.setStyleSheet(
			"background-color: #0d0d0d; color: #4ec94e; font-family: Consolas; font-size: 9pt; "
			"border: 1px solid #333333; border-radius: 4px; padding: 6px; "
			"selection-background-color: #1e4d2b; selection-color: #e8ffe8;"
		)
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