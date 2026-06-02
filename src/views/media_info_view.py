from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtCore import Qt, pyqtSignal
from colored_tabbar import ColoredTabBar
from overlay import LoadingOverlay

class MediaInfoDetailView(QWidget):
    start_import_requested = pyqtSignal()
    open_config_requested = pyqtSignal()
    scan_requested = pyqtSignal()
    search_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.label_header = QLabel("Keine Datei ausgewählt")
        layout.addWidget(self.label_header)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(ColoredTabBar(self._get_tab_color))
        layout.addWidget(self.tabs)

        self.category_colors = {
            "General": "#4A90E2",
            "Video":   "#D0021B",
            "Audio":   "#7ED321",
            "Text":    "#F5A623",
            "Other":   "#9B9B9B",
        }

        self.category_icons = {
            "General": QIcon(),
            "Video":   QIcon(),
            "Audio":   QIcon(),
            "Text":    QIcon(),
            "Other":   QIcon(),
        }

        self.overlay = LoadingOverlay(self)
        self.overlay.resize(self.size())
        self._tab_colors = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.resize(self.size())

    def clear(self):
        self.label_header.setText("Keine Datei ausgewählt")
        self.tabs.clear()
        self._tab_colors = []

    def set_data(self, file_info, categories):
        self.clear()
        if not file_info:
            return
        self.label_header.setText(f"<b>Datei:</b> {file_info['file_path']}")
        self._tab_colors = []

        track_counters = {}
        for category, attributes in categories.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Attribut", "Wert"])
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.setRowCount(len(attributes))
            for row_index, (attr, value) in enumerate(attributes):
                table.setItem(row_index, 0, QTableWidgetItem(attr))
                table.setItem(row_index, 1, QTableWidgetItem(value))
            tab_layout.addWidget(table)

            count = track_counters.get(category, 0) + 1
            track_counters[category] = count
            tab_title = category if category in ("General", "Other") else f"{category} #{count}"
            icon = self.category_icons.get(category, QIcon())
            self.tabs.addTab(tab, icon, tab_title)
            self._tab_colors.append(self.category_colors.get(category, "#666"))

        self.tabs.tabBar().update()

    def _get_tab_color(self, index):
        if 0 <= index < len(self._tab_colors):
            return self._tab_colors[index]
        return "#666"

    def apply_search(self, text):
        # einfache Suche: filtere alle Tabellen in allen Tabs
        text = (text or "").strip().lower()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            for child in tab.findChildren(QTableWidget):
                for r in range(child.rowCount()):
                    visible = False
                    for c in range(child.columnCount()):
                        item = child.item(r, c)
                        if item and text in item.text().lower():
                            visible = True
                            break
                    child.setRowHidden(r, not visible)
