from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
import os

class FileListView(QWidget):
    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Datei", "Größe", "Hash"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        self.btn_reload = QPushButton("Reload")
        self.btn_reload.clicked.connect(self.reload)
        layout.addWidget(self.btn_reload)

    def reload(self):
        # Placeholder: Presenter should supply real data. Keep empty table.
        self.table.setRowCount(0)

    def set_items(self, items):
        """Populate the table with items as returned by MediaRepository.list_media.

        items: iterable of tuples (id, file_path, file_name, file_size, hash, created_at)
        """
        self.table.setRowCount(0)
        for row_idx, item in enumerate(items):
            _id, file_path, file_name, file_size, hashv, created_at = item
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(file_name))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(file_size)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(hashv or ""))
