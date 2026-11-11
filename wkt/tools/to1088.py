from __future__ import annotations

import argparse
from typing import Any

from wkt.core.errors import WktError
from wkt.core.media import add_media_arguments, load_numpy, plan_frame_tool, run_frame_tool


NAME = "to1088"
SUMMARY = "將 1920x1080 的圖片或影片補成 1920x1088"
CATEGORY = "special"

SOURCE_SIZE = (1920, 1080)
OUTPUT_SIZE = (1920, 1088)
EXTRA_ROWS = OUTPUT_SIZE[1] - SOURCE_SIZE[1]
TAG = "1088"


def extend_frame(frame: Any) -> Any:
	"""在下方複製最後一列像素 EXTRA_ROWS 次。"""
	if frame is None:
		raise WktError("無法讀取影像資料")
	np = load_numpy()
	extra = np.repeat(frame[-1:, :, ...], EXTRA_ROWS, axis=0)
	return np.concatenate([frame, extra], axis=0)


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.description = "將 1920x1080 的圖片或影片，在下方補上最後一列像素 8 次，輸出成 1920x1088。"
	add_media_arguments(parser, TAG)


def plan(args: argparse.Namespace):
	return plan_frame_tool(args, TAG)


def run(args: argparse.Namespace) -> None:
	run_frame_tool(args, tag=TAG, frame_fn=extend_frame, expected_size=SOURCE_SIZE, output_size=OUTPUT_SIZE)
