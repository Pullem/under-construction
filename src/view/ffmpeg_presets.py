from PyQt6.QtCore import QTime

from .tab_builder import active_media_prefix


def show_trim_widget(view):
	view.video_params_group.setVisible(False)
	view.video_trim_widget.setVisible(True)


def hide_trim_widget(view):
	prefix = active_media_prefix(view)
	tw = getattr(view, f"{prefix}_trim_widget", None)
	if tw:
		tw.setVisible(False)
	pg = getattr(view, f"{prefix}_params_group", None)
	if pg:
		pg.setVisible(True)


def preset_trim(view):
	show_trim_widget(view)


def preset_frames(view):
	hide_trim_widget(view)
	w = lambda n: getattr(view, f"video_{n}")
	w("filter").setText("fps=1/10")
	w("format").setCurrentIndex(0)
	w("end").clear()


def preset_audio(view):
	hide_trim_widget(view)
	w = lambda n: getattr(view, f"video_{n}")
	w("filter").clear()
	w("format").setCurrentIndex(0)
	w("start").setTime(QTime(0, 0))
	w("end").clear()


def preset_timecode(view):
	hide_trim_widget(view)
	w = lambda n: getattr(view, f"video_{n}")
	w("filter").setText(
		"drawtext=timecode='00\\:00\\:00\\:00':rate=25:fontsize=40:fontcolor=white:box=1:boxcolor=black@1:x=10:y=__POSITION__,"
		"drawtext=timecode='__REALTIME__':rate=25:fontsize=40:fontcolor=white:box=1:boxcolor=black@1:x=main_w-text_w-10:y=__POSITION__"
	)
	w("format").setCurrentIndex(0)
	w("start").setTime(QTime(0, 0))
	w("end").clear()


def preset_container(view):
	hide_trim_widget(view)
	p = active_media_prefix(view)
	w = lambda n: getattr(view, f"{p}_{n}")
	w("filter").clear()
	w("format").setCurrentIndex(0)
	if p == "video":
		w("start").setTime(QTime(0, 0))
		w("end").clear()


def preset_hash(view):
	hide_trim_widget(view)
	p = active_media_prefix(view)
	w = lambda n: getattr(view, f"{p}_{n}")
	w("filter").setText("-f framehash -")
	w("format").setCurrentIndex(0)
	if p == "video":
		w("start").setTime(QTime(0, 0))
		w("end").clear()


def preset_custom(view):
	hide_trim_widget(view)


def preset_bitstream(view):
	hide_trim_widget(view)
	w = lambda n: getattr(view, f"video_{n}")
	w("filter").setText("__BITSTREAM__")
