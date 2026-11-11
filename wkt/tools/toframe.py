from __future__ import annotations

import argparse
import re
from pathlib import Path

from wkt.core.args import add_input_argument
from wkt.core.errors import WktError
from wkt.core.ffmpeg import find_ffmpeg, probe_duration, run_ffmpeg
from wkt.core.paths import ensure_output_available, require_input_file


NAME = "toframe"
SUMMARY = "將影片拆幀成 PNG"
CATEGORY = "general"

FRAME_PATTERN = "%06d.png"
FRAME_NAME_RE = re.compile(r"^\d{6}\.png$", re.IGNORECASE)


def build_output_dir(input_path: Path, output_arg: str | None, out_dir: str | None = None) -> Path:
	if output_arg and out_dir:
		raise WktError("-o／--output-dir 與 --out-dir 不能同時指定")
	if output_arg:
		return Path(output_arg).expanduser()
	if out_dir:
		return Path(out_dir).expanduser() / input_path.stem
	return input_path.with_name(input_path.stem)


def ensure_output_dir(output_dir: Path, force: bool = False) -> None:
	ensure_output_available(output_dir, force, directory=True)
	if force and output_dir.exists():
		unrelated = [path for path in output_dir.iterdir() if not path.is_file() or not FRAME_NAME_RE.match(path.name)]
		if unrelated:
			raise WktError(f"輸出資料夾含有非拆幀檔案，無法安全覆蓋：{output_dir}")
		for path in output_dir.iterdir():
			path.unlink()
	output_dir.mkdir(parents=True, exist_ok=True)


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
	add_input_argument(parser, "輸入影片路徑")
	parser.add_argument("-o", "--output-dir", help="輸出資料夾；未指定時會使用同層同名資料夾")
	parser.add_argument(
		"--709",
		dest="force_rec709",
		action="store_true",
		help="不依來源色彩標記，強制使用 Rec.709 矩陣並標記輸出 PNG",
	)


def plan(args: argparse.Namespace) -> Path:
	input_path = require_input_file(args.input)
	output_dir = build_output_dir(input_path, args.output_dir, args.out_dir)
	ensure_output_available(output_dir, args.force, directory=True)
	if args.force and output_dir.exists() and any(
		(not path.is_file() or not FRAME_NAME_RE.match(path.name)) for path in output_dir.iterdir()
	):
		raise WktError(f"輸出資料夾含有非拆幀檔案，無法安全覆蓋：{output_dir}")
	return output_dir


def run(args: argparse.Namespace) -> None:
	output_dir = plan(args)
	input_path = require_input_file(args.input)
	ffmpeg_path = find_ffmpeg()

	ensure_output_dir(output_dir, args.force)
	run_ffmpeg(
		build_ffmpeg_command(ffmpeg_path, input_path, output_dir, args.force_rec709),
		duration=probe_duration(ffmpeg_path, input_path),
	)
	print(f"完成：{output_dir} ({count_output_frames(output_dir)} 幀)")
