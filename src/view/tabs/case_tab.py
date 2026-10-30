"""Tab: Fallübersicht / Neuen Fall anlegen / Fallexplorer."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QLineEdit, QPushButton, QTextEdit, QDateEdit,
							 QTimeEdit, QCheckBox, QTableWidget, QHeaderView)
from PyQt6.QtCore import Qt, QDate, QTime


def build_case_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	title = QLabel("<b>Fallübersicht</b>")
	layout.addWidget(title)

	view.lbl_case_name = QLabel("Aktueller Fall: —")
	layout.addWidget(view.lbl_case_name)

	layout.addSpacing(20)
	layout.addWidget(QLabel("<b>Neuen Fall anlegen</b>"))

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
	view.d_incident.setMinimumWidth(140)
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
	view.d_incident_until.setMinimumWidth(140)
	view.d_incident_until.setVisible(False)
	tatzeit_layout.addWidget(view.d_incident_until)
	view.t_incident_until = QTimeEdit(QTime(0, 0))
	view.t_incident_until.setDisplayFormat("HH:mm")
	view.t_incident_until.setVisible(False)
	tatzeit_layout.addWidget(view.t_incident_until)
	tatzeit_layout.addStretch()
	layout.addLayout(tatzeit_layout)

	btn_create = QPushButton("Neuen Fall anlegen")
	btn_create.clicked.connect(view._on_create_case)
	btn_create.setObjectName("btnPrimary")
	layout.addWidget(btn_create)

	layout.addSpacing(20)
	layout.addWidget(QLabel("<b>Fallexplorer</b>"))

	view.case_search = QLineEdit()
	view.case_search.setPlaceholderText("In Fallbeschreibungen suchen...")
	view.case_search.setClearButtonEnabled(True)
	view.case_search.textChanged.connect(view.apply_case_filter)
	layout.addWidget(view.case_search)

	view.case_list = QTableWidget()
	view.case_list.setColumnCount(4)
	view.case_list.setHorizontalHeaderLabels(
		["Tatzeit", "Fallname", "Beschreibung", "Erstelldatum"])
	view.case_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
	view.case_list.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
	view.case_list.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
	view.case_list.verticalHeader().setVisible(False)
	view.case_list.setSortingEnabled(False)

	header = view.case_list.horizontalHeader()
	header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
	header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
	header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
	header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

	view.case_list.itemDoubleClicked.connect(view._on_case_selected)
	layout.addWidget(view.case_list, 1)

	btn_open = QPushButton("Ausgewählten Fall öffnen")
	btn_open.clicked.connect(view._on_case_selected)
	layout.addWidget(btn_open)

	view.nav_bar.addTab("Fallübersicht")
	view.content_stack.addWidget(widget)