from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import IO

from wkt.core import ui
from wkt.core.errors import WktError


FFMPEG_MISSING_MESSAGE = (
	"找不到 ffmpeg，請先安裝 ffmpeg 並確認可在命令列執行。\n"
	"  安裝：winget install Gyan.FFmpeg（安裝後請重新開啟終端機）\n"
	"  檢查：wkt doctor"
)
QUIET_FLAGS = ["-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:2"]
PROGRESS_KEY_RE = re.compile(r"^[a-z_][a-z0-9_]*=")
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
ERROR_TAIL_LINES = 15


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


def parse_timecode(text: str | None) -> float | None:
	""""3"、"00:00:03"、"1:02.5" → 秒數；無法解析回傳 None。"""
	if not text:
		return None
	try:
		seconds = 0.0
		for part in text.strip().split(":"):
			seconds = seconds * 60 + float(part)
		return seconds
	except ValueError:
		return None


def probe_duration(ffmpeg_path: str, input_path: Path) -> float | None:
	"""用 `ffmpeg -i` 讀取媒體長度（秒）；圖片或無法判斷時回傳 None。"""
	try:
		result = subprocess.run(
			[ffmpeg_path, "-hide_banner", "-i", str(input_path)],
			capture_output=True,
			text=True,
			encoding="utf-8",
			errors="replace",
		)
	except OSError:
		return None
	match = DURATION_RE.search(result.stderr)
	if not match:
		return None
	hours, minutes, seconds = match.groups()
	return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _progress_seconds(line: str) -> float | None:
	"""從 `-progress` 的輸出行取出已處理的秒數（out_time_us／out_time_ms 單位都是微秒）。"""
	key, _, value = line.partition("=")
	if key in ("out_time_us", "out_time_ms"):
		try:
			return int(value) / 1_000_000
		except ValueError:
			return None
	return None


def run_ffmpeg(
	command: list[str],
	*,
	stdout: IO[bytes] | None = None,
	duration: float | None = None,
) -> None:
	"""執行 ffmpeg 指令；失敗時 raise WktError（結束碼沿用 ffmpeg 的）。

	預設隱藏 ffmpeg 的日誌，只顯示進度條（需要 duration 才知道總量）；
	失敗時才印出 ffmpeg 的錯誤訊息。詳細模式（wkt -v）下原樣顯示 ffmpeg 的完整輸出。
	"""
	if ui.is_verbose():
		_run_verbose(command, stdout)
		return

	quiet_command = [command[0], *QUIET_FLAGS, *command[1:]]
	progress = ui.Progress(duration)
	error_lines: list[str] = []
	try:
		process = subprocess.Popen(
			quiet_command,
			stdout=stdout,
			stderr=subprocess.PIPE,
			text=True,
			encoding="utf-8",
			errors="replace",
		)
	except FileNotFoundError as exc:
		raise WktError(FFMPEG_MISSING_MESSAGE) from exc

	with process:  # 離開時一定會關閉 stderr 管道
		try:
			assert process.stderr is not None
			for raw_line in process.stderr:
				line = raw_line.rstrip()
				seconds = _progress_seconds(line)
				if seconds is not None:
					progress.update(seconds)
				elif line and not PROGRESS_KEY_RE.match(line):
					error_lines.append(line)
			return_code = process.wait()
		except BaseException:
			process.kill()
			raise
		finally:
			progress.close()

	if return_code != 0:
		if error_lines:
			print("\n".join(error_lines[-ERROR_TAIL_LINES:]), file=sys.stderr)
		raise WktError(f"處理失敗：ffmpeg 結束碼 {return_code}", exit_code=return_code)


def _run_verbose(command: list[str], stdout: IO[bytes] | None) -> None:
	try:
		subprocess.run(command, stdout=stdout, check=True)
	except FileNotFoundError as exc:
		raise WktError(FFMPEG_MISSING_MESSAGE) from exc
	except subprocess.CalledProcessError as exc:
		raise WktError(f"處理失敗：ffmpeg 結束碼 {exc.returncode}", exit_code=exc.returncode) from exc
