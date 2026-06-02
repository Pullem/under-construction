from PyQt6.QtWidgets import QTabBar, QStyleOptionTab
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt, QRect

class ColoredTabBar(QTabBar):
    def __init__(self, get_color_callback, parent=None):
        super().__init__(parent)
        self.get_color_callback = get_color_callback
        self.setDrawBase(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for index in range(self.count()):
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            rect = option.rect
            color = self.get_color_callback(index)
            if isinstance(color, str):
                color = QColor(color)

            # Hintergrund
            painter.save()
            painter.setPen(Qt.GlobalColor.transparent)
            painter.setBrush(color)
            painter.drawRoundedRect(QRect(rect), 6, 6)
            painter.restore()

            # Rahmen
            painter.setPen(Qt.GlobalColor.black)
            painter.drawRoundedRect(QRect(rect), 6, 6)

            # Icon + Text
            painter.setPen(Qt.GlobalColor.white)
            icon = option.icon
            text = option.text

            if not icon.isNull():
                icon_rect = rect.adjusted(6, 6, -6, -6)
                icon_rect.setWidth(20)
                icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignVCenter)
                text_rect = rect.adjusted(32, 0, -6, 0)
            else:
                text_rect = rect.adjusted(8, 0, -6, 0)

            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
