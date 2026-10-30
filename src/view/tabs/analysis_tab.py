"""Tab: Auswertung (Timeline) und Platzhalter-Tabs."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QPushButton, QSlider, QComboBox)
from PyQt6.QtCore import Qt

from ...timeline_window import TimelineWidget


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