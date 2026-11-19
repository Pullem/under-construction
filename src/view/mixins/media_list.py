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
				self._set_scaled_pixmap(pix)
				return
			except Exception:
				pix = QPixmap(path)
				if not pix.isNull():
					self._set_scaled_pixmap(pix)
					return
		# Kein Thumbnail verfügbar – Platzhalter zurücksetzen
		self.thumb_label.setText("Vorschau")
		self.thumb_label.setPixmap(QPixmap())

	def _set_scaled_pixmap(self, pix):
		"""Skaliert ein QPixmap auf die Vorschau-Label-Größe und setzt es.

		Nutzt KeepAspectRatio, damit das Bild das Vorschaufenster so weit
		wie möglich ausfüllt, ohne verzerrt zu werden.
		"""
		if pix is None or pix.isNull():
			self.thumb_label.setText("Vorschau")
			self.thumb_label.setPixmap(QPixmap())
			return
		scaled = pix.scaled(
			self.thumb_label.size(),
			Qt.AspectRatioMode.KeepAspectRatio,
			Qt.TransformationMode.SmoothTransformation,
		)
		self.thumb_label.setPixmap(scaled)

	def set_thumbnail_pixmap(self, pix):
		"""Setzt ein fertig geladenes QPixmap als Vorschau.

		Wird vom ThumbnailLoadWorker (Hintergrund-Thread) über
		ein Signal aufgerufen – kein Dateizugriff im GUI-Thread.
		"""
		self._set_scaled_pixmap(pix)

	def set_thumbnail_from_bytes(self, data):
		"""Erstellt ein QPixmap aus PNG-Bytes und setzt es als Vorschau.

		Wird vom ThumbnailLoadWorker über Signals aufgerufen.
		Das QPixmap wird hier im GUI-Thread erstellt (erlaubt),
		die Bildverarbeitung (PIL/OpenCV) erfolgt im Worker-Thread.
		"""
		if data is None:
			self.thumb_label.setText("Vorschau")
			self.thumb_label.setPixmap(QPixmap())
			return

		pix = QPixmap()
		if pix.loadFromData(data):
			self._set_scaled_pixmap(pix)
		else:
			self.thumb_label.setText("Vorschau")
			self.thumb_label.setPixmap(QPixmap())
