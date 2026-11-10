from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from pathlib import Path

from wkt.core.errors import WktError
from wkt.core.args import add_input_argument
from wkt.core.ffmpeg import find_ffmpeg, parse_timecode, probe_duration, run_ffmpeg
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


NAME = "togif"
SUMMARY = "將影片壓成小尺寸 GIF"

DEFAULT_FPS = 10
DEFAULT_WIDTH = 480
DEFAULT_COLORS = 96


def build_video_filter(fps: int, width: int, colors: int) -> str:
	scale_expr = f"scale='min({width}\\,iw)':-2:flags=lanczos"
	return (
		f"[0:v]fps={fps},{scale_expr},split[a][b];"
		f"[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
		"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle[gif]"
	)


def build_ffmpeg_command(
	ffmpeg_path: str,
	input_path: Path,
	fps: int,
	width: int,
	colors: int,
	start: str | None,
	duration: str | None,
) -> list[str]:
	"""輸出到 stdout（"-"）；由 run() 負責把 stdout 導向暫存檔。"""
	command = [ffmpeg_path, "-hide_banner", "-y"]
	if start:
		command.extend(["-ss", start])
	command.extend(["-i", str(input_path)])
	if duration:
		command.extend(["-t", duration])
	command.extend(
		[
			"-filter_complex",
			build_video_filter(fps=fps, width=width, colors=colors),
			"-map",
			"[gif]",
			"-loop",
			"0",
			"-f",
			"gif",
			"-",
		]
	)
	return command


def validate_args(args: argparse.Namespace) -> None:
	if args.fps <= 0:
		raise WktError("--fps 必須大於 0")
	if args.width <= 0:
		raise WktError("--width 必須大於 0")
	if not 2 <= args.colors <= 256:
		raise WktError("--colors 必須介於 2 到 256")


def build_temp_output_path(output_path: Path) -> Path:
	return output_path.with_name(f".{output_path.stem}.{uuid.uuid4().hex}.tmp.gif")


def pick_writable_output_path(output_path: Path) -> tuple[Path, str | None]:
	"""確認輸出資料夾可寫；不行就改輸出到系統暫存資料夾，並回傳提示訊息。"""
	probe_path = build_temp_output_path(output_path)
	try:
		output_path.parent.mkdir(parents=True, exist_ok=True)
		with probe_path.open("wb"):
			pass
		probe_path.unlink()
		return output_path, None
	except OSError as exc:
		probe_path.unlink(missing_ok=True)
		fallback_path = Path(tempfile.gettempdir()) / output_path.name
		return fallback_path, f"無法寫入原輸出資料夾，改輸出到暫存資料夾：{exc}"


def expected_duration(ffmpeg_path: str, input_path: Path, args: argparse.Namespace) -> float | None:
	"""輸出的預期長度（秒），用來顯示進度；有 --duration 以它為準，否則為「全長 − --start」。"""
	trimmed = parse_timecode(args.duration)
	if trimmed:
		return trimmed
	total = probe_duration(ffmpeg_path, input_path)
	if total is None:
		return None
	return max(total - (parse_timecode(args.start) or 0.0), 0.0) or None


def configure_parser(parser: argparse.ArgumentParser) -> None:
	add_input_argument(parser, "輸入影片路徑")
	parser.add_argument("-o", "--output", help="輸出 GIF 路徑；未指定時會使用同層同名 .gif")
	parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help=f"GIF fps，預設 {DEFAULT_FPS}")
	parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"最大寬度，預設 {DEFAULT_WIDTH}")
	parser.add_argument("--colors", type=int, default=DEFAULT_COLORS, help=f"調色盤顏色數，預設 {DEFAULT_COLORS}")
	parser.add_argument("--start", help="開始時間，例如 00:00:03 或 3")
	parser.add_argument("--duration", help="長度，例如 5 或 00:00:05")


def run(args: argparse.Namespace) -> None:
	validate_args(args)
	input_path = require_input_file(args.input).resolve()

	output_path = derive_output(input_path, args.output, suffix=".gif")
	if output_path.suffix.lower() != ".gif":
		output_path = output_path.with_suffix(".gif")
	output_path = output_path.resolve()
	ensure_not_same(input_path, output_path)

	ffmpeg_path = find_ffmpeg()
	output_path, fallback_message = pick_writable_output_path(output_path)
	if fallback_message:
		print(fallback_message, file=sys.stderr)

	temp_output_path = build_temp_output_path(output_path)
	command = build_ffmpeg_command(
		ffmpeg_path=ffmpeg_path,
		input_path=input_path,
		fps=args.fps,
		width=args.width,
		colors=args.colors,
		start=args.start,
		duration=args.duration,
	)
	try:
		with temp_output_path.open("wb") as output_file:
			run_ffmpeg(command, stdout=output_file, duration=expected_duration(ffmpeg_path, input_path, args))
		output_path.unlink(missing_ok=True)
		temp_output_path.replace(output_path)
	finally:
		temp_output_path.unlink(missing_ok=True)

	print(f"完成：{output_path}")
