from __future__ import annotations

import argparse
from pathlib import Path

from wkt.core.args import add_input_argument
from wkt.core.errors import WktError
from wkt.core.ffmpeg import find_ffmpeg, run_ffmpeg
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


NAME = "topng"
SUMMARY = "將 .webp、.jpg 等圖片轉換成 PNG"
CATEGORY = "general"

OUTPUT_SUFFIX = ".png"


def build_ffmpeg_command(ffmpeg_path: str, input_path: Path, output_path: Path) -> list[str]:
	"""只取第一幀（動態 webp／gif 也只輸出第一張）；有透明度的圖片會保留 alpha。"""
	return [
		ffmpeg_path,
		"-hide_banner",
		"-y",
		"-i",
		str(input_path),
		"-frames:v",
		"1",
		"-update",
		"1",
		str(output_path),
	]


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.description = "將 .webp、.jpg、.jpeg、.bmp、.tiff 等圖片轉換成 PNG；動態圖片只轉第一幀。"
	add_input_argument(parser, "輸入圖片路徑")
	parser.add_argument("-o", "--output", help="輸出路徑；未指定時會使用同層同名 .png")
	parser.add_argument("-f", "--force", action="store_true", help="輸出檔案已存在時直接覆蓋")


def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	if input_path.suffix.lower() == OUTPUT_SUFFIX and not args.output:
		raise WktError(f"輸入已經是 PNG，不需要轉換：{input_path}")

	output_path = derive_output(input_path, args.output, suffix=OUTPUT_SUFFIX)
	if output_path.suffix.lower() != OUTPUT_SUFFIX:
		output_path = output_path.with_suffix(OUTPUT_SUFFIX)
	ensure_not_same(input_path, output_path)
	if output_path.exists() and not args.force:
		raise WktError(f"輸出檔案已存在：{output_path}（加上 --force 可覆蓋）")

	output_path.parent.mkdir(parents=True, exist_ok=True)
	run_ffmpeg(build_ffmpeg_command(find_ffmpeg(), input_path, output_path))
	print(f"完成：{output_path}")
