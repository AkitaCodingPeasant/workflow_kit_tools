from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

from wkt.core.errors import WktError
from wkt.core.args import add_input_argument
from wkt.core.profiles import apply_profile, describe_profiles
from wkt.core.ffmpeg import find_ffmpeg, parse_timecode, probe_duration, run_ffmpeg
from wkt.core.paths import derive_output, ensure_not_same, ensure_output_available, require_input_file


NAME = "togif"
SUMMARY = "將影片壓成小尺寸 GIF"
CATEGORY = "general"

PROFILES = {
	"small": {"fps": 8, "width": 320, "colors": 64},
	"standard": {"fps": 10, "width": 480, "colors": 96},
	"high": {"fps": 15, "width": 720, "colors": 256},
}
DEFAULT_PROFILE = "standard"

# --max-size 自動降規格時的下限與嘗試次數
MIN_WIDTH = 96
MIN_FPS = 5
MIN_COLORS = 16
MAX_ATTEMPTS = 8
SAFETY_FACTOR = 0.92  # 預估縮小比例時多留一點餘裕，減少重試次數

SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(b|kb?|mb?|gb?)\s*$", re.IGNORECASE)
SIZE_UNITS = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}


def parse_size(text: str) -> int:
	"""'8MB'、'500k'、'2.5m' → 位元組數（以 1024 進位）；必須帶單位以免誤判。"""
	match = SIZE_RE.match(text)
	if not match:
		raise WktError(f"--max-size 格式錯誤：{text!r}（範例：8MB、500KB、2.5m）")
	size = int(float(match.group(1)) * SIZE_UNITS[match.group(2)[0].lower()])
	if size <= 0:
		raise WktError("--max-size 必須大於 0")
	return size


def format_size(size: int) -> str:
	value = float(size)
	for unit in ("B", "KB", "MB"):
		if value < 1024:
			return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
		value /= 1024
	return f"{value:.1f} GB"


def next_settings(
	fps: int, width: int, colors: int, actual: int, target: int
) -> tuple[int, int, int] | None:
	"""檔案超過上限時，決定下一輪的 (fps, width, colors)；已到下限、無法再縮時回傳 None。

	順序：先縮寬度（對檔案大小影響最大，GIF 大小約與像素數成正比）→ 再降 fps → 最後減少顏色。
	"""
	ratio = target / actual
	if width > MIN_WIDTH:
		scaled = int(width * (ratio**0.5) * SAFETY_FACTOR) // 2 * 2
		return fps, max(scaled, MIN_WIDTH), colors
	if fps > MIN_FPS:
		return max(int(fps * ratio * SAFETY_FACTOR), MIN_FPS), width, colors
	if colors > MIN_COLORS:
		return fps, width, max(colors // 2, MIN_COLORS)
	return None


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
	if args.max_size:
		parse_size(args.max_size)


def build_temp_output_path(output_path: Path) -> Path:
	return output_path.with_name(f".{output_path.stem}.{uuid.uuid4().hex}.tmp.gif")


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
	parser.epilog = (
		"預設組（--profile）：\n"
		+ describe_profiles(PROFILES, DEFAULT_PROFILE)
		+ "\n單項參數（--fps／--width／--colors）會覆寫預設組的對應值。\n"
		"--max-size 會在超過上限時自動依序縮小寬度、降低 fps、減少顏色後重試。"
	)
	parser.formatter_class = argparse.RawDescriptionHelpFormatter
	add_input_argument(parser, "輸入影片路徑")
	parser.add_argument("-o", "--output", help="輸出 GIF 路徑；未指定時會使用同層同名 .gif")
	parser.add_argument(
		"-p", "--profile", choices=list(PROFILES), help=f"預設組，預設 {DEFAULT_PROFILE}（內容見下方）"
	)
	parser.add_argument("--fps", type=int, help="GIF fps（預設依預設組）")
	parser.add_argument("--width", type=int, help="最大寬度（預設依預設組）")
	parser.add_argument("--colors", type=int, help="調色盤顏色數（預設依預設組）")
	parser.add_argument("--max-size", help="輸出檔案大小上限，例如 8MB、500KB；超過時自動降規格重試")
	parser.add_argument("--start", help="開始時間，例如 00:00:03 或 3")
	parser.add_argument("--duration", help="長度，例如 5 或 00:00:05")


def plan(args: argparse.Namespace) -> Path:
	apply_profile(args, PROFILES, DEFAULT_PROFILE)
	validate_args(args)
	input_path = require_input_file(args.input).resolve()

	output_path = derive_output(input_path, args.output, suffix=".gif", out_dir=args.out_dir)
	if output_path.suffix.lower() != ".gif":
		output_path = output_path.with_suffix(".gif")
	output_path = output_path.resolve()
	ensure_not_same(input_path, output_path)
	ensure_output_available(output_path, args.force)
	return output_path


def run(args: argparse.Namespace) -> None:
	output_path = plan(args)
	input_path = require_input_file(args.input).resolve()
	ffmpeg_path = find_ffmpeg()
	output_path.parent.mkdir(parents=True, exist_ok=True)

	target = parse_size(args.max_size) if args.max_size else None
	duration = expected_duration(ffmpeg_path, input_path, args)
	fps, width, colors = args.fps, args.width, args.colors

	temp_output_path = build_temp_output_path(output_path)
	try:
		for attempt in range(1, MAX_ATTEMPTS + 1):
			command = build_ffmpeg_command(
				ffmpeg_path=ffmpeg_path,
				input_path=input_path,
				fps=fps,
				width=width,
				colors=colors,
				start=args.start,
				duration=args.duration,
			)
			with temp_output_path.open("wb") as output_file:
				run_ffmpeg(command, stdout=output_file, duration=duration)
			actual = temp_output_path.stat().st_size
			if target is None or actual <= target:
				break
			print(
				f"第 {attempt} 次：{format_size(actual)} 超過上限 {format_size(target)}"
				f"（fps={fps} width={width} colors={colors}）",
				file=sys.stderr,
			)
			following = next_settings(fps, width, colors, actual, target) if attempt < MAX_ATTEMPTS else None
			if following is None:
				raise WktError(
					f"無法壓到 {format_size(target)} 以下（最後一次 {format_size(actual)}）。"
					"請改用較短的 --duration、或放寬 --max-size。"
				)
			fps, width, colors = following
		temp_output_path.replace(output_path)
	finally:
		temp_output_path.unlink(missing_ok=True)

	print(f"完成：{output_path}（{format_size(output_path.stat().st_size)}）")
