"""Tab: Medien Import."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton)


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
	btn_import.setObjectName("btnPrimary")
	layout.addWidget(btn_import)

	layout.addStretch()

	view.nav_bar.addTab("Import")
	view.content_stack.addWidget(widget)