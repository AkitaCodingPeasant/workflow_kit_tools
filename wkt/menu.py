"""檔案總管右鍵選單（傳統選單，Windows 11 為「顯示更多選項」）的註冊與解除。

選單只寫入目前使用者的 HKCU，不需要管理員權限，也不需要簽章。
要新增選單項目或檔案類型，只改下方的 MENU 設定即可，再執行 `wkt menu register`。
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from wkt.core.errors import WktError


NAME = "menu"
SUMMARY = "註冊或解除檔案總管右鍵選單（register／unregister／status）"

APP_KEY = "WorkflowKitTools"
MENU_LABEL = "WKT"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = PROJECT_ROOT / "wkt.cmd"
# 選單圖示。registry 的 Icon 不支援 PNG，所以用由 assets/icon.png 產生的 .ico（scripts/make_icon.py）
ICON = PROJECT_ROOT / "assets" / "icon.ico"


@dataclass(frozen=True)
class MenuItem:
	tool: str  # 對應 wkt/tools/ 的 NAME
	label: str  # 右鍵選單顯示的文字


# 副檔名 → 該類型檔案的右鍵選單項目（依順序顯示）
MENU: dict[str, tuple[MenuItem, ...]] = {
	".mp4": (
		MenuItem("togif", "轉換成 .gif"),
		MenuItem("reencode", "重新編碼"),
	),
}


def menu_key(extension: str) -> str:
	return rf"Software\Classes\SystemFileAssociations\{extension}\shell\{APP_KEY}"


def command_line(tool: str) -> str:
	return f'"{LAUNCHER}" {tool} "%1"'


def check_menu_config() -> None:
	"""MENU 引用的工具都必須存在，否則 raise WktError。"""
	from wkt.registry import tool_names

	known = tool_names()
	for extension, items in MENU.items():
		if not extension.startswith("."):
			raise WktError(f"MENU 的副檔名必須以 . 開頭：{extension}")
		for item in items:
			if item.tool not in known:
				raise WktError(f"MENU 引用了不存在的工具：{item.tool}（{extension}）")


def _delete_tree(winreg, path: str) -> bool:
	"""遞迴刪除 HKCU 下的 registry 樹；原本就不存在回傳 False。"""
	try:
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS)
	except FileNotFoundError:
		return False
	with key:
		while True:
			try:
				child = winreg.EnumKey(key, 0)
			except OSError:
				break
			_delete_tree(winreg, f"{path}\\{child}")
	winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
	return True


def _set_values(winreg, path: str, values: dict[str, str]) -> None:
	with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
		for name, value in values.items():
			winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def register() -> None:
	import winreg

	if not LAUNCHER.is_file():
		raise WktError(f"找不到工具入口：{LAUNCHER}")
	check_menu_config()
	if not ICON.is_file():
		print(f"找不到選單圖示，將不顯示圖示：{ICON}（可執行 scripts\\make_icon.py 產生）", file=sys.stderr)

	for extension, items in MENU.items():
		base = menu_key(extension)
		_delete_tree(winreg, base)  # 先清掉舊項目，避免已移除的項目殘留
		menu_values = {"MUIVerb": MENU_LABEL, "SubCommands": ""}
		if ICON.is_file():
			menu_values["Icon"] = str(ICON)
		_set_values(winreg, base, menu_values)
		for index, item in enumerate(items, start=1):
			item_path = rf"{base}\shell\{index:02d}_{item.tool}"
			_set_values(winreg, item_path, {"MUIVerb": item.label})
			_set_values(winreg, rf"{item_path}\command", {"": command_line(item.tool)})
		labels = "／".join(item.label for item in items)
		print(f"已註冊：{extension} 右鍵選單 → {MENU_LABEL} → {labels}")
	print("Windows 11 請按右鍵 →「顯示更多選項」（或 Shift+F10）。")


def unregister() -> None:
	import winreg

	for extension in MENU:
		removed = _delete_tree(winreg, menu_key(extension))
		print(f"{'已解除' if removed else '原本就未註冊'}：{extension}")


def status() -> None:
	import winreg

	for extension in MENU:
		try:
			with winreg.OpenKey(winreg.HKEY_CURRENT_USER, menu_key(extension)):
				print(f"已註冊：{extension}")
		except FileNotFoundError:
			print(f"未註冊：{extension}")


ACTIONS = {"register": register, "unregister": unregister, "status": status}


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.add_argument("action", choices=tuple(ACTIONS), help="register 註冊／unregister 解除／status 查看目前狀態")


def run(args: argparse.Namespace) -> None:
	try:
		ACTIONS[args.action]()
	except OSError as exc:
		raise WktError(f"操作 registry 失敗：{exc}") from exc
