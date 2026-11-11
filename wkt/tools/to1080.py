from __future__ import annotations

import argparse
from typing import Any

from wkt.core.errors import WktError
from wkt.core.media import add_media_arguments, plan_frame_tool, run_frame_tool


NAME = "to1080"
SUMMARY = "將 1920x1088 的圖片或影片裁成 1920x1080"
CATEGORY = "special"

SOURCE_SIZE = (1920, 1088)
OUTPUT_SIZE = (1920, 1080)
EXTRA_ROWS = SOURCE_SIZE[1] - OUTPUT_SIZE[1]
TAG = "1080"


def crop_frame(frame: Any) -> Any:
	"""裁掉最下方 EXTRA_ROWS 列。"""
	if frame is None:
		raise WktError("無法讀取影像資料")
	return frame[:-EXTRA_ROWS, :, ...]


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.description = "將 1920x1088 的圖片或影片，裁掉最下方 8px，輸出成 1920x1080。"
	add_media_arguments(parser, TAG)


def plan(args: argparse.Namespace):
	return plan_frame_tool(args, TAG)


def run(args: argparse.Namespace) -> None:
	run_frame_tool(args, tag=TAG, frame_fn=crop_frame, expected_size=SOURCE_SIZE, output_size=OUTPUT_SIZE)
