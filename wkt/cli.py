"""wkt 統一入口：把 registry 找到的指令組成 argparse 子指令並分派執行。"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from wkt import __version__
from wkt.batch import is_batchable, run_batch
from wkt.core import ui
from wkt.core.errors import WktError
from wkt.registry import load_commands


DEBUG_ENV = "WKT_DEBUG"  # 設為 1 時，未預期的例外會顯示完整 traceback
MENU_FLAG = "--from-menu"  # 右鍵選單專用：見 wkt/launcher.py

EXAMPLES = """\
範例：
  wkt toframe input.mp4
  wkt togif a.mp4 b.mp4 c.mp4      一次處理多個檔案
  wkt -v reencode input.mp4        顯示 ffmpeg 的完整輸出
  wkt doctor                       檢查執行環境
  wkt menu register                註冊右鍵選單
"""


def build_parser() -> argparse.ArgumentParser:
	builtins, tools = load_commands()

	parser = argparse.ArgumentParser(
		prog="wkt",
		description="WKT 工具箱統一入口。",
		epilog=EXAMPLES,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("--version", action="version", version=f"wkt {__version__}")
	parser.add_argument(
		"-v",
		"--verbose",
		action="store_true",
		help=f"顯示 ffmpeg 的完整輸出，不顯示進度條（也可設定環境變數 {ui.VERBOSE_ENV}=1）",
	)
	subparsers = parser.add_subparsers(dest="command", metavar="<指令>", title="可用指令")
	for module in (*tools, *builtins):
		sub = subparsers.add_parser(
			module.NAME,
			help=module.SUMMARY,
			description=module.SUMMARY,
		)
		module.configure_parser(sub)
		sub.set_defaults(handler=module.run, tool_name=module.NAME)
	return parser


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

	parser = build_parser()
	if not raw_args or raw_args[0] == "help":
		parser.print_help()
		return 0

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
