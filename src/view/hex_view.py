import math
from PyQt6.QtWidgets import QAbstractScrollArea, QWidget, QVBoxLayout, QHBoxLayout, \
    QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt, QFile, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics, QPen, QBrush


class HexViewWidget(QAbstractScrollArea):
    CHARS_PER_LINE = 16
    search_moved = pyqtSignal(int, int)  # index, total

    def __init__(self, parent=None):
        super().__init__(parent)
        self._font_size = 9
        self._apply_font()

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
        self._col_highlight = QColor("#665500")
        self._col_highlight_active = QColor("#886600")

        # Suche
        self._search_pattern = b""
        self._search_mode = "hex"  # "hex", "ascii", "text"
        self._search_results = []
        self._search_index = -1

    def _apply_font(self):
        font = QFont("Consolas", self._font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self._fm = QFontMetrics(font)
        self._line_height = self._fm.lineSpacing() + 2
        self._char_width = self._fm.horizontalAdvance("0")

    def set_font_size(self, size):
        self._font_size = max(6, min(24, size))
        self._apply_font()
        self._update_scrollbar()
        self.viewport().update()

    def set_file(self, path):
        self._file_path = path
        self._clear_search()
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

    # ---- Suche ----

    def search(self, pattern, mode):
        if not self._file or not self._file.isOpen() or not pattern:
            self._clear_search()
            return
        try:
            if mode == "hex":
                pattern_bytes = bytes.fromhex(pattern.replace(" ", "").replace("\\x", ""))
            elif mode == "ascii":
                pattern_bytes = pattern.encode("ascii", errors="ignore")
            else:  # text
                pattern_bytes = pattern.encode("utf-8")
        except Exception:
            self._clear_search()
            return

        self._search_pattern = pattern_bytes
        self._search_mode = mode
        self._search_results = []
        self._search_index = -1

        if not pattern_bytes:
            self.search_moved.emit(0, 0)
            self.viewport().update()
            return

        buf = self._read_all()
        pos = 0
        while True:
            pos = buf.find(pattern_bytes, pos)
            if pos == -1:
                break
            self._search_results.append(pos)
            pos += 1

        if self._search_results:
            self._search_index = 0
            self._show_match()
        self.search_moved.emit(self._search_index + 1, len(self._search_results))
        self.viewport().update()

    def search_next(self):
        if not self._search_results:
            return
        self._search_index = (self._search_index + 1) % len(self._search_results)
        self._show_match()
        self.search_moved.emit(self._search_index + 1, len(self._search_results))
        self.viewport().update()

    def search_prev(self):
        if not self._search_results:
            return
        self._search_index = (self._search_index - 1) % len(self._search_results)
        self._show_match()
        self.search_moved.emit(self._search_index + 1, len(self._search_results))
        self.viewport().update()

    def _show_match(self):
        if not self._search_results or self._search_index < 0:
            return
        offset = self._search_results[self._search_index]
        line = offset // self.CHARS_PER_LINE
        sb = self.verticalScrollBar()
        sb.setValue(line - self._visible_lines // 4)

    def _read_all(self):
        self._file.seek(0)
        return self._file.read(self._file_size)

    def _clear_search(self):
        self._search_pattern = b""
        self._search_results = []
        self._search_index = -1
        self.search_moved.emit(0, 0)

    # ---- Painting ----

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

            # Hervorhebung der Treffer-Zeile
            hl_rect = QBrush(QColor("#1a1a2e"))
            if self._search_results:
                active_off = self._search_results[self._search_index] if self._search_index >= 0 else -1
                active_line = active_off // self.CHARS_PER_LINE
                if active_line == line_no:
                    painter.fillRect(0, y - self._line_height + 2,
                                     self.viewport().width(), self._line_height,
                                     QColor("#1a1a3e"))

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

            # Suche-Highlight in Hex + ASCII
            if self._search_pattern and n > 0:
                full_offset = offset
                plen = len(self._search_pattern)
                for soff in range(n):
                    if soff + plen <= n and raw[soff:soff + plen] == self._search_pattern:
                        abs_off = full_offset + soff
                        is_active = self._search_results and self._search_index >= 0 and \
                            self._search_results[self._search_index] == abs_off
                        col = self._col_highlight_active if is_active else self._col_highlight
                        # Hex-Highlight
                        hextra = soff // 2
                        hex_x = x_hex_start + hextra * 5 * self._char_width
                        if soff % 2 == 0:
                            off_extra = 0
                        else:
                            hextra_old = hextra
                            hex_x = x_hex_start + hextra_old * 5 * self._char_width
                        # Einfachere Methode: zeichne einzelne Hex-Paare
                        for si in range(plen):
                            bi = soff + si
                            if bi >= n:
                                break
                            col_idx = bi
                            pair_idx = col_idx // 2
                            in_pair = col_idx % 2
                            bx = x_hex_start + pair_idx * 5 * self._char_width + in_pair * 2 * self._char_width
                            painter.setPen(col)
                            painter.drawText(int(bx), y, f"{raw[bi]:02x}")

                        # ASCII-Highlight
                        for si in range(plen):
                            bi = soff + si
                            if bi >= n:
                                break
                            ax = x_ascii_start + 2 * self._char_width + bi * self._char_width
                            painter.setPen(col)
                            ch = chr(raw[bi]) if 0x20 <= raw[bi] < 0x7f else "."
                            painter.drawText(int(ax), y, ch)

            # Normal-Hex (ohne Highlight) – nur zeichnen, wenn nicht bereits durch Highlight übermalt
            painter.setPen(self._col_hex)
            painter.drawText(x_hex_start, y, hex_str)

            # ASCII
            painter.setPen(self._col_ascii)
            painter.drawText(x_ascii_start, y, "│ " + "".join(ascii_parts))

        # Zeilen-Trennlinie
        painter.setPen(QColor("#333"))
        painter.drawLine(x_ascii_start - self._char_width * 2, event.rect().top(),
                         x_ascii_start - self._char_width * 2, event.rect().bottom())
