from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import IO

from wkt.core.errors import WktError


FFMPEG_MISSING_MESSAGE = "找不到 ffmpeg，請先安裝 ffmpeg 並確認可在命令列執行。"


def find_ffmpeg() -> str:
	"""找出 ffmpeg 執行檔路徑；找不到時 raise WktError。

	搜尋順序：PATH → WinGet 安裝位置 → 常見的手動安裝資料夾。
	"""
	found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
	if found:
		return found

	local_app_data = os.environ.get("LOCALAPPDATA")
	if local_app_data:
		winget_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
		if winget_root.exists():
			for candidate in winget_root.glob("Gyan.FFmpeg_*/*/bin/ffmpeg.exe"):
				return str(candidate)

	for candidate in (
		Path("C:/ffmpeg/bin/ffmpeg.exe"),
		Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
	):
		if candidate.exists():
			return str(candidate)

	raise WktError(FFMPEG_MISSING_MESSAGE)


def run_ffmpeg(command: list[str], *, stdout: IO[bytes] | None = None) -> None:
	"""執行 ffmpeg 指令；失敗時 raise WktError（結束碼沿用 ffmpeg 的）。"""
	try:
		subprocess.run(command, stdout=stdout, check=True)
	except FileNotFoundError as exc:
		raise WktError(FFMPEG_MISSING_MESSAGE) from exc
	except subprocess.CalledProcessError as exc:
		raise WktError(f"處理失敗：ffmpeg 結束碼 {exc.returncode}", exit_code=exc.returncode) from exc
