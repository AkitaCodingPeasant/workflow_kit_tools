"""wkt 統一入口：把 registry 找到的指令組成 argparse 子指令並分派執行。

說明的顯示規則（分類定義在 wkt/registry.py 的 CATEGORIES）：

	wkt / wkt -h        只列「通用工具」，最後附上其他分類的查看方式
	wkt help special    列出「特殊用途」工具
	wkt help manage     列出「管理指令」
	wkt help all        列出全部
	wkt <任何指令> -h   該指令自己的說明，不受分類影響（特殊工具要自己輸入才會看到它的提示）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from types import ModuleType

from wkt import __version__
from wkt.batch import is_batchable, run_batch
from wkt.core import ui
from wkt.core.errors import WktError
from wkt.tui import NO_TUI_ENV
from wkt.registry import CATEGORIES, DEFAULT_CATEGORY, group_by_category, load_commands


DEBUG_ENV = "WKT_DEBUG"  # 設為 1 時，未預期的例外會顯示完整 traceback
MENU_FLAG = "--from-menu"  # 右鍵選單專用：見 wkt/launcher.py
HELP_ALL = "all"
INVALID_CHOICE_RE = re.compile(r"invalid choice: '([^']*)'")

USAGE = "wkt [-h] [--version] [-v] [--no-tui] <指令> ..."

# 說明底下的範例跟著分類走；同時顯示多個分類（help all）時用通用工具的範例
EXAMPLES = {
	"general": """\
範例：
  wkt toframe input.mp4
  wkt togif a.mp4 b.mp4 c.mp4      一次處理多個檔案
  wkt -v reencode input.mp4        顯示 ffmpeg 的完整輸出
  wkt <指令> -h                    查看某個指令的參數
""",
	"special": """\
範例：
  wkt to1080 frame.png             1920x1088 裁成 1920x1080
  wkt tobt709 input.mp4            BT.601 轉 BT.709
  wkt <指令> -h                    查看某個指令的參數
""",
	"manage": """\
範例：
  wkt doctor                       檢查執行環境
  wkt menu register                註冊右鍵選單
  wkt dev test                     執行測試
  wkt <指令> -h                    查看某個指令的參數
""",
}


class WktArgumentParser(argparse.ArgumentParser):
	def error(self, message: str) -> None:
		match = INVALID_CHOICE_RE.search(message)
		if match and self.prog == "wkt":
			# 不用 argparse 預設的訊息：它會把所有指令名稱（含沒有列在說明裡的）一次列出
			self.print_usage(sys.stderr)
			self.exit(2, f"wkt: 未知的指令：{match.group(1)}\n執行 wkt help all 查看所有指令。\n")
		super().error(message)


def render_commands(grouped: dict[str, list[ModuleType]], visible: Sequence[str]) -> str:
	"""把要顯示的分類排成清單；名稱欄對齊，說明欄接在後面。"""
	shown = [module for key in visible for module in grouped[key]]
	width = max((len(module.NAME) for module in shown), default=0)
	blocks = []
	for key in visible:
		lines = [f"{CATEGORIES[key]}："]
		lines.extend(f"  {module.NAME:<{width}}  {module.SUMMARY}" for module in grouped[key])
		blocks.append("\n".join(lines))
	return "\n\n".join(blocks)


def render_other_categories(visible: Sequence[str]) -> str:
	"""提示還有哪些分類沒顯示、怎麼查看；全部都顯示時回傳空字串。"""
	hidden = [key for key in CATEGORIES if key not in visible]
	if not hidden:
		return ""
	parts = [f"{CATEGORIES[key]}（wkt help {key}）" for key in hidden]
	return "其他分類：" + "、".join(parts) + f"、全部（wkt help {HELP_ALL}）"


def build_parser(visible: Sequence[str] = (DEFAULT_CATEGORY,)) -> argparse.ArgumentParser:
	builtins, tools = load_commands()
	grouped = group_by_category([*tools, *builtins])

	description = "WKT 工具箱統一入口。\n\n" + render_commands(grouped, visible)
	other = render_other_categories(visible)
	if other:
		description += "\n\n" + other

	parser = WktArgumentParser(
		prog="wkt",
		usage=USAGE,
		description=description,
		epilog=EXAMPLES[visible[0] if len(visible) == 1 else DEFAULT_CATEGORY],
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("--version", action="version", version=f"wkt {__version__}")
	parser.add_argument(
		"-v",
		"--verbose",
		action="store_true",
		help=f"顯示 ffmpeg 的完整輸出，不顯示進度條（也可設定環境變數 {ui.VERBOSE_ENV}=1）",
	)
	parser.add_argument("--no-tui", action="store_true", help=f"不開啟互動選單，改印說明（也可設定環境變數 {NO_TUI_ENV}=1）")
	# 指令清單由上面的 description 負責顯示（含分類），所以子指令本身不列在 argparse 的清單裡
	subparsers = parser.add_subparsers(dest="command", metavar="<指令>", help=argparse.SUPPRESS)
	for module in (*tools, *builtins):
		sub = subparsers.add_parser(
			module.NAME,
			description=module.SUMMARY,
			formatter_class=argparse.RawDescriptionHelpFormatter,
		)
		module.configure_parser(sub)
		sub.set_defaults(handler=module.run, planner=getattr(module, "plan", None), tool_name=module.NAME)
	return parser


def show_help(topics: Sequence[str]) -> int:
	"""wkt help [分類|all]"""
	topic = topics[0].lower() if topics else DEFAULT_CATEGORY
	if topic == HELP_ALL:
		visible: tuple[str, ...] = tuple(CATEGORIES)
	elif topic in CATEGORIES:
		visible = (topic,)
	else:
		choices = "、".join([*CATEGORIES, HELP_ALL])
		print(f"wkt: 未知的說明主題：{topics[0]}（可用：{choices}）", file=sys.stderr)
		return 2
	build_parser(visible).print_help()
	return 0


def dispatch(args: argparse.Namespace, from_menu: bool) -> int:
	"""依指令類型執行：支援批次的工具走 run_batch／選單階段，其餘（menu、doctor）直接執行。"""
	if not is_batchable(args):
		args.handler(args)
		return 0
	if from_menu:
		from wkt.launcher import run_from_menu

		return run_from_menu(args.handler, args, args.tool_name)
	return run_batch(args.handler, args)


def main(argv: Sequence[str] | None = None) -> int:
	raw_args = list(sys.argv[1:] if argv is None else argv)
	from_menu = bool(raw_args) and raw_args[0] == MENU_FLAG
	if from_menu:
		raw_args = raw_args[1:]
	if raw_args and not raw_args[0].startswith("-"):
		raw_args[0] = raw_args[0].lower()  # 指令名稱不分大小寫

	if not raw_args:
		from wkt import tui

		if tui.should_launch_tui(raw_args):
			return tui.run_tui()
		build_parser().print_help()
		return 0
	if raw_args[0] == "help":
		return show_help(raw_args[1:])

	parser = build_parser()
	args = parser.parse_args(raw_args)
	if getattr(args, "handler", None) is None:  # 只給了 -v 等全域選項，沒有指令
		parser.print_help()
		return 0
	ui.set_verbose(args.verbose)
	try:
		return dispatch(args, from_menu)
	except WktError as exc:
		print(exc.message, file=sys.stderr)
		return exc.exit_code
	except KeyboardInterrupt:
		print("已中止。", file=sys.stderr)
		return 130
	except Exception as exc:
		if os.environ.get(DEBUG_ENV) == "1":
			raise
		print(f"處理失敗：{exc}", file=sys.stderr)
		return 1
