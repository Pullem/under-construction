"""Hex-Viewer-Steuerung der Hauptansicht."""

from PyQt6.QtWidgets import QFileDialog
class HexControlsMixin:
	"""Hex-Viewer-Tab: Öffnen, Sprung, Suche, Statuszeile."""

	def _on_hex_open(self):
		path, _ = QFileDialog.getOpenFileName(
			self, "Datei öffnen", "",
			"Alle Dateien (*.*)"
		)
		if path:
			self.set_hex_file(path)

	def _on_hex_goto(self):
		self.hex_viewer.goto_offset(self.hex_goto_input.text())

	def _on_hex_font_size(self, size):
		self.hex_viewer.set_font_size(size)

	def _on_hex_search(self):
		text = self.hex_search_input.text().strip()
		mode = self.hex_search_mode.currentData()
		self.hex_viewer.search(text, mode)

	def _on_hex_search_next(self):
		self.hex_viewer.search_next()

	def _on_hex_search_prev(self):
		self.hex_viewer.search_prev()

	def _on_hex_search_moved(self, index, total):
		if total > 0:
			self.hex_search_status.setText(f"{index}/{total}")
		else:
			self.hex_search_status.setText("")

	def set_hex_file(self, path):
		self.hex_viewer.set_file(path)
		self.hex_file_label.setText(path)
		self.hex_file_label.setToolTip(path)
		size = self.hex_viewer._file_size
		if size > 0:
			self.hex_status.setText(f"Datei: {path}  |  Größe: {size:,} Bytes  |  Zeilen: {self.hex_viewer._total_lines:,}")
		else:
			self.hex_status.setText("–")
