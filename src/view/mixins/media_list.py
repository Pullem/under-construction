"""Medienliste, Metadaten-Suche und Thumbnail-Anzeige."""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
class MediaListMixin:
	"""Medienliste, Metadaten-Suche und Thumbnail-Anzeige."""

	def _on_meta_search(self, query):
		if hasattr(self, "search_metadata_tables"):
			self.search_metadata_tables(query)

	def update_file_list(self, files):
		self.file_list.clear()
		self.file_list.addItems(files)

	def apply_row_filter(self, query):
		for i in range(self.file_list.count()):
			item = self.file_list.item(i)
			item.setHidden(query.lower() not in item.text().lower())

	def clear_metadata_display(self):
		self.tabs.clear()
		self._metadata_tables = []
		self.thumb_label.setText("Vorschau")
		self.thumb_label.setPixmap(QPixmap())

	def set_thumbnail(self, path):
		"""Legacy-Methode: synchrones Laden (nur noch für Abwärtskompatibilität).

		Bevorzugt set_thumbnail_pixmap() verwenden, das asynchron
		vom ThumbnailLoadWorker beliefert wird.
		"""
		if path and os.path.exists(path):
			try:
				from PIL import Image, ImageOps
				from io import BytesIO
				img = Image.open(path)
				img = ImageOps.exif_transpose(img) or img
				img.thumbnail((320, 180))
				buf = BytesIO()
				img.save(buf, format="PNG")
				buf.seek(0)
				pix = QPixmap()
				pix.loadFromData(buf.read())
				self.thumb_label.setPixmap(pix)
				return
			except Exception:
				pix = QPixmap(path)
				if not pix.isNull():
					self.thumb_label.setPixmap(
						pix.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio))
					return
		# Kein Thumbnail verfügbar – Platzhalter zurücksetzen
		self.thumb_label.setText("Vorschau")
		self.thumb_label.setPixmap(QPixmap())

	def set_thumbnail_pixmap(self, pix):
		"""Setzt ein fertig geladenes QPixmap als Vorschau.

		Wird vom ThumbnailLoadWorker (Hintergrund-Thread) über
		ein Signal aufgerufen – kein Dateizugriff im GUI-Thread.
		"""
		if pix is not None and not pix.isNull():
			self.thumb_label.setPixmap(pix)
		else:
			self.thumb_label.setText("Vorschau")
			self.thumb_label.setPixmap(QPixmap())

	def set_thumbnail_from_bytes(self, data):
		"""Erstellt ein QPixmap aus PNG-Bytes und setzt es als Vorschau.

		Wird vom ThumbnailLoadWorker über Signals aufgerufen.
		Das QPixmap wird hier im GUI-Thread erstellt (erlaubt),
		die Bildverarbeitung (PIL/OpenCV) erfolgt im Worker-Thread.
		"""
		from PyQt6.QtGui import QPixmap
		if data is None:
			self.thumb_label.setText("Vorschau")
			self.thumb_label.setPixmap(QPixmap())
			return

		pix = QPixmap()
		if pix.loadFromData(data):
			self.thumb_label.setPixmap(pix)
		else:
			self.thumb_label.setText("Vorschau")
			self.thumb_label.setPixmap(QPixmap())
