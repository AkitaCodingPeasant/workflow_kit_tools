"""終端機輸出的共用設定：詳細模式、批次標籤、進度條。

進度條只在 stderr 是互動式終端機、且未開啟詳細模式時顯示；
重新導向到檔案或管線時完全不輸出，避免弄髒輸出內容。
"""

from __future__ import annotations

import os
import sys


VERBOSE_ENV = "WKT_VERBOSE"
BAR_WIDTH = 24

_verbose = os.environ.get(VERBOSE_ENV) == "1"
_label = ""


def set_verbose(value: bool) -> None:
	global _verbose
	_verbose = value or os.environ.get(VERBOSE_ENV) == "1"


def is_verbose() -> bool:
	return _verbose


def set_label(label: str) -> None:
	"""批次處理時，在進度條前面顯示的文字，例如 "[2/5] clip.mp4"。"""
	global _label
	_label = label


def format_bar(label: str, fraction: float, width: int = BAR_WIDTH) -> str:
	fraction = min(max(fraction, 0.0), 1.0)
	filled = int(round(fraction * width))
	bar = "█" * filled + "░" * (width - filled)
	prefix = f"{label} " if label else ""
	return f"{prefix}[{bar}] {fraction * 100:3.0f}%"


class Progress:
	"""單行進度條。total 為 None（不知道總量）時不顯示任何東西。"""

	def __init__(self, total: float | None, label: str | None = None) -> None:
		self.total = total if total and total > 0 else None
		self.label = _label if label is None else label
		self.enabled = bool(self.total) and not _verbose and sys.stderr.isatty()
		self._last = -1

	def update(self, value: float) -> None:
		if not self.enabled or self.total is None:
			return
		percent = int(min(max(value / self.total, 0.0), 1.0) * 100)
		if percent == self._last:
			return
		self._last = percent
		sys.stderr.write("\r" + format_bar(self.label, value / self.total))
		sys.stderr.flush()

	def close(self) -> None:
		if self.enabled and self._last >= 0:
			sys.stderr.write("\r" + " " * (BAR_WIDTH + len(self.label) + 12) + "\r")
			sys.stderr.flush()
