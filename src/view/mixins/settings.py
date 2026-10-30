"""Einstellungen: Passwörter, Basisordner, Zeitzone, GPU-Status."""

from PyQt6.QtWidgets import QLineEdit, QMessageBox

from ...utils.gpu_config import get_gpu_config, check_cuda_available
class SettingsMixin:
	"""Einstellungen-Tab: Anzeige, Passwörter, Speichern."""

	def _refresh_settings_display(self, db_user, db_password, case_root, root_password=""):
		self.lbl_db_user.setText(db_user or "—")
		self._raw_db_password = db_password or ""
		self._pw_visible = False
		self._update_password_display()
		self._raw_root_password = root_password or ""
		self._root_pw_visible = False
		self._update_root_password_display()
		self.txt_case_root.setText(case_root or "")
		self.txt_new_db_password.clear()
		self._refresh_timezone()

	def _update_password_display(self):
		if self._raw_db_password:
			self.lbl_db_password.setText(self._raw_db_password if self._pw_visible else "••••••••")
		else:
			self.lbl_db_password.setText("—")
		self.btn_toggle_pw.setVisible(bool(self._raw_db_password))

	def _update_root_password_display(self):
		if self._raw_root_password:
			self.lbl_root_password.setText(self._raw_root_password if self._root_pw_visible else "••••••••")
		else:
			self.lbl_root_password.setText("—")

	def _toggle_root_pw_visible(self, checked):
		self._root_pw_visible = checked
		self._update_root_password_display()

	def _toggle_password_visible(self, checked):
		self._pw_visible = checked
		self._update_password_display()

	def _toggle_new_pw_visible(self, checked):
		self.txt_new_db_password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

	def _on_browse_case_root(self):
		from PyQt6.QtWidgets import QFileDialog
		folder = QFileDialog.getExistingDirectory(self, "Basisordner für Fälle auswählen")
		if folder:
			self.txt_case_root.setText(folder)

	def _on_save_settings(self):
		case_root = self.txt_case_root.text().strip()
		if not case_root:
			QMessageBox.warning(self, "Fehler", "Basisordner darf nicht leer sein.")
			return
		new_pw = self.txt_new_db_password.text().strip()
		if new_pw:
			self.update_db_password_requested.emit(new_pw)
		self.save_settings_requested.emit(case_root)

	@staticmethod
	def _get_current_utc_offset():
		from datetime import datetime, timedelta
		now = datetime.now()
		mar = datetime(now.year, 3, 31)
		last_sun_mar = mar - timedelta(days=(mar.weekday() + 1) % 7)
		oct_ = datetime(now.year, 10, 31)
		last_sun_oct = oct_ - timedelta(days=(oct_.weekday() + 1) % 7)
		return 2 if last_sun_mar <= now < last_sun_oct else 1

	def _refresh_timezone(self):
		offset = self._get_current_utc_offset()
		name = "Sommerzeit UTC+2 (MESZ)" if offset == 2 else "Winterzeit UTC+1 (MEZ)"
		if hasattr(self, 'lbl_tz_info'):
			self.lbl_tz_info.setText(name)
		for combo_name in ('video_utc_combo', 'cbo_offset'):
			combo = getattr(self, combo_name, None)
			if combo:
				idx = combo.findData(offset)
				if idx >= 0:
					combo.setCurrentIndex(idx)

	def _update_gpu_status(self):
		"""Update GPU status label in settings tab."""
		if not hasattr(self, 'lbl_gpu_status'):
			return
		try:
			cuda_available, gpu_name = check_cuda_available()
			config = get_gpu_config()
			if cuda_available and config.enabled:
				vram_gb = config.max_vram_mb / 1024
				self.lbl_gpu_status.setText(
					f"✅ GPU aktiv: {gpu_name}\n"
					f"   Gerät: {config.device_index} | VRAM-Limit: {vram_gb:.1f} GB\n"
					f"   Decode: {config.decode_hwaccel.upper()} | Thumbnail HW: {'Ja' if config.thumbnail_hwaccel else 'Nein'}"
				)
				self.lbl_gpu_status.setStyleSheet(
					"background-color: #14311c; color: #7ddc7d; padding: 8px 10px; "
					"border: 1px solid #2e6b3f; border-radius: 4px;"
				)
			elif config.enabled and not cuda_available:
				self.lbl_gpu_status.setText(
					"⚠️ GPU konfiguriert, aber CUDA nicht verfügbar\n"
					"Fallback auf CPU-Berechnung"
				)
				self.lbl_gpu_status.setStyleSheet(
					"background-color: #3a3115; color: #ffd666; padding: 8px 10px; "
					"border: 1px solid #7a6a2a; border-radius: 4px;"
				)
			else:
				self.lbl_gpu_status.setText(
					"❌ GPU deaktiviert (config/gpu.ini: enabled=false)"
				)
				self.lbl_gpu_status.setStyleSheet(
					"background-color: #3a1c1c; color: #ff9a9a; padding: 8px 10px; "
					"border: 1px solid #7a3a3a; border-radius: 4px;"
				)
		except Exception as e:
			self.lbl_gpu_status.setText(f"❌ GPU-Status Fehler: {e}")
			self.lbl_gpu_status.setStyleSheet(
				"background-color: #3a1c1c; color: #ff9a9a; padding: 8px 10px; "
				"border: 1px solid #7a3a3a; border-radius: 4px;"
			)
