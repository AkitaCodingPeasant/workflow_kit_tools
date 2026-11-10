from __future__ import annotations


class WktError(Exception):
	"""可預期的失敗（使用者輸入錯誤、缺少外部程式、ffmpeg 失敗等）。

	工具遇到這類狀況時一律 raise WktError，不要自己 print 或 sys.exit；
	由 wkt.cli 統一輸出到 stderr 並轉成結束碼。
	"""

	def __init__(self, message: str, exit_code: int = 1) -> None:
		super().__init__(message)
		self.message = message
		self.exit_code = exit_code
