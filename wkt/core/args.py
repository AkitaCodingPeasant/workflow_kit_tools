from __future__ import annotations

import argparse


def add_input_argument(parser: argparse.ArgumentParser, help_text: str) -> None:
	"""所有工具共用的輸入參數：一個或多個檔案。

	工具的 run(args) 仍然只會拿到「單一」檔案：args.input 是字串。
	多檔案由 wkt.batch 在外層逐一呼叫 run()，工具本身不需要處理批次。
	"""
	parser.add_argument("input", nargs="+", metavar="input", help=f"{help_text}（可指定多個）")
