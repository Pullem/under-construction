import os
from io import BytesIO

import numpy as np
import pyqtgraph as pg
from PIL import Image, ImageOps

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QSplitter, QFileDialog, QMessageBox, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPixmap


class ImageEnhanceWidget(QWidget):
    _PREVIEW_MAX_W = 600
    _PREVIEW_MAX_H = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_path = None
        self._preview_arr = None
        self._full_arr = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._update_preview)
        self._curves = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Top: side-by-side previews + waveform in the middle
        self._top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._processed_view = QLabel("Prozessiert")
        self._processed_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._processed_view.setStyleSheet("border: 1px solid #444; background: #111; color: #666; font-size: 11pt;")
        self._original_view = QLabel("Original")
        self._original_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._original_view.setStyleSheet("border: 1px solid #444; background: #111; color: #666; font-size: 11pt;")

        wf_panel = QWidget()
        wf_lay = QVBoxLayout(wf_panel)
        wf_lay.setContentsMargins(0, 0, 0, 0)
        wf_lay.setSpacing(4)

        wf_controls = QHBoxLayout()
        wf_controls.setSpacing(6)
        self._wf_all = QCheckBox("Alle Zeilen überlagern")
        self._wf_all.setChecked(True)
        self._wf_all.toggled.connect(self._on_wf_mode)
        wf_controls.addWidget(self._wf_all)
        wf_controls.addSpacing(8)
        wf_controls.addWidget(QLabel("Zeile:"))
        self._wf_line = QSpinBox()
        self._wf_line.setRange(0, 0)
        self._wf_line.setEnabled(False)
        self._wf_line.valueChanged.connect(self._on_wf_line)
        wf_controls.addWidget(self._wf_line)
        self._wf_line_val = QLabel("0")
        self._wf_line_val.setFixedWidth(50)
        wf_controls.addWidget(self._wf_line_val)
        self._wf_density = QCheckBox("Dichte-Hintergrund")
        self._wf_density.setChecked(True)
        self._wf_density.toggled.connect(self._on_wf_mode)
        wf_controls.addWidget(self._wf_density)
        wf_controls.addStretch()
        wf_lay.addLayout(wf_controls)

        self._wf_plot = pg.PlotWidget()
        self._wf_plot.setBackground('#111111')
        self._wf_plot.setLabel('left', 'Luma', color='#aaa', fontsize=9)
        self._wf_plot.setLabel('bottom', 'Spalte', color='#aaa', fontsize=9)
        self._wf_plot.setTitle('Luminanz-Waveform', color='#ccc', size='10pt')
        self._wf_plot.showGrid(x=False, y=True, alpha=0.15)
        self._wf_plot.setXRange(0, 1, padding=0)
        self._wf_plot.setYRange(0, 1, padding=0)
        self._wf_plot.getAxis('bottom').setPen(pg.mkPen('#444'))
        self._wf_plot.getAxis('left').setPen(pg.mkPen('#444'))
        self._wf_plot.getAxis('bottom').setTextPen(pg.mkPen('#aaa'))
        self._wf_plot.getAxis('left').setTextPen(pg.mkPen('#aaa'))
        self._wf_img = pg.ImageItem(axisOrder='row-major')
        self._wf_img.setColorMap(pg.colormap.getFromMatplotlib('hot'))
        self._wf_plot.addItem(self._wf_img)
        self._wf_curve = pg.PlotCurveItem(pen=pg.mkPen('#00ff88', width=1.5))
        self._wf_curve.setVisible(False)
        self._wf_plot.addItem(self._wf_curve)
        wf_lay.addWidget(self._wf_plot, 1)

        self._top_splitter.addWidget(self._processed_view)
        self._top_splitter.addWidget(wf_panel)
        self._top_splitter.addWidget(self._original_view)
        self._top_splitter.setStretchFactor(0, 1)
        self._top_splitter.setStretchFactor(1, 1)
        self._top_splitter.setStretchFactor(2, 1)
        self._top_splitter.setSizes([600, 600, 600])
        layout.addWidget(self._top_splitter, 3)

        # Bottom: controls + histogram
        bottom = QWidget()
        blay = QHBoxLayout(bottom)
        blay.setContentsMargins(0, 4, 0, 0)

        ctrl = QWidget()
        clay = QVBoxLayout(ctrl)

        self._s_lift = QSlider(Qt.Orientation.Horizontal)
        self._v_lift = QLabel("0.00")
        self._add_row(clay, "Shadows Lift", self._s_lift, self._v_lift, 0, 100, 0, lambda v: f"{v/100:.2f}")

        self._s_gamma = QSlider(Qt.Orientation.Horizontal)
        self._v_gamma = QLabel("1.00")
        self._add_row(clay, "Gamma Offset", self._s_gamma, self._v_gamma, 10, 500, 100, lambda v: f"{v/100:.2f}")

        self._s_exp = QSlider(Qt.Orientation.Horizontal)
        self._v_exp = QLabel("0.0")
        self._add_row(clay, "Exposure (EV)", self._s_exp, self._v_exp, -200, 200, 0, lambda v: f"{v/100:.1f}")

        self._s_black = QSlider(Qt.Orientation.Horizontal)
        self._v_black = QLabel("0.000")
        self._add_row(clay, "Black Level", self._s_black, self._v_black, 0, 300, 0, lambda v: f"{v/1000:.3f}")

        clay.addStretch()

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._reset_params)
        btn_row.addWidget(btn_reset)
        btn_export = QPushButton("Export...")
        btn_export.clicked.connect(self._export)
        btn_row.addWidget(btn_export)
        clay.addLayout(btn_row)

        blay.addWidget(ctrl, 1)

        self._hist_plot = pg.PlotWidget()
        self._hist_plot.setBackground('#111111')
        self._hist_plot.setMinimumWidth(300)
        self._hist_plot.setLabel('left', 'Count', color='#aaa', fontsize=9)
        self._hist_plot.setLabel('bottom', 'Pixel Value', color='#aaa', fontsize=9)
        self._hist_plot.setTitle('R / G / B / Luma', color='#ccc', size='10pt')
        self._hist_plot.showGrid(x=False, y=True, alpha=0.15)
        self._hist_plot.setXRange(0, 1, padding=0)
        self._hist_plot.getAxis('bottom').setPen(pg.mkPen('#444'))
        self._hist_plot.getAxis('left').setPen(pg.mkPen('#444'))
        self._hist_plot.getAxis('bottom').setTextPen(pg.mkPen('#aaa'))
        self._hist_plot.getAxis('left').setTextPen(pg.mkPen('#aaa'))

        blay.addWidget(self._hist_plot, 1)

        layout.addWidget(bottom, 2)

        for s in (self._s_lift, self._s_gamma, self._s_exp, self._s_black):
            s.valueChanged.connect(lambda: self._debounce.start(50))

    def _add_row(self, parent, name, slider, val_label, lo, hi, default, fmt):
        row = QHBoxLayout()
        lbl = QLabel(f"{name}:")
        lbl.setFixedWidth(140)
        row.addWidget(lbl)
        slider.setRange(lo, hi)
        slider.setValue(default)
        row.addWidget(slider, 1)
        val_label.setText(fmt(default))
        val_label.setFixedWidth(55)
        slider.valueChanged.connect(lambda v, f=fmt, l=val_label: l.setText(f(v)))
        row.addWidget(val_label)
        parent.addLayout(row)

    # ── public API ──────────────────────────────────────────

    def load_image(self, path):
        if not path or not os.path.exists(path):
            return
        self._image_path = path
        try:
            pil = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
            arr = np.array(pil, dtype=np.float32) / 255.0
            self._full_arr = arr

            w, h = pil.size
            scale = min(self._PREVIEW_MAX_W / w, self._PREVIEW_MAX_H / h, 1.0)
            if scale < 1.0:
                pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            self._preview_arr = np.array(pil, dtype=np.float32) / 255.0

            h = self._preview_arr.shape[0]
            self._wf_line.blockSignals(True)
            self._wf_line.setRange(0, max(h - 1, 0))
            self._wf_line.setValue(0)
            self._wf_line.blockSignals(False)
            self._wf_line_val.setText("0")
            self._wf_all.setChecked(True)

            self._show_pixmap(self._original_view, self._preview_arr)
            self._update_preview()
        except Exception as e:
            print(f"ImageEnhanceWidget.load_image: {e}")

    # ── processing pipeline ─────────────────────────────────

    def _process(self, arr):
        img = arr.copy()
        black = self._s_black.value() / 1000.0
        lift = self._s_lift.value() / 100.0
        gamma = self._s_gamma.value() / 100.0
        ev = self._s_exp.value() / 100.0

        if black != 0:
            img += black
        if lift != 0:
            img += lift * (1.0 - img) ** 2
        if gamma != 1.0:
            img = np.power(np.maximum(img, 0), 1.0 / gamma)
        if ev != 0:
            img *= 2.0 ** ev

        return np.clip(img, 0, 1)

    def _update_preview(self):
        if self._preview_arr is None:
            return
        processed = self._process(self._preview_arr)
        row = self._wf_line.value() if not self._wf_all.isChecked() else None
        self._show_pixmap(self._processed_view, processed, line_row=row)
        self._render_histogram(processed)
        self._render_waveform(processed)

    # ── display helpers ─────────────────────────────────────

    def _show_pixmap(self, label, arr_f32, line_row=None):
        data = (arr_f32 * 255).astype(np.uint8)
        h, w = data.shape[:2]
        if line_row is not None and h > 0:
            y = min(max(line_row, 0), h - 1)
            for dy in (-1, 0, 1):
                yy = y + dy
                if 0 <= yy < h:
                    data[yy, :, 0] = 0
                    data[yy, :, 1] = 255
                    data[yy, :, 2] = 136
        bio = BytesIO()
        Image.fromarray(data, 'RGB').save(bio, format='PNG')
        bio.seek(0)
        pix = QPixmap()
        pix.loadFromData(bio.read())
        label.setPixmap(pix)

    def _render_histogram(self, arr):
        bins = np.linspace(0, 1, 257)
        colors = {'r': '#ff4444', 'g': '#44ff44', 'b': '#4488ff'}
        for i, label in enumerate(('r', 'g', 'b')):
            h, _ = np.histogram(arr[:, :, i], bins=bins)
            if label not in self._curves:
                self._curves[label] = self._hist_plot.plot(bins[:-1], h, pen=pg.mkPen(colors[label], width=1.2))
            else:
                self._curves[label].setData(bins[:-1], h)

        luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        hl, _ = np.histogram(luma, bins=bins)
        if 'luma' not in self._curves:
            self._curves['luma'] = self._hist_plot.plot(bins[:-1], hl, pen=pg.mkPen('#aaaaaa', width=1, style=Qt.PenStyle.DashLine))
        else:
            self._curves['luma'].setData(bins[:-1], hl)

    def _render_waveform(self, arr):
        NB = 256
        PAD = 2
        luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        h, w = luma.shape
        lq = (np.clip(luma, 0, 1) * (NB - 1)).astype(np.int32)
        xs = np.arange(w)
        flat = (lq * w + xs).ravel()
        acc = np.bincount(flat, minlength=NB * w).reshape(NB, w).astype(np.float32)

        if self._wf_all.isChecked():
            self._wf_curve.setVisible(False)
            self._show_density(acc, w, NB, PAD, dim=False)
        else:
            y = min(max(self._wf_line.value(), 0), h - 1)
            self._wf_curve.setData(xs, luma[y])
            self._wf_curve.setVisible(True)
            if self._wf_density.isChecked():
                self._show_density(acc, w, NB, PAD, dim=True)
            else:
                self._wf_img.setVisible(False)
        self._wf_plot.setXRange(0, w, padding=0)
        self._wf_plot.setYRange(0, 1, padding=0)

    def _show_density(self, acc, w, NB, PAD, dim):
        acc = np.pad(acc, ((PAD, PAD), (0, 0)), mode='edge')
        top = max(float(acc.max()), 1.0)
        if dim:
            top *= 2.0
        self._wf_img.setVisible(True)
        self._wf_img.setImage(acc, autoLevels=False)
        self._wf_img.setLevels([0.0, top])
        self._wf_img.setRect(QRectF(0, 0, w, (NB + PAD - 1) / (NB - 1)))

    def _on_wf_mode(self):
        self._wf_line.setEnabled(not self._wf_all.isChecked())
        self._wf_density.setEnabled(not self._wf_all.isChecked())
        self._debounce.start(50)

    def _on_wf_line(self, v):
        self._wf_line_val.setText(str(v))
        self._debounce.start(50)

    # ── actions ─────────────────────────────────────────────

    def _reset_params(self):
        for s in (self._s_lift, self._s_gamma, self._s_exp, self._s_black):
            s.setValue(s.minimum() if s is self._s_lift else
                       s.minimum() if s is self._s_black else
                       100 if s is self._s_gamma else 0)

    def _export(self):
        if self._full_arr is None:
            QMessageBox.warning(self, "Kein Bild", "Bitte zuerst ein Bild laden.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", "PNG (*.png);;JPEG (*.jpg)")
        if not path:
            return
        proc = self._process(self._full_arr)
        Image.fromarray((proc * 255).astype(np.uint8), 'RGB').save(path)
        QMessageBox.information(self, "Export", f"Gespeichert:\n{path}")


class ImageEnhanceWindow(QWidget):
    """Standalone, movable window wrapping ImageEnhanceWidget."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle("Histogramm / Gamma")
        self.resize(1920, 800)
        self._enhance = ImageEnhanceWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._enhance)

    def load_image(self, path):
        self._enhance.load_image(path)

    def show_image(self, path):
        self.load_image(path)
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        self.hide()
        event.accept()
