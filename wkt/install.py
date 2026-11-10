"""wkt install：重新執行一鍵安裝（修復用）。

第一次安裝時 Python 可能還不存在，所以首次安裝只能雙擊根目錄的 install.cmd；
裝好之後，要修復或重裝都可以直接用這個指令。實際工作由 scripts/install.ps1 完成。
想「只檢查、不修改」請用 wkt doctor。
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from wkt.core.errors import WktError


NAME = "install"
SUMMARY = "重新執行一鍵安裝：補齊 ffmpeg／OpenCV、加入 PATH、註冊右鍵選單（修復用）"
CATEGORY = "manage"

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "install.ps1"


def powershell_command(args: argparse.Namespace, script: Path = SCRIPT) -> list[str]:
	command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
	if args.yes:
		command.append("-Yes")
	if args.no_path:
		command.append("-NoPath")
	if args.no_menu:
		command.append("-NoMenu")
	return command


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.description = "補齊缺少的 ffmpeg／OpenCV、把 wkt 加入 PATH、註冊右鍵選單，最後自動執行 wkt doctor。"
	parser.add_argument("-y", "--yes", action="store_true", help="不詢問確認，直接執行")
	parser.add_argument("--no-path", action="store_true", help="不修改使用者 PATH")
	parser.add_argument("--no-menu", action="store_true", help="不註冊右鍵選單")


def run(args: argparse.Namespace) -> None:
	if not SCRIPT.is_file():
		raise WktError(f"找不到安裝腳本：{SCRIPT}")
	code = subprocess.run(powershell_command(args)).returncode
	if code != 0:
		raise WktError(f"安裝未完成（結束碼 {code}）。", exit_code=code)
