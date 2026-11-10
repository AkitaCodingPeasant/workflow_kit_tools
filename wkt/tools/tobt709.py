from __future__ import annotations

import argparse
from pathlib import Path

from wkt.core.args import add_input_argument
from wkt.core.ffmpeg import find_ffmpeg, probe_duration, run_ffmpeg
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


NAME = "tobt709"
SUMMARY = "將影片從 BT.601 色域轉成 BT.709"
CATEGORY = "special"

DEFAULT_INPUT_STANDARD = "smpte170m"
INPUT_STANDARDS = ("smpte170m", "bt470bg", "bt601-6-525", "bt601-6-625")
OUTPUT_STANDARD = "bt709"
TAG = "bt709"


def build_ffmpeg_command(
	ffmpeg_path: str,
	input_path: Path,
	output_path: Path,
	input_standard: str,
	crf: int,
	preset: str,
) -> list[str]:
	filter_arg = f"colorspace=iall={input_standard}:all={OUTPUT_STANDARD}:format=yuv420p"
	return [
		ffmpeg_path,
		"-hide_banner",
		"-y",
		"-i",
		str(input_path),
		"-map",
		"0:v:0",
		"-map",
		"0:a?",
		"-vf",
		filter_arg,
		"-c:v",
		"libx264",
		"-crf",
		str(crf),
		"-preset",
		preset,
		"-c:a",
		"copy",
		"-color_primaries",
		OUTPUT_STANDARD,
		"-color_trc",
		OUTPUT_STANDARD,
		"-colorspace",
		OUTPUT_STANDARD,
		"-movflags",
		"+faststart",
		str(output_path),
	]


def configure_parser(parser: argparse.ArgumentParser) -> None:
	add_input_argument(parser, "輸入影片路徑")
	parser.add_argument("-o", "--output", help=f"輸出路徑；未指定時會自動加上 _{TAG}")
	parser.add_argument(
		"--input-standard",
		choices=INPUT_STANDARDS,
		default=DEFAULT_INPUT_STANDARD,
		help=f"BT.601 來源標準，預設 {DEFAULT_INPUT_STANDARD}",
	)
	parser.add_argument("--crf", type=int, default=18, help="H.264 品質，數字越小品質越高，預設 18")
	parser.add_argument("--preset", default="medium", help="x264 preset，預設 medium")


def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	output_path = derive_output(input_path, args.output, tag=TAG)
	ensure_not_same(input_path, output_path)

	ffmpeg_path = find_ffmpeg()
	command = build_ffmpeg_command(
		ffmpeg_path=ffmpeg_path,
		input_path=input_path,
		output_path=output_path,
		input_standard=args.input_standard,
		crf=args.crf,
		preset=args.preset,
	)
	run_ffmpeg(command, duration=probe_duration(ffmpeg_path, input_path))
	print(f"完成：{output_path}")
