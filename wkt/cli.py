"""wkt 統一入口：把 registry 找到的指令組成 argparse 子指令並分派執行。"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from wkt import __version__
from wkt.core.errors import WktError
from wkt.registry import load_commands


DEBUG_ENV = "WKT_DEBUG"  # 設為 1 時，未預期的例外會顯示完整 traceback

EXAMPLES = """\
範例：
  wkt toframe input.mp4
  wkt to1080 input.mp4
  wkt togif input.mp4 --fps 12
  wkt menu register
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
	subparsers = parser.add_subparsers(dest="command", metavar="<指令>", title="可用指令")
	for module in (*tools, *builtins):
		sub = subparsers.add_parser(
			module.NAME,
			help=module.SUMMARY,
			description=module.SUMMARY,
		)
		module.configure_parser(sub)
		sub.set_defaults(handler=module.run)
	return parser


def main(argv: Sequence[str] | None = None) -> int:
	raw_args = list(sys.argv[1:] if argv is None else argv)
	if raw_args and not raw_args[0].startswith("-"):
		raw_args[0] = raw_args[0].lower()  # 指令名稱不分大小寫

	parser = build_parser()
	if not raw_args or raw_args[0] == "help":
		parser.print_help()
		return 0

	args = parser.parse_args(raw_args)
	try:
		args.handler(args)
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
	return 0
