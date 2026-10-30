"""Flache Navigations-Tabbar (horizontale Schrift, Akzent-Balken)."""

from PyQt6.QtWidgets import QTabBar, QStyle, QStyleOptionTab
from PyQt6.QtCore import QSize, QRect, Qt
from PyQt6.QtGui import QPainter, QColor


# ---------------------------------------------------------
# CUSTOM TAB BAR (flaches Design, horizontale Schrift)
# ---------------------------------------------------------
class FlatTabBar(QTabBar):
	# Farbtokens der Navigation (dunkles Design)
	_BG = QColor("#1a1a1a")
	_BG_HOVER = QColor("#242424")
	_BG_SELECTED = QColor("#252526")
	_TEXT = QColor("#9a9a9a")
	_TEXT_HOVER = QColor("#dcdcdc")
	_TEXT_SELECTED = QColor("#ffffff")
	_ACCENT = QColor("#2d7dd2")
	_SEPARATOR = QColor("#2a2a2a")

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setDrawBase(False)
		self.setExpanding(True)
		self.setMouseTracking(True)
		self._hover_index = -1

	def tabSizeHint(self, index):
		s = super().tabSizeHint(index)
		return QSize(max(s.width() + 30, 180), 40)

	# Hover-Zustand nur visuell verfolgen (keine Funktionsänderung)
	def mouseMoveEvent(self, event):
		super().mouseMoveEvent(event)
		idx = self.tabAt(event.position().toPoint())
		if idx != self._hover_index:
			self._hover_index = idx
			self.update()

	def leaveEvent(self, event):
		self._hover_index = -1
		super().leaveEvent(event)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)

		for idx in range(self.count()):
			opt = QStyleOptionTab()
			self.initStyleOption(opt, idx)
			rect = opt.rect
			selected = bool(opt.state & QStyle.StateFlag.State_Selected)
			hovered = (idx == self._hover_index and not selected)

			# Hintergrund je nach Zustand
			if selected:
				bg = self._BG_SELECTED
			elif hovered:
				bg = self._BG_HOVER
			else:
				bg = self._BG
			painter.save()
			painter.setPen(Qt.PenStyle.NoPen)
			painter.setBrush(bg)
			painter.drawRect(rect)

			# Feine Trennlinie zwischen den Einträgen
			painter.setPen(self._SEPARATOR)
			painter.drawLine(rect.bottomLeft(), rect.bottomRight())

			# Akzent-Balken links für den aktiven Eintrag
			if selected:
				painter.setPen(Qt.PenStyle.NoPen)
				painter.setBrush(self._ACCENT)
				painter.drawRoundedRect(
					QRect(rect.left() + 1, rect.top() + 8, 3, max(rect.height() - 16, 4)),
					1.5, 1.5)
			painter.restore()

			# Typografie: aktiver Eintrag fett und hell
			font = painter.font()
			font.setBold(selected)
			painter.setFont(font)
			if selected:
				painter.setPen(self._TEXT_SELECTED)
			elif hovered:
				painter.setPen(self._TEXT_HOVER)
			else:
				painter.setPen(self._TEXT)
			painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.tabText(idx))
			font.setBold(False)
			painter.setFont(font)
