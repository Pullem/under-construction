import av
import numpy as np
from collections import OrderedDict
from PyQt6.QtGui import QImage, QPixmap


class VideoSource:
	def __init__(self):
		self._container = None
		self._video_stream = None
		self.fps = 25.0
		self.total_frames = 0
		self._keyframes = []
		self._cache = OrderedDict()
		self._cache_max = 200
		self._last_frame = -1
		self._decoder = None
		self._path = ""

	def open(self, path):
		self.close()
		self._path = path
		self._container = av.open(path)
		streams = [s for s in self._container.streams if s.type == "video"]
		if not streams:
			raise ValueError("Kein Video-Stream gefunden")
		self._video_stream = streams[0]
		self.fps = float(self._video_stream.average_rate) if self._video_stream.average_rate else 25.0
		frames = self._video_stream.frames
		if frames and frames > 0:
			self.total_frames = frames
		else:
			dur = float(self._container.duration) / 1_000_000 if self._container.duration else 0
			self.total_frames = int(dur * self.fps) if dur > 0 else 1
		self._scan_keyframes()
		self._container.seek(0, stream=self._video_stream)
		self._last_frame = -1
		self._decoder = None

	def _scan_keyframes(self):
		self._keyframes = []
		for packet in self._container.demux(self._video_stream):
			if packet.is_keyframe and packet.pts is not None:
				fn = int(round(packet.pts * self._video_stream.time_base * self.fps))
				self._keyframes.append(fn)
		self._keyframes.sort()
		self._keyframes = list(dict.fromkeys(self._keyframes))

	def get_frame(self, frame_num):
		frame_num = max(0, min(self.total_frames - 1, frame_num))
		if frame_num in self._cache:
			self._cache.move_to_end(frame_num)
			return self._cache[frame_num]
		if self._decoder is None or frame_num <= self._last_frame or frame_num - self._last_frame > 60:
			self._seek_to(frame_num)
			self._decoder = self._container.decode(video=0)
		for frame in self._decoder:
			t = frame.time
			if t is None:
				continue
			fn = int(round(t * self.fps))
			pix = self._frame_to_pixmap(frame)
			self._add_cache(fn, pix)
			self._last_frame = fn
			if fn >= frame_num:
				return self._cache.get(frame_num)
		return None

	def _seek_to(self, frame_num):
		kf = 0
		for k in self._keyframes:
			if k <= frame_num:
				kf = k
			else:
				break
		seek_sec = kf / self.fps
		tb = float(self._video_stream.time_base) if self._video_stream.time_base else 1/90000
		self._container.seek(int(seek_sec / tb), stream=self._video_stream)

	def _frame_to_pixmap(self, frame):
		try:
			arr = frame.to_ndarray(format="rgb24")
			if arr is None:
				return None
			h, w, *_ = arr.shape
			img = QImage(arr.tobytes(), w, h, arr.strides[0], QImage.Format.Format_RGB888)
			return QPixmap.fromImage(img)
		except Exception as e:
			print(f"Frame-Konvertierung fehlgeschlagen: {e}")
			return None

	def _add_cache(self, fn, pix):
		self._cache[fn] = pix
		if len(self._cache) > self._cache_max:
			self._cache.popitem(last=False)

	def get_keyframes(self):
		return list(self._keyframes)

	def is_open(self):
		return self._container is not None and self._video_stream is not None

	def close(self):
		self._cache.clear()
		self._decoder = None
		self._last_frame = -1
		self._keyframes = []
		self._last_arr = None
		if self._container:
			self._container.close()
			self._container = None
		self._video_stream = None
		self._path = ""
