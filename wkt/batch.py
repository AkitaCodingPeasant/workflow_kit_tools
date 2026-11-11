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
from wkt.core.paths import output_status


DEBUG_ENV = "WKT_DEBUG"
OUTPUT_OPTIONS = ("output", "output_dir")


def is_batchable(args: argparse.Namespace) -> bool:
	return isinstance(getattr(args, "input", None), list)


def preview_output(planner: Callable[[argparse.Namespace], Path], item: argparse.Namespace) -> tuple[Path, str, bool]:
	"""預覽既有輸出，但不因缺少 --force 而隱藏目標路徑。"""
	preview = copy.copy(item)
	preview.force = True
	output = Path(planner(preview))
	status = output_status(output)
	conflict = status == "覆蓋" and not getattr(item, "force", False)
	return output, "衝突（需 --force）" if conflict else status, conflict


def run_batch(run: Callable[[argparse.Namespace], None], args: argparse.Namespace) -> int:
	"""回傳結束碼：全部成功 0，只要有一個失敗就是 1。

	只有一個輸入時行為與單檔完全相同（錯誤直接往上拋，結束碼沿用）。
	"""
	inputs: list[str] = list(args.input)
	total = len(inputs)

	if total > 1 and any(getattr(args, name, None) for name in OUTPUT_OPTIONS):
		raise WktError("同時處理多個檔案時不能指定 -o／--output／--output-dir；請改用 --out-dir。")

	planner = getattr(args, "planner", None)
	dry_run = getattr(args, "dry_run", False)
	if dry_run and planner is None:
		raise WktError("此指令不支援 --dry-run")
	if planner is not None:
		# 先擋掉同名輸出及輸出碰到批次中另一個輸入的情況，避免 --force 造成資料損失。
		seen: dict[Path, str] = {}
		input_paths = {Path(raw).expanduser().resolve() for raw in inputs}
		for raw in inputs:
			item = copy.copy(args)
			item.input = raw
			try:
				check = copy.copy(item)
				if dry_run:
					check.force = True
				output = Path(planner(check)).resolve()
			except WktError:
				continue  # 錯誤由逐檔流程回報，不影響其他檔案
			if output in input_paths and not dry_run:
				raise WktError(f"輸出路徑與批次輸入檔案衝突：{output}")
			if output in seen and not dry_run:
				raise WktError(f"批次輸出路徑重複：{output}（{seen[output]}、{raw}）")
			seen[output] = raw

	if total == 1:
		single = copy.copy(args)
		single.input = inputs[0]
		if dry_run:
			output, status, conflict = preview_output(planner, single)
			print(f"預覽：{single.input} → {output}（{status}）")
			return 1 if conflict else 0
		else:
			run(single)
		return 0

	failures: list[tuple[str, str]] = []
	preview_seen: set[Path] = set()
	try:
		for index, raw in enumerate(inputs, start=1):
			item = copy.copy(args)
			item.input = raw
			ui.set_label(f"[{index}/{total}] {Path(raw).name}")
			print(f"[{index}/{total}] {raw}")
			try:
				if dry_run:
					output, status, conflict = preview_output(planner, item)
					key = output.resolve()
					if key in preview_seen:
						status, conflict = "衝突（批次輸出重複）", True
					elif key in input_paths:
						status, conflict = "衝突（與批次輸入相同）", True
					preview_seen.add(key)
					print(f"  → {output}（{status}）")
					if conflict:
						failures.append((raw, f"{status}：{output}"))
				else:
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

	print(f"\n{'預覽' if dry_run else '完成'} {total - len(failures)}／{total}")
	if failures:
		print("失敗的檔案：", file=sys.stderr)
		for raw, reason in failures:
			print(f"  {raw}\n    {reason}", file=sys.stderr)
		return 1
	return 0
