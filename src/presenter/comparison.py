import json
from PyQt6.QtWidgets import QMenu

from ..compare_window import ComparisonWindow


class ComparisonMixin:
	def show_context_menu(self, position):
		item = self.view.file_list.itemAt(position)
		if not item:
			return

		menu = QMenu()
		add_action = menu.addAction(f"'{item.text()}' zum Vergleich hinzufügen")
		open_action = menu.addAction("Vergleichs-Fenster öffnen")
		clear_action = menu.addAction("Vergleichs-Liste leeren")

		action = menu.exec(self.view.file_list.mapToGlobal(position))

		if action == add_action:
			self.add_to_comparison(item.text())
		elif action == open_action:
			self.open_comparison_view()
		elif action == clear_action:
			self.comparison_data.clear()
			print("Vergleichsliste geleert.")

	def add_to_comparison(self, file_name):
		try:
			conn = self.model.get_connection()
			cur = conn.cursor(dictionary=True)
			cur.execute("SELECT metadata, exif_metadata FROM media_files WHERE file_name = ?", (file_name,))
			row = cur.fetchone()
			conn.close()

			if row:
				data = json.loads(row['metadata'])
				if row['exif_metadata']:
					data["EXIF"] = json.loads(row['exif_metadata'])

				self.comparison_data[file_name] = data
				print(f"'{file_name}' vorgemerkt. ({len(self.comparison_data)} Dateien in Liste).")
		except Exception as e:
			print(f"Fehler beim Hinzufügen zum Vergleich: {e}")

	def open_comparison_view(self):
		if not self.comparison_data:
			print("Keine Dateien ausgewählt!")
			return

		self.comparison_window = ComparisonWindow(self.comparison_data)
		self.comparison_window.show()
