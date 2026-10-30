"""Tab: Einstellungen."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
							 QLineEdit, QPushButton, QComboBox)


def build_settings_tab(view):
	widget = QWidget()
	layout = QVBoxLayout(widget)

	layout.addWidget(QLabel("<b>Einstellungen</b>"))
	layout.addSpacing(20)

	# GPU Status Section
	layout.addWidget(QLabel("<b>GPU-Beschleunigung (RTX 2080 Super)</b>"))
	view.lbl_gpu_status = QLabel("Prüfe...")
	view.lbl_gpu_status.setStyleSheet("background-color: #252526; color: #b8b8b8; padding: 7px 9px; border: 1px solid #3c3c3c; border-radius: 4px;")
	layout.addWidget(view.lbl_gpu_status)
	layout.addSpacing(15)

	layout.addWidget(QLabel("Datenbank-Benutzer:"))
	view.lbl_db_user = QLabel("—")
	view.lbl_db_user.setStyleSheet("background-color: #252526; color: #b8b8b8; padding: 7px 9px; border: 1px solid #3c3c3c; border-radius: 4px;")
	layout.addWidget(view.lbl_db_user)

	layout.addWidget(QLabel("Datenbank-Passwort:"))
	pw_layout = QHBoxLayout()
	view.lbl_db_password = QLabel("—")
	view.lbl_db_password.setStyleSheet("background-color: #252526; color: #b8b8b8; padding: 7px 9px; border: 1px solid #3c3c3c; border-radius: 4px;")
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
	view.lbl_root_password.setStyleSheet("background-color: #252526; color: #b8b8b8; padding: 7px 9px; border: 1px solid #3c3c3c; border-radius: 4px;")
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
	view.lbl_tz_info.setStyleSheet("color: #7ddc7d; font-weight: bold; padding-left: 8px;")
	layout.addWidget(view.lbl_tz_info)

	layout.addSpacing(10)
	btn_save = QPushButton("Einstellungen speichern")
	btn_save.clicked.connect(view._on_save_settings)
	btn_save.setObjectName("btnPrimary")
	layout.addWidget(btn_save)

	layout.addStretch()

	view.nav_bar.addTab("Einstellungen")
	view.content_stack.addWidget(widget)