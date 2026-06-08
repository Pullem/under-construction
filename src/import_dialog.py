import os
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
	QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
	QPushButton, QListWidget, QFileDialog, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from PyQt6.QtWidgets import QComboBox



# ---------------------------------------------------------
# DROP-FÄHIGE LISTWIDGET
# ---------------------------------------------------------
class DropListWidget(QListWidget):
	fileDropped = pyqtSignal(str)

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setAcceptDrops(True)

	def dragEnterEvent(self, event: QDragEnterEvent):
		if event.mimeData().hasUrls():
			event.acceptProposedAction()
		else:
			event.ignore()

	def dragMoveEvent(self, event: QDragEnterEvent):
		if event.mimeData().hasUrls():
			event.acceptProposedAction()
		else:
			event.ignore()

	def dropEvent(self, event: QDropEvent):
		if event.mimeData().hasUrls():
			for url in event.mimeData().urls():
				path = url.toLocalFile()
				if os.path.isfile(path):
					self.fileDropped.emit(path)
			event.acceptProposedAction()
		else:
			event.ignore()


# ---------------------------------------------------------
# WORKER-SIGNALE
# ---------------------------------------------------------
class ImportSignals(QObject):
	progress = pyqtSignal(int)
	file_done = pyqtSignal(dict)
	finished = pyqtSignal()
	error = pyqtSignal(str)


# ---------------------------------------------------------
# IMPORT-WORKER (läuft im ThreadPool)
# ---------------------------------------------------------
class ImportWorker(QRunnable):
	def __init__(self, files, dest_folder, model, supplier_info, delivery_info):
		super().__init__()
		self.files = files
		self.dest_folder = Path(dest_folder)
		self.model = model
		self.supplier_info = supplier_info
		self.delivery_info = delivery_info
		self.signals = ImportSignals()

	def run(self):
		try:
			# 1) Lieferant anlegen oder finden
			supplier = self.model.find_supplier_by_name(self.supplier_info["name"])
			if supplier:
				supplier_id = supplier["id"]
			else:
				supplier_id = self.model.create_supplier(
					self.supplier_info["name"],
					self.supplier_info.get("contact"),
					self.supplier_info.get("role"),
					self.supplier_info.get("notes")
				)

			# 2) Lieferung anlegen
			delivered_at = (
				self.delivery_info.get("delivered_at")
				or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			)

			delivery_id = self.model.create_delivery(
				supplier_id,
				self.model.current_case_id,
				delivered_at,
				self.delivery_info.get("description")
			)

			# 3) Dateien importieren
			total = len(self.files)

			for idx, src in enumerate(self.files, start=1):
				try:
					src_path = Path(src)
					dest_dir = self.dest_folder
					dest_dir.mkdir(parents=True, exist_ok=True)

					dest = dest_dir / src_path.name
					if dest.exists():
						dest = dest_dir / f"{src_path.stem}_{idx}{src_path.suffix}"

					shutil.copy2(src_path, dest)

					# Hash berechnen
					f_hash = self.model.calculate_hash(str(dest))

					# Minimal-Metadaten
					mi_dict = {"imported_from": str(src_path)}
					exif_dict = {}

					# Media speichern
					self.model.save_to_db(
						str(dest),
						dest.name,
						f_hash,
						mi_dict,
						exif_dict
					)

					# media_id holen
					conn = self.model.get_connection()
					if conn:
						cur = conn.cursor(dictionary=True)
						cur.execute("SELECT id FROM media_files WHERE sha256_hash = ?", (f_hash,))
						row = cur.fetchone()
						conn.close()

						if row:
							media_id = row["id"]
							self.model.link_media_to_delivery(media_id, delivery_id)

					self.signals.file_done.emit({
						"src": str(src_path),
						"dest": str(dest),
						"file_name": dest.name
					})

				except Exception as e_file:
					self.signals.error.emit(f"Fehler bei Datei {src}: {e_file}")

				percent = int((idx / total) * 100)
				self.signals.progress.emit(percent)

			self.signals.finished.emit()

		except Exception as e:
			self.signals.error.emit(str(e))


