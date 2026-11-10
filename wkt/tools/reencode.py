from __future__ import annotations

import argparse
from pathlib import Path

from wkt.core.args import add_input_argument
from wkt.core.ffmpeg import find_ffmpeg, probe_duration, run_ffmpeg
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


NAME = "reencode"
SUMMARY = "將影片重新編碼成 H.264/AAC"
CATEGORY = "general"

TAG = "reencoded"


def build_ffmpeg_command(
	ffmpeg_path: str,
	input_path: Path,
	output_path: Path,
	crf: int,
	preset: str,
	audio_bitrate: str,
) -> list[str]:
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
		"-c:v",
		"libx264",
		"-crf",
		str(crf),
		"-preset",
		preset,
		"-pix_fmt",
		"yuv420p",
		"-c:a",
		"aac",
		"-b:a",
		audio_bitrate,
		"-movflags",
		"+faststart",
		str(output_path),
	]


def configure_parser(parser: argparse.ArgumentParser) -> None:
	add_input_argument(parser, "輸入影片路徑")
	parser.add_argument("-o", "--output", help=f"輸出路徑；未指定時會自動加上 _{TAG}")
	parser.add_argument("--crf", type=int, default=18, help="H.264 品質，數字越小品質越高，預設 18")
	parser.add_argument("--preset", default="medium", help="x264 preset，預設 medium")
	parser.add_argument("--audio-bitrate", default="192k", help="AAC 音訊位元率，預設 192k")


def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	output_path = derive_output(input_path, args.output, tag=TAG)
	ensure_not_same(input_path, output_path)

	ffmpeg_path = find_ffmpeg()
	command = build_ffmpeg_command(
		ffmpeg_path=ffmpeg_path,
		input_path=input_path,
		output_path=output_path,
		crf=args.crf,
		preset=args.preset,
		audio_bitrate=args.audio_bitrate,
	)
	run_ffmpeg(command, duration=probe_duration(ffmpeg_path, input_path))
	print(f"完成：{output_path}")
