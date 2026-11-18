"""Python 安裝方式：全域 Python 或專案內的虛擬環境（.venv）。

安裝方式記錄在專案根目錄的 .wkt-env（內容為 global 或 venv），由 scripts/install.ps1 寫入，
wkt.cmd 依此決定用哪個 Python 執行。沒有這個檔案時視為全域（相容舊版安裝）。
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODE_FILE = PROJECT_ROOT / ".wkt-env"
VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"

GLOBAL, VENV = "global", "venv"
MODES = (GLOBAL, VENV)
MODE_TEXT = {GLOBAL: "全域 Python", VENV: "虛擬環境（.venv）"}


def configured_mode(mode_file: Path = MODE_FILE) -> str:
	"""讀取安裝方式；檔案不存在或內容無法辨識時回傳 global。"""
	try:
		value = mode_file.read_text(encoding="utf-8-sig").strip().lower()
	except OSError:
		return GLOBAL
	return value if value in MODES else GLOBAL


def running_in_venv() -> bool:
	return sys.prefix != sys.base_prefix


def pip_install_hint() -> str:
	"""依安裝方式給出安裝 requirements.txt 的指令。"""
	if configured_mode() == VENV:
		return r".venv\Scripts\python.exe -m pip install -r requirements.txt"
	return "py -3 -m pip install -r requirements.txt"
