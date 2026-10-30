"""Tab: Hex-Viewer."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QSpinBox, QLineEdit, QPushButton, QComboBox)
from ..hex_view import HexViewWidget


def build_hex_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel("<b>Hex-Viewer</b>"))
	layout.addSpacing(8)

	# Toolbar Zeile 1: Datei + Schrift + Offset
	toolbar = QHBoxLayout()
	view.hex_file_label = QLabel("–")
	view.hex_file_label.setStyleSheet("color: #b0b0b0;")
	toolbar.addWidget(view.hex_file_label, 1)

	toolbar.addWidget(QLabel("Schrift:"))
	view.hex_font_spin = QSpinBox()
	view.hex_font_spin.setRange(6, 24)
	view.hex_font_spin.setValue(9)
	view.hex_font_spin.setFixedWidth(70)
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
	view.hex_search_mode.setFixedWidth(110)
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
	view.hex_search_status.setStyleSheet("color: #9a9a9a;")
	search_bar.addWidget(view.hex_search_status)
	search_bar.addStretch()
	layout.addLayout(search_bar)

	view.hex_viewer = HexViewWidget()
	view.hex_viewer.setStyleSheet("border: 1px solid #3c3c3c;")
	view.hex_viewer.search_moved.connect(view._on_hex_search_moved)
	layout.addWidget(view.hex_viewer, 1)

	view.hex_status = QLabel("–")
	view.hex_status.setStyleSheet("color: #9a9a9a;")
	layout.addWidget(view.hex_status)

	view.nav_bar.addTab("Hex-Viewer")
	view.content_stack.addWidget(widget)