"""Dunkles Standard-Stylesheet der Hauptansicht (rein grafisch)."""
class DarkStyleMixin:
	"""Dunkles Stylesheet für das Hauptfenster."""

	def apply_dark_style(self):
		"""Einheitliches dunkles Farbschema (rein grafisch, keine Logikänderung)."""
		from pathlib import Path
		assets = (Path(__file__).resolve().parents[1] / "assets").as_posix().replace("\\", "/")

		style = """
			/* ===== Grundflächen ===== */
			QMainWindow { background-color: #1a1a1a; }
			QDialog { background-color: #1a1a1a; color: #e6e6e6; }
			QStackedWidget { background-color: #1e1e1e; border: none; }
			QTabWidget::pane { border: 1px solid #333333; background-color: #1e1e1e; }
			QScrollArea { border: none; background-color: transparent; }

			/* ===== Beschriftungen ===== */
			QLabel { color: #cccccc; font-family: 'Segoe UI', sans-serif; }

			/* ===== Innere Registerkarten ===== */
			QTabBar::tab {
				background-color: #2d2d2d;
				color: #8f8f8f;
				padding: 7px 14px;
				border: 1px solid #333333;
				border-bottom: 2px solid #444444;
				border-top-left-radius: 4px;
				border-top-right-radius: 4px;
			}
			QTabBar::tab:selected {
				background-color: #1e1e1e;
				color: #ffffff;
				border-bottom: 2px solid #2d7dd2;
			}
			QTabBar::tab:hover:!selected { background-color: #383838; color: #d0d0d0; }
			QTabBar::tab:disabled { color: #666666; }

			/* ===== Schaltflächen ===== */
			QPushButton {
				background-color: #2f2f2f;
				color: #e6e6e6;
				border: 1px solid #4a4a4a;
				border-radius: 4px;
				padding: 6px 10px;
			}
			QPushButton:hover { background-color: #3a3a3a; border-color: #5c5c5c; }
			QPushButton:pressed { background-color: #262626; border-color: #444444; }
			QPushButton:disabled { background-color: #242424; color: #6a6a6a; border-color: #333333; }
			QPushButton:checked { background-color: #094771; border-color: #1177bb; color: #ffffff; }
			QPushButton:focus { border-color: #2d7dd2; }
			QPushButton#btnPrimary {
				background-color: #0e639c;
				border-color: #0e639c;
				color: #ffffff;
				font-weight: bold;
			}
			QPushButton#btnPrimary:hover { background-color: #1177bb; border-color: #1177bb; }
			QPushButton#btnPrimary:pressed { background-color: #0a4f7f; border-color: #0a4f7f; }
			QPushButton#btnPrimary:disabled {
				background-color: #243a4a; color: #6a8296; border-color: #2d4a5e;
			}
			/* Kompakte Analyse-Buttons (verhindert beschnittene Beschriftungen) */
			QPushButton#btnAnalysis { padding: 5px 6px; }

			/* ===== Eingabefelder ===== */
			QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox,
			QDoubleSpinBox, QDateEdit, QTimeEdit {
				background-color: #2d2d2d;
				color: #ffffff;
				border: 1px solid #454545;
				border-radius: 4px;
				padding: 5px 8px;
				selection-background-color: #264f78;
				selection-color: #ffffff;
			}
			QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover,
			QSpinBox:hover, QDoubleSpinBox:hover, QDateEdit:hover, QTimeEdit:hover {
				border-color: #5c5c5c;
			}
			QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
			QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus {
				border-color: #2d7dd2;
				background-color: #313131;
			}
			QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
			QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
			QDateEdit:disabled, QTimeEdit:disabled {
				background-color: #242424; color: #6f6f6f; border-color: #333333;
			}
			/* Innerer Editor von SpinBox/Datum (kein doppelter Rahmen) */
			QLineEdit#qt_spinbox_lineedit {
				padding: 0;
				border: none;
				background-color: transparent;
			}

			/* ===== Auswahllisten (Combobox) ===== */
			QComboBox { padding: 5px 28px 5px 8px; }
			QComboBox::drop-down {
				subcontrol-origin: padding;
				subcontrol-position: center right;
				width: 24px;
				border-left: 1px solid #454545;
				background-color: transparent;
			}
			QComboBox::down-arrow {
				image: url("%(assets)s/arrow_down.png");
				width: 9px;
				height: 6px;
			}
			QComboBox QAbstractItemView {
				background-color: #252526;
				color: #e6e6e6;
				border: 1px solid #4a4a4a;
				selection-background-color: #094771;
				selection-color: #ffffff;
				outline: 0;
			}

			/* ===== Datum / Uhrzeit / Spinner ===== */
			QDateTimeEdit { padding: 5px 26px 5px 8px; }
			QDateTimeEdit::up-button, QSpinBox::up-button, QDoubleSpinBox::up-button {
				subcontrol-origin: border;
				subcontrol-position: top right;
				width: 18px;
				border-left: 1px solid #454545;
				border-bottom: none;
				background-color: transparent;
			}
			QDateTimeEdit::down-button, QSpinBox::down-button, QDoubleSpinBox::down-button {
				subcontrol-origin: border;
				subcontrol-position: bottom right;
				width: 18px;
				border-left: 1px solid #454545;
				border-top: none;
				background-color: transparent;
			}
			QDateTimeEdit::up-arrow, QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
				image: url("%(assets)s/arrow_up.png");
				width: 9px;
				height: 6px;
			}
			QDateTimeEdit::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
				image: url("%(assets)s/arrow_down.png");
				width: 9px;
				height: 6px;
			}
			QDateTimeEdit::calendar-button {
				subcontrol-origin: padding;
				subcontrol-position: center right;
				width: 24px;
				border-left: 1px solid #454545;
				background-color: transparent;
				image: url("%(assets)s/calendar.png");
			}

			/* ===== Kalender-Popup ===== */
			QCalendarWidget { background-color: #252526; }
			QCalendarWidget QToolButton {
				background-color: #2f2f2f;
				color: #e6e6e6;
				border: 1px solid #454545;
				border-radius: 3px;
				padding: 3px 6px;
				margin: 1px;
			}
			QCalendarWidget QToolButton:hover { background-color: #3a3a3a; }
			QCalendarWidget QAbstractItemView {
				background-color: #252526;
				color: #e6e6e6;
				selection-background-color: #094771;
				selection-color: #ffffff;
				outline: 0;
			}
			QCalendarWidget QSpinBox, QCalendarWidget QComboBox {
				background-color: #2d2d2d;
				color: #ffffff;
				border: 1px solid #454545;
				border-radius: 3px;
			}

			/* ===== Kontrollkästchen ===== */
			QCheckBox { spacing: 7px; color: #e0e0e0; }
			QCheckBox::indicator {
				width: 15px;
				height: 15px;
				border: 1px solid #5a5a5a;
				border-radius: 3px;
				background-color: #2d2d2d;
			}
			QCheckBox::indicator:hover { border-color: #2d7dd2; }
			QCheckBox::indicator:checked {
				background-color: #0e639c;
				border-color: #1177bb;
				image: url("%(assets)s/check.png");
			}
			QCheckBox::indicator:disabled {
				background-color: #242424;
				border-color: #444444;
			}
			QCheckBox:disabled { color: #6f6f6f; }

			/* ===== Listen ===== */
			QListWidget {
				background-color: #252526;
				color: #eeeeee;
				border: 1px solid #333333;
				border-radius: 4px;
				padding: 2px;
				outline: none;
			}
			QListWidget::item {
				padding: 7px 8px;
				border-left: 2px solid transparent;
				border-bottom: 1px solid #2a2a2a;
			}
			QListWidget::item:selected {
				background-color: #094771;
				color: #ffffff;
				border-left: 2px solid #2d7dd2;
			}
			QListWidget::item:hover:!selected { background-color: #2e3134; }

			/* ===== Tabellen ===== */
			QHeaderView::section {
				background-color: #252526;
				color: #b0b0b0;
				padding: 6px 8px;
				border: none;
				border-right: 1px solid #333333;
				border-bottom: 1px solid #333333;
			}
			QTableWidget {
				background-color: #1e1e1e;
				color: #dddddd;
				gridline-color: #2d2d2d;
				border: 1px solid #333333;
				selection-background-color: #094771;
				selection-color: #ffffff;
			}

			/* ===== Schieberegler ===== */
			QSlider::groove:horizontal {
				height: 4px;
				background-color: #3c3c3c;
				border-radius: 2px;
			}
			QSlider::sub-page:horizontal {
				background-color: #0e639c;
				border-radius: 2px;
			}
			QSlider::handle:horizontal {
				width: 14px;
				margin: -5px 0;
				border-radius: 7px;
				background-color: #e8e8e8;
				border: 1px solid #0e639c;
			}
			QSlider::handle:horizontal:hover { background-color: #ffffff; }

			/* ===== Fortschritt ===== */
			QProgressBar {
				background-color: #2d2d2d;
				border: 1px solid #454545;
				border-radius: 4px;
				text-align: center;
				color: #e6e6e6;
				min-height: 16px;
			}
			QProgressBar::chunk {
				background-color: #0e639c;
				border-radius: 3px;
			}

			/* ===== Bildlaufleisten ===== */
			QScrollBar:vertical {
				background-color: #1a1a1a;
				width: 12px;
				margin: 0;
				border: none;
			}
			QScrollBar::handle:vertical {
				background-color: #4d4d4d;
				min-height: 30px;
				width: 8px;
				margin: 2px;
				border-radius: 4px;
			}
			QScrollBar::handle:vertical:hover { background-color: #606060; }
			QScrollBar:horizontal {
				background-color: #1a1a1a;
				height: 12px;
				margin: 0;
				border: none;
			}
			QScrollBar::handle:horizontal {
				background-color: #4d4d4d;
				min-width: 30px;
				height: 8px;
				margin: 2px;
				border-radius: 4px;
			}
			QScrollBar::handle:horizontal:hover { background-color: #606060; }
			QScrollBar::add-line, QScrollBar::sub-line {
				width: 0;
				height: 0;
				border: none;
				background-color: transparent;
			}
			QScrollBar::add-page, QScrollBar::sub-page {
				background-color: transparent;
			}
			QScrollBar::corner { background-color: transparent; }

			/* ===== Teiler ===== */
			QSplitter::handle { background-color: #333333; }
			QSplitter::handle:horizontal { width: 2px; }
			QSplitter::handle:vertical { height: 2px; }
			QSplitter::handle:hover { background-color: #2d7dd2; }
			QSplitter::handle:pressed { background-color: #1177bb; }

			/* ===== Kontextmenüs und Hinweise ===== */
			QMenu {
				background-color: #252526;
				color: #e0e0e0;
				border: 1px solid #4a4a4a;
				padding: 4px;
			}
			QMenu::item {
				padding: 6px 26px 6px 14px;
				border-radius: 3px;
			}
			QMenu::item:selected { background-color: #094771; color: #ffffff; }
			QMenu::item:disabled { color: #6f6f6f; }
			QMenu::separator { height: 1px; background-color: #3c3c3c; margin: 4px 8px; }
			QToolTip {
				background-color: #2d2d2d;
				color: #e6e6e6;
				border: 1px solid #5a5a5a;
				padding: 4px 8px;
			}
			QMessageBox { background-color: #1e1e1e; }

			/* ===== Statusleiste ===== */
			QStatusBar { background-color: #1f1f1f; color: #b0b0b0; }
			QStatusBar::item { border: none; }
		""" % {"assets": assets}
		self.setStyleSheet(style)
