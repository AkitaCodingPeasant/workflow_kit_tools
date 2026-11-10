"""工具探索與契約檢查。

一個「指令模組」必須提供四個名稱（契約）：

	NAME: str                                      指令名稱，小寫英數字、英文字母開頭
	SUMMARY: str                                   一行說明
	configure_parser(parser) -> None               定義該指令自己的參數
	run(args: argparse.Namespace) -> None          執行；失敗 raise WktError

wkt/tools/ 下的模組會被自動探索；wkt/menu.py 是唯一的內建指令。
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from types import ModuleType

from wkt import tools


NAME_RE = re.compile(r"^[a-z][a-z0-9]*$")
BUILTIN_MODULES = ("wkt.menu",)


def validate_command(module: ModuleType) -> None:
	"""不符合契約就 raise ValueError（這是開發階段的錯誤，不是使用者錯誤）。"""
	label = module.__name__
	name = getattr(module, "NAME", None)
	if not isinstance(name, str) or not NAME_RE.match(name):
		raise ValueError(f"{label}: NAME 必須是小寫英數字且以英文字母開頭，目前是 {name!r}")
	if not isinstance(getattr(module, "SUMMARY", None), str) or not module.SUMMARY.strip():
		raise ValueError(f"{label}: SUMMARY 必須是非空字串")
	for function_name in ("configure_parser", "run"):
		if not callable(getattr(module, function_name, None)):
			raise ValueError(f"{label}: 缺少函式 {function_name}()")


def discover_tools() -> list[ModuleType]:
	"""載入 wkt/tools/ 下所有非底線開頭的模組，依 NAME 排序。"""
	modules = []
	for info in pkgutil.iter_modules(tools.__path__):
		if info.name.startswith("_"):
			continue
		module = importlib.import_module(f"{tools.__name__}.{info.name}")
		validate_command(module)
		modules.append(module)
	modules.sort(key=lambda module: module.NAME)
	return modules


def load_commands() -> tuple[list[ModuleType], list[ModuleType]]:
	"""回傳 (內建指令, 工具)；並確認指令名稱沒有重複。"""
	builtins = [importlib.import_module(name) for name in BUILTIN_MODULES]
	for module in builtins:
		validate_command(module)
	discovered = discover_tools()

	seen: dict[str, str] = {}
	for module in (*builtins, *discovered):
		if module.NAME in seen:
			raise ValueError(f"指令名稱重複：{module.NAME}（{seen[module.NAME]} 與 {module.__name__}）")
		seen[module.NAME] = module.__name__
	return builtins, discovered


def tool_names() -> set[str]:
	return {module.NAME for module in discover_tools()}
