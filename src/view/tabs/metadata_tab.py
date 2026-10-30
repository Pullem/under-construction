"""Tab: Metadaten."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QLineEdit, QPushButton, QListWidget, QTabWidget)
from PyQt6.QtCore import Qt


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
	view.thumb_label.setStyleSheet(
		"border: 1px solid #3c3c3c; border-radius: 4px; background-color: #000000; color: #777777;"
	)

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