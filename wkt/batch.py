"""多檔案批次執行：對每個輸入逐一呼叫工具的 run()，最後彙整成功／失敗。"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from collections.abc import Callable
from pathlib import Path

from wkt.core import ui
from wkt.core.errors import WktError


DEBUG_ENV = "WKT_DEBUG"
OUTPUT_OPTIONS = ("output", "output_dir")


def is_batchable(args: argparse.Namespace) -> bool:
	return isinstance(getattr(args, "input", None), list)


def run_batch(run: Callable[[argparse.Namespace], None], args: argparse.Namespace) -> int:
	"""回傳結束碼：全部成功 0，只要有一個失敗就是 1。

	只有一個輸入時行為與單檔完全相同（錯誤直接往上拋，結束碼沿用）。
	"""
	inputs: list[str] = list(args.input)
	total = len(inputs)

	if total > 1 and any(getattr(args, name, None) for name in OUTPUT_OPTIONS):
		raise WktError("同時處理多個檔案時不能指定 -o／--output／--output-dir，輸出會放在各檔案旁邊。")

	if total == 1:
		single = copy.copy(args)
		single.input = inputs[0]
		run(single)
		return 0

	failures: list[tuple[str, str]] = []
	try:
		for index, raw in enumerate(inputs, start=1):
			item = copy.copy(args)
			item.input = raw
			ui.set_label(f"[{index}/{total}] {Path(raw).name}")
			print(f"[{index}/{total}] {raw}")
			try:
				run(item)
			except WktError as exc:
				print(exc.message, file=sys.stderr)
				failures.append((raw, exc.message.splitlines()[0]))
			except Exception as exc:
				if os.environ.get(DEBUG_ENV) == "1":
					raise
				print(f"處理失敗：{exc}", file=sys.stderr)
				failures.append((raw, f"處理失敗：{exc}"))
	finally:
		ui.set_label("")

	print(f"\n完成 {total - len(failures)}／{total}")
	if failures:
		print("失敗的檔案：", file=sys.stderr)
		for raw, reason in failures:
			print(f"  {raw}\n    {reason}", file=sys.stderr)
		return 1
	return 0
