import math
from PyQt6.QtWidgets import QAbstractScrollArea, QWidget, QVBoxLayout, QHBoxLayout, \
    QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt, QFile
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen


class HexViewWidget(QAbstractScrollArea):
    CHARS_PER_LINE = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self._fm = QFontMetrics(font)
        self._line_height = self._fm.lineSpacing() + 2
        self._char_width = self._fm.horizontalAdvance("0")

        self._file_path = None
        self._file = None
        self._file_size = 0
        self._total_lines = 0
        self._visible_lines = 0

        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self.verticalScrollBar().valueChanged.connect(self.viewport().update)

        # Farben
        self._col_offset = QColor("#888")
        self._col_hex = QColor("#88ddff")
        self._col_ascii = QColor("#88ff88")
        self._col_sep = QColor("#555")
        self._col_bg = QColor("#111")

    def set_file(self, path):
        self._file_path = path
        f = QFile(path)
        if not f.exists():
            return
        if self._file and self._file.isOpen():
            self._file.close()
        self._file = f
        if not self._file.open(QFile.OpenModeFlag.ReadOnly):
            self._file = None
            return
        self._file_size = self._file.size()
        self._total_lines = max(1, math.ceil(self._file_size / self.CHARS_PER_LINE))
        self.verticalScrollBar().setValue(0)
        self._update_scrollbar()
        self.viewport().update()

    def _update_scrollbar(self):
        vh = self.viewport().height()
        self._visible_lines = max(1, vh // self._line_height)
        max_scroll = max(0, self._total_lines - self._visible_lines)
        self.verticalScrollBar().setRange(0, max_scroll)
        self.verticalScrollBar().setPageStep(self._visible_lines)
        self.verticalScrollBar().setSingleStep(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scrollbar()

    def goto_offset(self, offset_str):
        try:
            offset = int(offset_str.strip(), 16)
        except ValueError:
            QMessageBox.warning(self, "Fehler", "Ungültiger Hex-Offset")
            return
        if offset < 0 or offset >= self._file_size:
            QMessageBox.warning(self, "Fehler", "Offset außerhalb der Datei")
            return
        line = offset // self.CHARS_PER_LINE
        sb = self.verticalScrollBar()
        sb.setValue(line)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), self._col_bg)

        if not self._file or not self._file.isOpen():
            painter.setPen(QColor("#666"))
            painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Datei geladen")
            return

        scroll_val = self.verticalScrollBar().value()
        first_line = scroll_val
        last_line = min(self._total_lines, first_line + self._visible_lines + 1)

        x_offset = 2
        x_hex_start = x_offset + 9 * self._char_width
        x_ascii_start = x_hex_start + 50 * self._char_width
        y_base = self._line_height

        for line_no in range(first_line, last_line):
            y = y_base + (line_no - first_line) * self._line_height
            offset = line_no * self.CHARS_PER_LINE

            # Offset
            painter.setPen(self._col_offset)
            painter.drawText(x_offset, y, f"{offset:08x}")

            # Hex
            painter.setPen(self._col_sep)
            painter.drawText(x_hex_start - self._char_width, y, " ")

            self._file.seek(offset)
            raw = self._file.read(self.CHARS_PER_LINE)
            n = len(raw)

            hex_parts = []
            ascii_parts = []
            for i in range(self.CHARS_PER_LINE):
                if i < n:
                    b = raw[i]
                    hex_parts.append(f"{b:02x}")
                    ascii_parts.append(chr(b) if 0x20 <= b < 0x7f else ".")
                else:
                    hex_parts.append("  ")
                    ascii_parts.append(" ")

            # Hex-String mit Extra-Space nach 8 Bytes
            hex_str = ""
            for i in range(0, self.CHARS_PER_LINE, 2):
                if i > 0 and i % 8 == 0:
                    hex_str += " "
                hex_str += hex_parts[i] + hex_parts[i + 1] + " "

            painter.setPen(self._col_hex)
            painter.drawText(x_hex_start, y, hex_str)

            # ASCII
            painter.setPen(self._col_ascii)
            painter.drawText(x_ascii_start, y, "│ " + "".join(ascii_parts))

        # Zeilen-Trennlinie zw. Offset/Hex und ASCII
        painter.setPen(QColor("#333"))
        painter.drawLine(x_ascii_start - self._char_width * 2, event.rect().top(),
                         x_ascii_start - self._char_width * 2, event.rect().bottom())
