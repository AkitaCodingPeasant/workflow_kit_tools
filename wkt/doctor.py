"""wkt doctor：一次檢查 WKT 能不能正常運作，並對每個問題給出修復指令。

狀態：
	ok   正常
	warn 部分功能受影響，但不影響其他功能（不計入失敗）
	fail 核心功能無法使用（結束碼 1）
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from wkt import __version__
from wkt.core.errors import WktError
from wkt.core.ffmpeg import find_ffmpeg


NAME = "doctor"
SUMMARY = "檢查執行環境（Python／ffmpeg／OpenCV／選單／PATH）並提供修復建議"
CATEGORY = "manage"

OK, WARN, FAIL = "ok", "warn", "fail"
MIN_PYTHON = (3, 10)
LABELS = {OK: "[ OK ]", WARN: "[警告]", FAIL: "[失敗]"}  # 純文字標記：重新導向到檔案時也不會有編碼問題
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Check:
	name: str
	status: str
	detail: str
	fix: str | None = None


def check_python() -> Check:
	version = ".".join(str(part) for part in sys.version_info[:3])
	if sys.version_info[:2] >= MIN_PYTHON:
		return Check("Python", OK, f"{version}（需要 {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 以上）")
	return Check(
		"Python",
		FAIL,
		f"{version} 太舊，需要 {MIN_PYTHON[0]}.{MIN_PYTHON[1]} 以上",
		"winget install Python.Python.3.12",
	)


def _ffmpeg_output(ffmpeg_path: str, *args: str) -> str:
	result = subprocess.run(
		[ffmpeg_path, "-hide_banner", *args],
		capture_output=True,
		text=True,
		encoding="utf-8",
		errors="replace",
		timeout=30,
	)
	return result.stdout


def check_ffmpeg() -> Check:
	try:
		ffmpeg_path = find_ffmpeg()
	except WktError:
		return Check("ffmpeg", FAIL, "找不到 ffmpeg", "winget install Gyan.FFmpeg（安裝後重新開啟終端機）")

	try:
		version_line = _ffmpeg_output(ffmpeg_path, "-version").splitlines()[0]
		has_x264 = "libx264" in _ffmpeg_output(ffmpeg_path, "-encoders")
	except (OSError, IndexError, subprocess.TimeoutExpired):
		return Check("ffmpeg", FAIL, f"無法執行：{ffmpeg_path}", "重新安裝：winget install Gyan.FFmpeg")

	detail = f"{version_line.removeprefix('ffmpeg version ').split(' Copyright')[0]}（{ffmpeg_path}）"
	if not has_x264:
		return Check(
			"ffmpeg",
			WARN,
			f"{detail}；缺少 libx264 編碼器，reencode、tobt709 無法使用",
			"改裝完整版：winget install Gyan.FFmpeg",
		)
	return Check("ffmpeg", OK, detail)


def check_opencv() -> Check:
	missing = []
	versions = []
	for module_name in ("cv2", "numpy"):
		try:
			module = __import__(module_name)
			versions.append(f"{module_name} {module.__version__}")
		except ImportError:
			missing.append(module_name)
	if missing:
		return Check(
			"OpenCV／numpy",
			WARN,
			f"未安裝 {'、'.join(missing)}（只有 to1080、to1088 需要）",
			"py -3 -m pip install -r requirements.txt",
		)
	return Check("OpenCV／numpy", OK, "、".join(versions))


def check_questionary() -> Check:
	try:
		import questionary
	except ImportError:
		return Check(
			"questionary",
			WARN,
			"未安裝（只有互動選單需要；wkt 其他功能不受影響）",
			"py -3 -m pip install -r requirements.txt",
		)
	return Check("questionary", OK, f"questionary {questionary.__version__}")


def check_menu() -> list[Check]:
	from wkt import menu

	checks = []
	for extension in menu.MENU:
		state = menu.menu_state(extension)
		name = f"右鍵選單 {extension}"
		if state == "ok":
			checks.append(Check(name, OK, "已註冊"))
		elif state == "missing":
			checks.append(Check(name, WARN, "尚未註冊", "wkt menu register"))
		elif state == "stale":
			checks.append(Check(name, WARN, "已註冊但設定較舊（仍可使用）", "wkt menu register"))
		else:
			checks.append(Check(name, FAIL, "已註冊但指向的位置不存在（資料夾被移動過？）", "wkt menu register"))

	if menu.ICON.is_file():
		checks.append(Check("選單圖示", OK, str(menu.ICON)))
	else:
		checks.append(Check("選單圖示", WARN, f"找不到 {menu.ICON}", "wkt dev icon"))
	return checks


def _same_path(left: str, right: Path) -> bool:
	return os.path.normcase(os.path.abspath(left)) == os.path.normcase(str(right))


def find_on_path(name: str, path_value: str | None = None) -> str | None:
	"""只在 PATH 的各個資料夾中找 name.cmd／.exe／.bat。

	不用 shutil.which：它在 Windows 上會一併搜尋「目前資料夾」，
	在專案資料夾裡執行時會誤判成已加入 PATH。
	"""
	for folder in (os.environ.get("PATH", "") if path_value is None else path_value).split(os.pathsep):
		if not folder:
			continue
		for extension in (".cmd", ".exe", ".bat"):
			candidate = Path(folder) / f"{name}{extension}"
			if candidate.is_file():
				return str(candidate)
	return None


def check_path() -> Check:
	found = find_on_path("wkt")
	if found and _same_path(found, PROJECT_ROOT / "wkt.cmd"):
		return Check("PATH", OK, "終端機可直接輸入 wkt")
	if found:
		return Check("PATH", WARN, f"PATH 中的 wkt 指向別處：{found}", "wkt install（或雙擊 install.cmd）")
	return Check("PATH", WARN, "終端機無法直接輸入 wkt（右鍵選單不受影響）", "雙擊 install.cmd，並重新開啟終端機")


def run_checks() -> list[Check]:
	checks = [check_python(), check_ffmpeg(), check_opencv(), check_questionary()]
	checks.extend(check_menu())
	checks.append(check_path())
	return checks


def render(checks: list[Check]) -> str:
	lines = [f"WKT {__version__} 環境檢查", ""]
	width = max(len(check.name) for check in checks)
	for check in checks:
		lines.append(f"{LABELS[check.status]} {check.name:<{width}}  {check.detail}")
		if check.fix:
			lines.append(f"       修復：{check.fix}")
	return "\n".join(lines)


def summarize(checks: list[Check]) -> tuple[int, int]:
	failures = sum(1 for check in checks if check.status == FAIL)
	warnings = sum(1 for check in checks if check.status == WARN)
	return failures, warnings


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.description = "檢查 Python、ffmpeg、OpenCV、右鍵選單與 PATH，並對每個問題給出修復指令。有失敗項目時結束碼為 1。"


def run(args: argparse.Namespace, checker: Callable[[], list[Check]] = run_checks) -> None:
	checks = checker()
	print(render(checks))
	failures, warnings = summarize(checks)
	print()
	if failures:
		raise WktError(f"{failures} 項失敗、{warnings} 項警告：請依上方「修復」建議處理。")
	print("全部通過。" if not warnings else f"沒有失敗項目（{warnings} 項警告，不影響核心功能）。")