# ---------------------------------------------------------
# IMPORT-DIALOG
# ---------------------------------------------------------
class ImportMediaDialog(QDialog):
	def __init__(self, model, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Import Media")
		self.setMinimumSize(700, 500)
		self.model = model
		self.threadpool = QThreadPool()
		self.files = []

		self.setup_ui()

		# --- Standard-Lieferdatum: jetzt ---
		now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		self.input_date.setText(now_str)


	def setup_ui(self):
		layout = QVBoxLayout()

		# Lieferantenfelder
		supplier_layout = QHBoxLayout()

		# --- Lieferanten-Auswahl (ComboBox) ---
		self.input_supplier = QComboBox()
		self.input_supplier.setEditable(True)
		self.input_supplier.setPlaceholderText("Lieferant Name")

		# Liste der Lieferanten laden
		self._load_suppliers()

		# Wenn ein Lieferant ausgewählt wird → Felder automatisch füllen
		self.input_supplier.currentIndexChanged.connect(self._supplier_selected)
		self.input_supplier.currentTextChanged.connect(self._supplier_selected)


		self.input_contact = QLineEdit()
		self.input_contact.setPlaceholderText("Kontakt (Telefon / Email)")

		self.input_role = QLineEdit()
		self.input_role.setPlaceholderText("Rolle (Zeuge, Polizei, Firma...)")

		supplier_layout.addWidget(self.input_supplier)
		supplier_layout.addWidget(self.input_contact)
		supplier_layout.addWidget(self.input_role)
		layout.addLayout(supplier_layout)

		# Lieferdatum + Beschreibung
		meta_layout = QHBoxLayout()

		self.input_date = QLineEdit()
		self.input_date.setPlaceholderText("Lieferdatum (YYYY-MM-DD HH:MM)")

		# --- PATCH: Jetzt-Button ---
		self.btn_set_now = QPushButton("Jetzt")
		self.btn_set_now.setToolTip("Aktuelles Datum und Uhrzeit eintragen")
		self.btn_set_now.clicked.connect(self._set_now)

		self.input_desc = QLineEdit()
		self.input_desc.setPlaceholderText("Beschreibung der Lieferung")

		meta_layout.addWidget(self.input_date)
		meta_layout.addWidget(self.btn_set_now)
		meta_layout.addWidget(self.input_desc)

		layout.addLayout(meta_layout)

		# Notizen
		self.txt_notes = QTextEdit()
		self.txt_notes.setPlaceholderText("Notizen (optional)")
		layout.addWidget(self.txt_notes)

		# Datei-Liste (mit Drag&Drop)
		layout.addWidget(QLabel("Dateien (Drag & Drop oder 'Dateien hinzufügen')"))

		self.list_widget = DropListWidget()
		self.list_widget.fileDropped.connect(self.add_file)
		layout.addWidget(self.list_widget)

		# Buttons
		btn_layout = QHBoxLayout()
		btn_add = QPushButton("Dateien hinzufügen")
		btn_add.clicked.connect(self.add_files_dialog)

		btn_start = QPushButton("Import starten")
		btn_start.clicked.connect(self.start_import)

		btn_cancel = QPushButton("Abbrechen")
		btn_cancel.clicked.connect(self.reject)

		btn_layout.addWidget(btn_add)
		btn_layout.addWidget(btn_start)
		btn_layout.addWidget(btn_cancel)
		layout.addLayout(btn_layout)

		# Fortschritt
		self.progress = QProgressBar()
		layout.addWidget(self.progress)

		self.setLayout(layout)

	# ---------------------------------------------------------
	# Datei-Handling
	# ---------------------------------------------------------
	def add_files_dialog(self):
		files, _ = QFileDialog.getOpenFileNames(
			self,
			"Dateien auswählen",
			str(Path.home()),
			"Media Files (*.mp4 *.mov *.jpg *.png);;Alle Dateien (*)"
		)
		for f in files:
			self.add_file(f)

	def add_file(self, path):
		if path not in self.files:
			self.files.append(path)
			self.list_widget.addItem(path)

	def _validate_date(self, text):
			"""Prüft, ob das Datum im Format YYYY-MM-DD HH:MM:SS ist."""
			try:
				datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
				return True
			except ValueError:
				return False

	def _set_now(self):
		now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		self.input_date.setText(now_str)


	def _load_suppliers(self):
		"""Lädt alle Lieferanten aus der DB in die ComboBox."""
		conn = self.model.get_connection()
		if not conn:
			return

		try:
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT name FROM suppliers ORDER BY name ASC")
			rows = cur.fetchall()
			for r in rows:
				self.input_supplier.addItem(r["name"])
		finally:
			conn.close()


	def _supplier_selected(self, value):
		# value kann Index (int) oder Text (str) sein
		if isinstance(value, int):
			name = self.input_supplier.itemText(value)
		else:
			name = value

		if not name:
			return

		supplier = self.model.find_supplier_by_name(name)
		if not supplier:
			# Neuer Lieferant → Felder leeren
			self.input_contact.setText("")
			self.input_role.setText("")
			self.txt_notes.setText("")
			self.input_desc.setText("")
			return

		# Bestehender Lieferant → Felder füllen
		self.input_contact.setText(supplier.get("contact", "") or "")
		self.input_role.setText(supplier.get("role", "") or "")
		self.txt_notes.setText(supplier.get("notes", "") or "")

		# Letzte Lieferung holen
		last_delivery = self.model.get_last_delivery_for_supplier(
			supplier["id"],
			self.model.current_case_id
		)

		if last_delivery:
			# Beschreibung übernehmen
			self.input_desc.setText(last_delivery.get("description", "") or "")

			# Datum konvertieren
			dt = last_delivery.get("delivered_at")
			if isinstance(dt, datetime):
				dt = dt.strftime("%Y-%m-%d %H:%M:%S")

			self.input_date.setText(dt or "")
		else:
			# Keine frühere Lieferung → Beschreibung leer lassen
			self.input_desc.setText("")





	# ---------------------------------------------------------
	# Import starten
	# ---------------------------------------------------------
	def start_import(self):
		if not self.files:
			QMessageBox.warning(self, "Keine Dateien", "Bitte mindestens eine Datei hinzufügen.")
			return

		if not self.input_supplier.currentText().strip():
			QMessageBox.warning(self, "Lieferant fehlt", "Bitte den Namen des Lieferanten angeben.")
			return


		# --- PATCH: Datum validieren ---
		date_text = self.input_date.text().strip()
		if date_text and not self._validate_date(date_text):
			QMessageBox.warning(
				self,
				"Ungültiges Datum",
				"Bitte das Datum im Format:\n\nYYYY-MM-DD HH:MM:SS\n\nangeben."
			)
			return



		supplier_info = {
			"name": self.input_supplier.currentText().strip(),
			"contact": self.input_contact.text().strip(),
			"role": self.input_role.text().strip(),
			"notes": self.txt_notes.toPlainText().strip()
		}

		delivery_info = {
			"delivered_at": self.input_date.text().strip() or None,
			"description": self.input_desc.text().strip()
		}

		dest_folder = Path(self.model.current_case_path) / "evidence_input"

		worker = ImportWorker(self.files, dest_folder, self.model, supplier_info, delivery_info)
		worker.signals.progress.connect(self.progress.setValue)
		worker.signals.file_done.connect(self._on_file_done)
		worker.signals.error.connect(self._on_error)
		worker.signals.finished.connect(self._on_finished)

		self.threadpool.start(worker)
		self.setEnabled(False)

	# ---------------------------------------------------------
	# Worker-Signale
	# ---------------------------------------------------------
	def _on_file_done(self, info):
		self.list_widget.addItem(f"Imported: {info['file_name']}")

	def _on_error(self, msg):
		QMessageBox.critical(self, "Import Fehler", msg)
		self.setEnabled(True)

	def _on_finished(self):
		QMessageBox.information(self, "Import fertig", "Alle Dateien wurden importiert.")
		self.setEnabled(True)
		self.accept()
