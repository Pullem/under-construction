"""Gemeinsame Widgets für Tabs (AspectFitLabel, AnalysisTabWidget)."""

from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter


class AspectFitLabel(QLabel):
	"""QLabel, das sein Pixmap seitenverhältnistreu in die Label-Größe
	einpasst und sich bei Resizes automatisch nachskaliert."""

	def __init__(self, text="", parent=None):
		super().__init__(text, parent)
		self._src = QPixmap()

	def setPixmap(self, pixmap):
		self._src = QPixmap(pixmap)
		self._fit()

	def clear(self):
		self._src = QPixmap()
		super().clear()

	def resizeEvent(self, event):
		super().resizeEvent(event)
		self._fit()

	def _fit(self):
		if self._src.isNull():
			return
		w, h = self.width(), self.height()
		if w <= 0 or h <= 0:
			return
		super().setPixmap(self._src.scaled(
			QSize(w, h), Qt.AspectRatioMode.KeepAspectRatio,
			Qt.TransformationMode.SmoothTransformation))


class AnalysisTabWidget(QWidget):
	"""pyqtgraph-basiertes Ergebnis-Panel für eine Bild-Analyse.

	Oben: Karten-Widget (GraphicsLayoutWidget) mit 1–2 Subplots
	(ImageItem + HistogramLUTItem als Farbskala). Unten: Verteilungs-Plot
	(PlotWidget, Vector-Text wie das Histogramm/Gamma-Fenster). Export der
	Panels als hochauflösende PNGs via pyqtgraph ImageExporter.
	"""

	EXPORT_MAP_WIDTH = 2700
	EXPORT_HIST_WIDTH = 2200

	def __init__(self, mode, parent=None):
		super().__init__(parent)
		self.mode = mode
		self._images = []
		self._luts = []
		self._plots = []
		self._cmaps = []

		self.map_widget = pg.GraphicsLayoutWidget()
		self.map_widget.setBackground("#111111")
		self.map_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
		self.map_widget.setMinimumSize(0, 0)

		if mode == "ela":
			self._add_subplot("hot", lock_aspect=True)
		elif mode == "copymove":
			self._add_subplot(None, lock_aspect=True)
		elif mode == "resample":
			self._add_subplot("coolwarm", lock_aspect=True)
			self._add_subplot("plasma", lock_aspect=False)
		elif mode == "jpeggrid":
			self._add_subplot("inferno", lock_aspect=False)
			self._add_subplot(None, lock_aspect=True)

		self.hist_widget = pg.PlotWidget()
		self.hist_widget.setBackground("#111111")
		self.hist_widget.showGrid(x=False, y=True, alpha=0.15)
		self.hist_widget.getAxis("bottom").setPen(pg.mkPen("#444"))
		self.hist_widget.getAxis("left").setPen(pg.mkPen("#444"))
		self.hist_widget.getAxis("bottom").setTextPen(pg.mkPen("#aaa"))
		self.hist_widget.getAxis("left").setTextPen(pg.mkPen("#aaa"))
		self.hist_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
		self.hist_widget.setMinimumSize(0, 0)
		self._hist_curve = self.hist_widget.plot([], [], pen=pg.mkPen("#0f0", width=1.2))
		self._hist_marker = pg.InfiniteLine(
			angle=90, pen=pg.mkPen("#ff9900", style=Qt.PenStyle.DashLine))
		self._hist_marker.setVisible(False)
		self.hist_widget.addItem(self._hist_marker)

		lay = QVBoxLayout(self)
		lay.setContentsMargins(2, 2, 2, 2)

		head = QHBoxLayout()
		self._fit_button = QPushButton("Bild einpassen")
		self._fit_button.clicked.connect(self._on_fit_view)
		head.addWidget(self._fit_button)
		head.addStretch()
		self._hist_toggle = None
		if mode == "copymove":
			self._hist_toggle = QPushButton("Vektor-Histogramm anzeigen")
			self._hist_toggle.setCheckable(True)
			self._hist_toggle.setEnabled(False)
			self._hist_toggle.toggled.connect(self._on_hist_toggle)
			head.addWidget(self._hist_toggle)
			self.hist_widget.hide()
		lay.addLayout(head)

		lay.addWidget(self.map_widget, 1)
		lay.addWidget(self.hist_widget, 1)

	# ---- Aufbau ----

	def _add_subplot(self, cmap_name, lock_aspect):
		col = len(self._images) * 2
		pi = self.map_widget.addPlot(row=0, col=col)
		vb = pi.getViewBox()
		vb.setAspectLocked(lock_aspect)
		vb.setBackgroundColor("#111111")
		vb.invertY(True)
		pi.hideButtons()
		pi.setMenuEnabled(False)
		for ax in ("left", "bottom", "right", "top"):
			pi.showAxis(ax, False)
		img = pg.ImageItem()
		img.setOpts(axisOrder="row-major")
		img.setAutoDownsample(True)
		pi.addItem(img)
		lut = None
		if cmap_name:
			lut = pg.HistogramLUTItem()
			lut.axis.setVisible(False)
			lut.setVisible(False)
			lut.setImageItem(img)
			self.map_widget.addItem(lut, row=0, col=col + 1)
		self._plots.append(pi)
		self._images.append(img)
		self._luts.append(lut)
		self._cmaps.append(cmap_name)

	# ---- Befüllung ----

	def show_result(self, data):
		if data is None:
			return
		handler = getattr(self, f"_show_{self.mode}", None)
		if handler:
			handler(data)

	def _set_image(self, index, data, vmin, vmax):
		img = self._images[index]
		img.setVisible(True)
		img.setImage(data, autoLevels=True)
		img.setLevels([vmin, vmax])
		lut = self._luts[index]
		if lut is not None:
			lut.gradient.setColorMap(pg.colormap.getFromMatplotlib(self._cmaps[index]))
			lut.setLevels(vmin, vmax)
			lut.setHistogramRange(vmin, vmax)
			lut.setVisible(True)
		self._set_plot_title(index, "")

	def _set_plot_title(self, index, text):
		self._plots[index].setTitle(text, color="#888", size="10pt") if text \
			else self._plots[index].setTitle("")

	def _set_placeholder(self, index, text):
		self._images[index].setVisible(False)
		if self._luts[index] is not None:
			self._luts[index].setVisible(False)
		self._set_plot_title(index, text)

	def _set_histogram(self, x, y, title, xlabel, ylabel, marker=None):
		self.hist_widget.setTitle(title, color="#ccc", size="10pt")
		self.hist_widget.setLabel("bottom", xlabel, color="#aaa", fontsize=9)
		self.hist_widget.setLabel("left", ylabel, color="#aaa", fontsize=9)
		self._hist_curve.setData(x, y)
		if marker is not None:
			self._hist_marker.setValue(marker)
			self._hist_marker.setVisible(True)
		else:
			self._hist_marker.setVisible(False)

	def _set_hist_placeholder(self, title="–"):
		self._hist_curve.setData([], [])
		self._hist_marker.setVisible(False)
		self.hist_widget.setTitle(title, color="#888", size="10pt")

	def _on_fit_view(self):
		for pi in self._plots:
			pi.getViewBox().autoRange()

	def _on_hist_toggle(self, checked):
		self.hist_widget.setVisible(checked)
		self._hist_toggle.setText(
			"Vektor-Histogramm verbergen" if checked else "Vektor-Histogramm anzeigen")

	def _show_ela(self, data):
		diff = data["diff"]
		vmax = float(max(np.percentile(diff.ravel(), 99.9), 1.0))
		self._set_image(0, diff, 0, vmax)
		self._set_plot_title(0, "ELA-Fehlermap")
		vals, edges = np.histogram(diff.ravel(), bins=256, range=(0, vmax))
		self._set_histogram(edges[:-1], vals, "ELA-Histogramm",
							"Fehler-Level", "Pixel")

	def _show_copymove(self, data):
		vis = data.get("vis")
		if vis is None:
			self._set_placeholder(0, "Keine konsistente Transformationsgruppe gefunden")
			self._set_hist_placeholder("Copy-Move: keine Histogramm-Analyse")
			if self._hist_toggle is not None:
				self._hist_toggle.setChecked(False)
				self._hist_toggle.setEnabled(False)
			return
		self._set_image(0, vis, 0, 255)
		self._set_plot_title(0, "Copy-Move-Regionen")
		shifts = data.get("shifts")
		if shifts is not None and len(shifts) > 0:
			norms = np.linalg.norm(shifts, axis=1)
			vals, edges = np.histogram(norms, bins=40)
			self._set_histogram(edges[:-1], vals, "Copy-Move-Shift-Vektoren",
								"Verschiebung (px)", "Anzahl Keypoint-Paare",
								marker=float(np.median(norms)))
			if self._hist_toggle is not None:
				self._hist_toggle.setEnabled(True)
		else:
			self._set_hist_placeholder("Copy-Move: keine Shift-Vektoren")
			if self._hist_toggle is not None:
				self._hist_toggle.setChecked(False)
				self._hist_toggle.setEnabled(False)

	def _show_resample(self, data):
		self._set_image(0, data["res"], -data["v_lim"], data["v_lim"])
		self._set_plot_title(0, "Resampling-Residual")
		noise_map = data["noise_map"]
		nm = np.nan_to_num(noise_map, nan=0.0)
		self._set_image(1, nm, 0.0, data["noise_vmax"])
		self._set_plot_title(1, "Rausch-Karte")
		valid = noise_map[~np.isnan(noise_map)]
		vals, edges = np.histogram(valid, bins=40)
		self._set_histogram(edges[:-1], vals, "Rausch-Verteilung über Bildblöcke",
							"Rauschniveau (Std-Abweichung)", "Anzahl Blöcke",
							marker=data.get("sigma_noise", 0.0))

	def _show_jpeggrid(self, data):
		block = data.get("block")
		if block is None or not block.size:
			self._set_placeholder(0, "Kein JPEG-Blockraster erkannt")
			self._set_placeholder(1, "–")
			self._set_hist_placeholder("Kein JPEG-Blockraster erkannt")
			return
		self._set_image(0, block, 0.0, data["block_vmax"])
		self._set_plot_title(0, "JPEG-Blockraster")
		overlay = data.get("overlay")
		alpha = data.get("alpha")
		if overlay is not None and alpha is not None:
			rgba = np.dstack([
				(np.clip(overlay, 0, 1) * 255).astype(np.uint8),
				(np.clip(alpha, 0, 1) * 255).astype(np.uint8)])
			self._set_image(1, rgba, 0, 255)
			self._set_plot_title(1, "Grid-Overlay")
		else:
			self._set_placeholder(1, "Kein Grid-Overlay")
		vals, edges = np.histogram(block.ravel(), bins=60)
		self._set_histogram(edges[:-1], vals, "Blockiness-Verteilung",
							"Blockiness", "Anzahl Zellen",
							marker=data.get("block_mean", 0.0))

	# ---- Export ----

	def export_analysis(self, stem, exports_dir):
		exports_dir = Path(exports_dir)
		exports_dir.mkdir(parents=True, exist_ok=True)
		if self.mode == "copymove":
			path = exports_dir / f"{stem}_copymove.png"
			self._export_widget(self.map_widget, path, self.EXPORT_MAP_WIDTH)
			return str(path), None
		errormap_path = exports_dir / f"{stem}_{self.mode}_errormap.png"
		hist_path = exports_dir / f"{stem}_{self.mode}_histogram.png"
		self._export_widget(self.map_widget, errormap_path, self.EXPORT_MAP_WIDTH)
		self._export_widget(self.hist_widget, hist_path, self.EXPORT_HIST_WIDTH)
		return str(errormap_path), str(hist_path)

	def _export_widget(self, widget, path, width):
		item = widget.plotItem if isinstance(widget, pg.PlotWidget) else widget.ci
		if widget.width() <= 0 or widget.height() <= 0:
			widget.resize(800, 400)
		exporter = ImageExporter(item)
		exporter.params["width"] = width
		exporter.export(str(path))