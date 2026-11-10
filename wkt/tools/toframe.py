from __future__ import annotations

import argparse
import re
from pathlib import Path

from wkt.core.errors import WktError
from wkt.core.ffmpeg import find_ffmpeg, run_ffmpeg
from wkt.core.paths import require_input_file


NAME = "toframe"
SUMMARY = "將影片拆幀成 PNG"

FRAME_PATTERN = "%06d.png"
FRAME_NAME_RE = re.compile(r"^\d{6}\.png$", re.IGNORECASE)


def build_output_dir(input_path: Path, output_arg: str | None) -> Path:
	if output_arg:
		return Path(output_arg).expanduser()
	return input_path.with_name(input_path.stem)


def ensure_output_dir(output_dir: Path) -> None:
	if output_dir.exists():
		if not output_dir.is_dir():
			raise WktError(f"輸出路徑已存在但不是資料夾：{output_dir}")
		if any(output_dir.iterdir()):
			raise WktError(f"輸出資料夾已存在且不是空的：{output_dir}")
	else:
		output_dir.mkdir(parents=True)


def build_ffmpeg_command(
	ffmpeg_path: str,
	input_path: Path,
	output_dir: Path,
	force_rec709: bool = False,
) -> list[str]:
	command = [
		ffmpeg_path,
		"-hide_banner",
		"-y",
		"-i",
		str(input_path),
		"-map",
		"0:v:0",
	]
	if force_rec709:
		command.extend([
			"-vf",
			"scale=in_color_matrix=bt709,format=rgb24,"
			"setparams=range=full:color_primaries=bt709:color_trc=bt709:colorspace=gbr",
		])
	command.extend([
		"-fps_mode",
		"passthrough",
		"-start_number",
		"0",
		str(output_dir / FRAME_PATTERN),
	])
	return command


def count_output_frames(output_dir: Path) -> int:
	return sum(1 for path in output_dir.iterdir() if path.is_file() and FRAME_NAME_RE.match(path.name))


def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.description = "將影片拆幀成 PNG，輸出到同層同名資料夾。"
	parser.add_argument("input", help="輸入影片路徑")
	parser.add_argument("-o", "--output-dir", help="輸出資料夾；未指定時會使用同層同名資料夾")
	parser.add_argument(
		"--709",
		dest="force_rec709",
		action="store_true",
		help="不依來源色彩標記，強制使用 Rec.709 矩陣並標記輸出 PNG",
	)


def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	output_dir = build_output_dir(input_path, args.output_dir)
	ffmpeg_path = find_ffmpeg()

	ensure_output_dir(output_dir)
	run_ffmpeg(build_ffmpeg_command(ffmpeg_path, input_path, output_dir, args.force_rec709))
	print(f"完成：{output_dir} ({count_output_frames(output_dir)} 幀)")
