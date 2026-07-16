import os
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QSplitter, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
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
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Top: side-by-side previews
        self._top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._processed_view = QLabel("Prozessiert")
        self._processed_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._processed_view.setStyleSheet("border: 1px solid #444; background: #111; color: #666; font-size: 11pt;")
        self._original_view = QLabel("Original")
        self._original_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._original_view.setStyleSheet("border: 1px solid #444; background: #111; color: #666; font-size: 11pt;")
        self._top_splitter.addWidget(self._processed_view)
        self._top_splitter.addWidget(self._original_view)
        self._top_splitter.setStretchFactor(0, 1)
        self._top_splitter.setStretchFactor(1, 1)
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

        self._hist_view = QLabel("Histogramm")
        self._hist_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hist_view.setStyleSheet("border: 1px solid #444; background: #111; color: #666; font-size: 11pt;")
        self._hist_view.setMinimumWidth(300)
        blay.addWidget(self._hist_view, 1)

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
        self._show_pixmap(self._processed_view, processed)
        self._render_histogram(processed)

    # ── display helpers ─────────────────────────────────────

    def _show_pixmap(self, label, arr_f32):
        data = (arr_f32 * 255).astype(np.uint8)
        h, w = data.shape[:2]
        bio = BytesIO()
        Image.fromarray(data, 'RGB').save(bio, format='PNG')
        bio.seek(0)
        pix = QPixmap()
        pix.loadFromData(bio.read())
        label.setPixmap(pix)

    def _render_histogram(self, arr):
        fig, ax = plt.subplots(figsize=(4, 2.4), facecolor='#1e1e1e')
        ax.set_facecolor('#1e1e1e')
        bins = np.linspace(0, 1, 257)
        colors = ('red', 'green', 'blue')
        for i, c in enumerate(colors):
            h, _ = np.histogram(arr[:, :, i], bins=bins)
            ax.plot(bins[:-1], h, color=c, alpha=0.7, linewidth=0.7)
        luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        hl, _ = np.histogram(luma, bins=bins)
        ax.fill_between(bins[:-1], hl, alpha=0.15, color='#aaa')
        ax.tick_params(colors='#aaa', labelsize=7)
        ax.set_xlim(0, 1)
        for sp in ax.spines.values():
            sp.set_color('#444')
        ax.set_xlabel('Pixel Value', color='#aaa', fontsize=8)
        ax.set_ylabel('Count', color='#aaa', fontsize=8)
        ax.set_title('R / G / B / Luma', color='#ccc', fontsize=9)
        fig.tight_layout()
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        pix = QPixmap()
        pix.loadFromData(buf.read())
        self._hist_view.setPixmap(pix)

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
        self.resize(1280, 800)
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
