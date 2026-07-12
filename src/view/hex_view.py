import math
from PyQt6.QtWidgets import QAbstractScrollArea, QMessageBox
from PyQt6.QtCore import Qt, QFile, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QFontMetrics


class HexViewWidget(QAbstractScrollArea):
    CHARS_PER_LINE = 16
    search_moved = pyqtSignal(int, int)

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

        self._col_offset = QColor("#888")
        self._col_hex = QColor("#88ddff")
        self._col_ascii = QColor("#88ff88")
        self._col_sep = QColor("#555")
        self._col_bg = QColor("#111")
        self._col_header = QColor("#666")
        self._col_highlight = QColor("#665500")
        self._col_highlight_active = QColor("#886600")

        self._search_pattern = b""
        self._search_mode = "hex"
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
        self.verticalScrollBar().setValue(line)

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
            else:
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

        cw = self._char_width
        x_offset = 2
        x_hex_start = x_offset + 9 * cw
        hex_stride = 3 * cw                     # "XX " per byte
        x_ascii_start = x_hex_start + self.CHARS_PER_LINE * 3 * cw + 1 * cw + 2 * cw  # hex + gap + "│ "
        ascii_stride = 2 * cw                   # char + space

        scroll_val = self.verticalScrollBar().value()
        first_line = scroll_val
        last_line = min(self._total_lines, first_line + self._visible_lines + 1)
        y_base = self._line_height

        # Header: Spalten-Indizes 00–0F
        painter.setPen(self._col_header)
        header_parts = []
        for i in range(self.CHARS_PER_LINE):
            if i == 8:
                header_parts.append(" ")
            header_parts.append(f"{i:02x}")
        header_str = " ".join(header_parts)
        painter.drawText(x_hex_start, y_base, header_str)
        line_y_offset = 1  # header uses 1 line

        for line_no in range(first_line, last_line):
            y = y_base + (line_no - first_line + line_y_offset) * self._line_height
            offset = line_no * self.CHARS_PER_LINE

            # Treffer-Zeilen-Hintergrund
            if self._search_results and self._search_index >= 0:
                active_off = self._search_results[self._search_index]
                if active_off // self.CHARS_PER_LINE == line_no:
                    painter.fillRect(0, y - self._line_height + 2,
                                     self.viewport().width(), self._line_height,
                                     QColor("#1a1a3e"))

            # Offset
            painter.setPen(self._col_offset)
            painter.drawText(x_offset, y, f"{offset:08x}")

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
            hex_parts_display = []
            for i in range(self.CHARS_PER_LINE):
                if i == 8:
                    hex_parts_display.append(" ")
                hex_parts_display.append(hex_parts[i])
            hex_str = " ".join(hex_parts_display)

            # Hex mit Suche-Highlight
            if self._search_pattern and n > 0:
                plen = len(self._search_pattern)
                for soff in range(n - plen + 1):
                    if raw[soff:soff + plen] != self._search_pattern:
                        continue
                    abs_off = offset + soff
                    is_active = self._search_index >= 0 and self._search_results[self._search_index] == abs_off
                    hl_col = self._col_highlight_active if is_active else self._col_highlight
                    for si in range(plen):
                        bi = soff + si
                        if bi >= n:
                            break
                        bx = x_hex_start + bi * 3 * cw
                        painter.setPen(hl_col)
                        painter.drawText(int(bx), y, f"{raw[bi]:02x}")
                        ax = x_ascii_start + bi * 2 * cw
                        painter.drawText(int(ax), y, chr(raw[bi]) if 0x20 <= raw[bi] < 0x7f else ".")

            # Normal-Hex (wird von Hervorhebung übermalt)
            painter.setPen(self._col_hex)
            painter.drawText(x_hex_start, y, hex_str)

            # ASCII
            painter.setPen(self._col_ascii)
            painter.drawText(x_ascii_start, y, "│ " + " ".join(ascii_parts))

        # Trennlinie
        painter.setPen(QColor("#333"))
        sep_x = x_ascii_start - 2 * cw
        painter.drawLine(sep_x, event.rect().top(), sep_x, event.rect().bottom())
