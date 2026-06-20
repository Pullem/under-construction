from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PyQt6.QtGui import QPixmap, QColor, QIcon


class MetadataTabMixin:
	def create_color_icon(self, hex_color):
		pixmap = QPixmap(12, 12)
		pixmap.fill(QColor(hex_color))
		return QIcon(pixmap)

	def display_metadata(self, metadata_dict):
		self.tabs.clear()

		colors = {
			"General": "#4FC3F7", "Video": "#29B6F6", "Audio": "#66BB6A",
			"EXIF Deep Dive": "#FF7043", "Other": "#9E9E9E"
		}

		for i, (category, params) in enumerate(metadata_dict.items()):
			if not isinstance(params, dict):
				continue

			table = QTableWidget(len(params), 2)
			table.setHorizontalHeaderLabels(["Parameter", "Wert"])
			table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

			table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
			table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

			for row, (key, value) in enumerate(params.items()):
				table.setItem(row, 0, QTableWidgetItem(str(key)))
				table.setItem(row, 1, QTableWidgetItem(str(value)))

			color_hex = colors.get(category, colors["Other"])
			self.tabs.addTab(table, category)
			self.tabs.setTabIcon(i, self.create_color_icon(color_hex))
			self.tabs.tabBar().setTabTextColor(i, QColor(color_hex))

	def get_active_tab_name(self):
		idx = self.tabs.currentIndex()
		return self.tabs.tabText(idx) if idx != -1 else None

	def set_active_tab_by_name(self, name):
		if not name:
			return
		for i in range(self.tabs.count()):
			if self.tabs.tabText(i) == name:
				self.tabs.setCurrentIndex(i)
				return
		self.tabs.setCurrentIndex(0)
