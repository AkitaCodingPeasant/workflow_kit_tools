"""工具探索與契約檢查。

一個「指令模組」必須提供五個名稱（契約）：

	NAME: str                                      指令名稱，小寫英數字、英文字母開頭
	SUMMARY: str                                   一行說明
	CATEGORY: str                                  分類：general／special／manage（見 CATEGORIES）
	configure_parser(parser) -> None               定義該指令自己的參數
	run(args: argparse.Namespace) -> None          執行；失敗 raise WktError

wkt/tools/ 下的模組會被自動探索；內建指令（menu、doctor、install、dev）列在 BUILTIN_MODULES。
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from types import ModuleType

from wkt import tools


NAME_RE = re.compile(r"^[a-z][a-z0-9]*$")
BUILTIN_MODULES = ("wkt.menu", "wkt.doctor", "wkt.install", "wkt.dev")

# 分類只在這裡定義一次；順序就是 `wkt help all` 的顯示順序。
#   general  通用工具：任何影片或圖片都可能用到（預設的 wkt --help 只列這一類）
#   special  特殊用途：只在特定規格或情境才會用到，只會出現在 wkt help special
#   manage   管理指令：不處理檔案的指令（內建指令一律是這一類，工具不可使用）
CATEGORIES = {
	"general": "通用工具",
	"special": "特殊用途",
	"manage": "管理指令",
}
DEFAULT_CATEGORY = "general"
MANAGE_CATEGORY = "manage"


def validate_command(module: ModuleType) -> None:
	"""不符合契約就 raise ValueError（這是開發階段的錯誤，不是使用者錯誤）。"""
	label = module.__name__
	name = getattr(module, "NAME", None)
	if not isinstance(name, str) or not NAME_RE.match(name):
		raise ValueError(f"{label}: NAME 必須是小寫英數字且以英文字母開頭，目前是 {name!r}")
	if not isinstance(getattr(module, "SUMMARY", None), str) or not module.SUMMARY.strip():
		raise ValueError(f"{label}: SUMMARY 必須是非空字串")
	category = getattr(module, "CATEGORY", None)
	if category not in CATEGORIES:
		raise ValueError(f"{label}: CATEGORY 必須是 {'、'.join(CATEGORIES)} 之一，目前是 {category!r}")
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
		if not callable(getattr(module, "plan", None)):
			raise ValueError(f"{module.__name__}: 缺少函式 plan()（用於 --dry-run）")
		if module.CATEGORY == MANAGE_CATEGORY:
			raise ValueError(f"{module.__name__}: 工具不能使用 {MANAGE_CATEGORY} 分類（那是內建指令專用）")
		modules.append(module)
	modules.sort(key=lambda module: module.NAME)
	return modules


def load_commands() -> tuple[list[ModuleType], list[ModuleType]]:
	"""回傳 (內建指令, 工具)；並確認指令名稱沒有重複。"""
	builtins = [importlib.import_module(name) for name in BUILTIN_MODULES]
	for module in builtins:
		validate_command(module)
		if module.CATEGORY != MANAGE_CATEGORY:
			raise ValueError(f"{module.__name__}: 內建指令的 CATEGORY 必須是 {MANAGE_CATEGORY}")
	discovered = discover_tools()

	seen: dict[str, str] = {}
	for module in (*builtins, *discovered):
		if module.NAME in seen:
			raise ValueError(f"指令名稱重複：{module.NAME}（{seen[module.NAME]} 與 {module.__name__}）")
		seen[module.NAME] = module.__name__
	return builtins, discovered


def group_by_category(modules: list[ModuleType]) -> dict[str, list[ModuleType]]:
	"""依 CATEGORIES 的順序分組，每組內依 NAME 排序；沒有任何指令的分類也會保留（空清單）。"""
	return {
		key: sorted((module for module in modules if module.CATEGORY == key), key=lambda module: module.NAME)
		for key in CATEGORIES
	}


def tool_categories() -> dict[str, str]:
	"""{工具名稱: 分類}（不含內建指令）。"""
	return {module.NAME: module.CATEGORY for module in discover_tools()}


def tool_names() -> set[str]:
	return set(tool_categories())
