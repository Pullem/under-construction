import os
from io import BytesIO

import numpy as np
import pyqtgraph as pg
from PIL import Image, ImageOps

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QSplitter, QFileDialog, QMessageBox, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import QPixmap


class ToneCurveEditor(pg.PlotWidget):
    """Interaktive Tone-Curve (Kennlinie) mit ziehbaren Kontrollpunkten."""

    changed = pyqtSignal()
    feedback = pyqtSignal(str)

    _HANDLE_TOL = 14.0
    _DRAG_TOL = 5.0
    _EDGE_GUARD = 0.05
    _DUP_GUARD = 0.02

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground('#111111')
        self.setLabel('left', 'Ausgang', color='#aaa', fontsize=9)
        self.setLabel('bottom', 'Eingang', color='#aaa', fontsize=9)
        self.setTitle('Tone-Curve', color='#ccc', size='10pt')
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setXRange(0, 1, padding=0)
        self.setYRange(0, 1, padding=0)
        self.setMouseEnabled(x=False, y=False)
        for a in ('bottom', 'left'):
            self.getAxis(a).setPen(pg.mkPen('#444'))
            self.getAxis(a).setTextPen(pg.mkPen('#aaa'))

        self._ref = pg.PlotCurveItem([0, 1], [0, 1], pen=pg.mkPen('#555', width=1, style=Qt.PenStyle.DashLine))
        self.addItem(self._ref)

        self._line = pg.PlotCurveItem(pen=pg.mkPen('#00ff88', width=2))
        self.addItem(self._line)

        self._handles = pg.ScatterPlotItem(size=15, brush=pg.mkBrush('#00ff88'), pen=pg.mkPen('#000000', width=1))
        self._handles.setZValue(10)
        self.addItem(self._handles)

        self.plotItem.hideButtons()
        self.plotItem.vb.setMenuEnabled(False)
        self.viewport().setMouseTracking(True)
        self._brush_default = pg.mkBrush('#00ff88')
        self._brush_hover = pg.mkBrush('#aaffcc')
        self._hover_idx = -1

        self._pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)]
        self._drag = -1
        self._press_idx = -1
        self._press_pos = None
        self._redraw()

    def _redraw(self):
        xs = [p[0] for p in self._pts]
        ys = [p[1] for p in self._pts]
        self._line.setData(xs, ys)
        self._handles.setData(pos=[(x, y) for x, y in zip(xs, ys)])
        self._apply_hover(self._drag if self._drag >= 0 else -1)

    def curve(self):
        xs = sorted(p[0] for p in self._pts)
        ys = [p[1] for p in sorted(self._pts, key=lambda p: p[0])]
        return np.array(xs, dtype=np.float64), np.array(ys, dtype=np.float64)

    def set_points(self, pts):
        self._pts = [(float(x), float(y)) for x, y in pts]
        self._pts.sort(key=lambda p: p[0])
        self._redraw()
        self.changed.emit()

    def reset(self):
        self.set_points([(0.0, 0.0), (0.5, 0.5), (1.0, 1.0)])

    def _scene_pos(self, ev):
        return self.mapToScene(ev.position().toPoint())

    def _view_pos(self, ev):
        return self.plotItem.vb.mapSceneToView(self._scene_pos(ev))

    def _scene_of(self, x, y):
        return self.plotItem.vb.mapViewToScene(pg.Point(x, y))

    def _apply_hover(self, idx):
        self._hover_idx = idx
        n = len(self._pts)
        brushes = [self._brush_default] * n
        if 0 <= idx < n:
            brushes[idx] = self._brush_hover
        self._handles.setBrush(brushes)

    def _hit_handle(self, ev):
        sp = self._scene_pos(ev)
        best = -1
        best_d = self._HANDLE_TOL
        for i, (x, y) in enumerate(self._pts):
            sp_i = self._scene_of(x, y)
            d = ((sp - sp_i).x() ** 2 + (sp - sp_i).y() ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best = i
        return best

    def mousePressEvent(self, ev):
        p = self._scene_pos(ev)
        idx = self._hit_handle(ev)
        if ev.button() == Qt.MouseButton.LeftButton:
            # print(f"TC press L ({p.x():.3f},{p.y():.3f}) hit={idx}")
            if idx >= 0:
                self._press_idx = idx
                self._press_pos = p
                self._apply_hover(idx)
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                ev.accept()
                return
        elif ev.button() == Qt.MouseButton.RightButton:
            # print(f"TC press R ({p.x():.3f},{p.y():.3f}) hit={idx}")
            if idx >= 0 and len(self._pts) > 2:
                x0, _ = self._pts[idx]
                if self._EDGE_GUARD < x0 < 1.0 - self._EDGE_GUARD:
                    self._pts.pop(idx)
                    self._redraw()
                    self.changed.emit()
                    self.feedback.emit("Punkt entfernt")
                    ev.accept()
                    return
                self.feedback.emit("Endpunkte (0 und 1) sind geschützt")
                ev.accept()
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._press_idx >= 0 and self._drag < 0:
            p = self._scene_pos(ev)
            d = ((p - self._press_pos).x() ** 2 + (p - self._press_pos).y() ** 2) ** 0.5
            if d > self._DRAG_TOL:
                self._drag = self._press_idx
        if self._drag >= 0:
            pos = self._view_pos(ev)
            idx = self._drag
            lo = self._pts[idx - 1][0] if idx > 0 else 0.0
            hi = self._pts[idx + 1][0] if idx < len(self._pts) - 1 else 1.0
            x = min(max(pos.x(), lo), hi)
            y = min(max(pos.y(), 0.0), 1.0)
            self._pts[idx] = (float(x), float(y))
            self._redraw()
            self._apply_hover(idx)
            self.changed.emit()
            ev.accept()
            return
        if self._press_idx < 0:
            idx = self._hit_handle(ev)
            self._apply_hover(idx)
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor if idx >= 0 else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._press_idx >= 0 or self._drag >= 0:
            if self._drag >= 0:
                x, y = self._pts[self._drag]
                self.feedback.emit(f"Punkt ({x:.2f}, {y:.2f}) verschoben")
            self._press_idx = -1
            self._press_pos = None
            self._drag = -1
            self._apply_hover(-1)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            ev.accept()
            return
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self._hit_handle(ev) < 0:
            p = self._scene_pos(ev)
            pos = self._view_pos(ev)
            x = min(max(pos.x(), 0.0), 1.0)
            y = min(max(pos.y(), 0.0), 1.0)
            # print(f"TC dblclick ({p.x():.3f},{p.y():.3f}) -> data ({x:.3f},{y:.3f})")
            if min(abs(x - px) for px, py in self._pts) >= self._DUP_GUARD:
                self._pts.append((float(x), float(y)))
                self._pts.sort(key=lambda p: p[0])
                self._redraw()
                self.changed.emit()
                self.feedback.emit(f"Punkt bei ({x:.2f}, {y:.2f}) hinzugefügt")
            else:
                self.feedback.emit("Zu nah an vorhandenem Punkt")
            ev.accept()
            return
        super().mouseDoubleClickEvent(ev)

    def leaveEvent(self, event):
        if self._press_idx < 0 and self._drag < 0:
            self._apply_hover(-1)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)


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

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(4)

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
        rlay.addWidget(self._hist_plot, 3)

        tone_panel = QWidget()
        tlay = QVBoxLayout(tone_panel)
        tlay.setContentsMargins(0, 0, 0, 0)
        tlay.setSpacing(4)
        tone_head = QHBoxLayout()
        tone_head.setSpacing(6)
        self._tone_enabled = QCheckBox("Tone-Curve aktiv")
        self._tone_enabled.setChecked(True)
        self._tone_enabled.toggled.connect(lambda: self._debounce.start(50))
        tone_head.addWidget(self._tone_enabled)
        tone_head.addStretch()
        btn_tone_reset = QPushButton("Reset")
        btn_tone_reset.clicked.connect(self._tone_curve_reset)
        tone_head.addWidget(btn_tone_reset)
        tlay.addLayout(tone_head)
        self._tone_hint = QLabel("Ziehen = Punkt bewegen · Doppelklick = Punkt setzen · Rechtsklick = Punkt löschen")
        self._tone_hint.setStyleSheet("color: #888; font-size: 9pt;")
        tlay.addWidget(self._tone_hint)
        self._tone_feedback = QLabel("")
        self._tone_feedback.setStyleSheet("color: #00ff88; font-size: 9pt;")
        tlay.addWidget(self._tone_feedback)
        self._tone_fb_timer = QTimer(self)
        self._tone_fb_timer.setSingleShot(True)
        self._tone_fb_timer.timeout.connect(self._tone_feedback.clear)
        self._tone_curve = ToneCurveEditor()
        self._tone_curve.setMinimumHeight(150)
        self._tone_curve.changed.connect(lambda: self._debounce.start(50))
        self._tone_curve.feedback.connect(self._show_tone_feedback)
        tlay.addWidget(self._tone_curve, 1)
        rlay.addWidget(tone_panel, 2)

        blay.addWidget(right, 1)

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

        if self._tone_enabled.isChecked():
            xs, ys = self._tone_curve.curve()
            out = np.interp(img, xs, ys)
            if len(xs) > 1:
                lo = img < xs[0]
                hi = img > xs[-1]
                if np.any(lo):
                    s0 = (ys[1] - ys[0]) / (xs[1] - xs[0])
                    out[lo] = ys[0] + (img[lo] - xs[0]) * s0
                if np.any(hi):
                    s1 = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
                    out[hi] = ys[-1] + (img[hi] - xs[-1]) * s1
            img = out

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

    def _tone_curve_reset(self):
        self._tone_curve.reset()

    def _show_tone_feedback(self, msg):
        self._tone_feedback.setText(msg)
        self._tone_fb_timer.start(2000)

    # ── actions ─────────────────────────────────────────────

    def _reset_params(self):
        for s in (self._s_lift, self._s_gamma, self._s_exp, self._s_black):
            s.setValue(s.minimum() if s is self._s_lift else
                       s.minimum() if s is self._s_black else
                       100 if s is self._s_gamma else 0)
        self._tone_curve.reset()

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
