"""各工具「組 ffmpeg 指令」的純函式測試：不需要安裝 ffmpeg。"""

from __future__ import annotations

import argparse
import contextlib
import io
import unittest
from pathlib import Path

from wkt.core.errors import WktError
from wkt.core.profiles import apply_profile
from wkt.tools import reencode, toframe, togif, tobt709, topng


FFMPEG = "ffmpeg"
SRC = Path("in.mp4")
DST = Path("out.mp4")


class CommandTests(unittest.TestCase):
	def test_reencode(self) -> None:
		cmd = reencode.build_ffmpeg_command(FFMPEG, SRC, DST, crf=20, preset="fast", audio_bitrate="128k")
		self.assertEqual(cmd[0], FFMPEG)
		self.assertEqual(cmd[-1], str(DST))
		self.assertIn("libx264", cmd)
		self.assertEqual(cmd[cmd.index("-crf") + 1], "20")
		self.assertEqual(cmd[cmd.index("-b:a") + 1], "128k")

	def test_tobt709(self) -> None:
		cmd = tobt709.build_ffmpeg_command(FFMPEG, SRC, DST, "smpte170m", 18, "medium")
		self.assertIn("colorspace=iall=smpte170m:all=bt709:format=yuv420p", cmd)
		self.assertEqual(cmd[cmd.index("-colorspace") + 1], "bt709")

	def test_toframe_default_and_709(self) -> None:
		plain = toframe.build_ffmpeg_command(FFMPEG, SRC, Path("frames"))
		self.assertNotIn("-vf", plain)
		self.assertEqual(plain[-1], str(Path("frames") / "%06d.png"))
		forced = toframe.build_ffmpeg_command(FFMPEG, SRC, Path("frames"), force_rec709=True)
		self.assertIn("-vf", forced)

	def test_topng_takes_single_frame(self) -> None:
		cmd = topng.build_ffmpeg_command(FFMPEG, Path("in.webp"), Path("in.png"))
		self.assertEqual(cmd[cmd.index("-frames:v") + 1], "1")
		self.assertEqual(cmd[-1], "in.png")

	def test_togif_trim_options_are_optional(self) -> None:
		plain = togif.build_ffmpeg_command(FFMPEG, SRC, 10, 480, 96, None, None)
		self.assertNotIn("-ss", plain)
		self.assertNotIn("-t", plain)
		self.assertEqual(plain[-1], "-")
		trimmed = togif.build_ffmpeg_command(FFMPEG, SRC, 10, 480, 96, "3", "5")
		self.assertEqual(trimmed[trimmed.index("-ss") + 1], "3")
		self.assertEqual(trimmed[trimmed.index("-t") + 1], "5")

	def test_togif_filter_mentions_fps_width_colors(self) -> None:
		video_filter = togif.build_video_filter(12, 320, 64)
		self.assertIn("fps=12", video_filter)
		self.assertIn("320", video_filter)
		self.assertIn("max_colors=64", video_filter)


def togif_args(*argv: str) -> argparse.Namespace:
	parser = argparse.ArgumentParser()
	togif.configure_parser(parser)
	args = parser.parse_args([str(SRC), *argv])
	apply_profile(args, togif.PROFILES, togif.DEFAULT_PROFILE)
	return args


class TogifProfileTests(unittest.TestCase):
	def test_default_is_standard(self) -> None:
		args = togif_args()
		self.assertEqual((args.fps, args.width, args.colors), (10, 480, 96))

	def test_profile_applies_all_values(self) -> None:
		args = togif_args("--profile", "small")
		self.assertEqual((args.fps, args.width, args.colors), (8, 320, 64))

	def test_explicit_option_overrides_profile(self) -> None:
		args = togif_args("-p", "small", "--fps", "15")
		self.assertEqual((args.fps, args.width, args.colors), (15, 320, 64))

	def test_explicit_value_equal_to_default_still_wins(self) -> None:
		args = togif_args("--profile", "high", "--fps", "10")
		self.assertEqual(args.fps, 10)

	def test_unknown_profile_is_rejected(self) -> None:
		with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
			togif_args("--profile", "huge")


class TogifMaxSizeTests(unittest.TestCase):
	def test_parse_size(self) -> None:
		self.assertEqual(togif.parse_size("8MB"), 8 * 1024**2)
		self.assertEqual(togif.parse_size("500k"), 500 * 1024)
		self.assertEqual(togif.parse_size("2.5 m"), int(2.5 * 1024**2))

	def test_parse_size_rejects_bad_input(self) -> None:
		for text in ("8", "abc", "-1MB", "0KB", ""):
			with self.subTest(text=text), self.assertRaises(WktError):
				togif.parse_size(text)

	def test_validate_rejects_bad_max_size(self) -> None:
		with self.assertRaises(WktError):
			togif.validate_args(togif_args("--max-size", "big"))

	def test_next_settings_shrinks_width_first(self) -> None:
		fps, width, colors = togif.next_settings(10, 480, 96, actual=4_000_000, target=1_000_000)
		self.assertEqual(fps, 10)
		self.assertEqual(colors, 96)
		self.assertLess(width, 480)
		self.assertEqual(width % 2, 0)

	def test_next_settings_then_fps_then_colors_then_gives_up(self) -> None:
		fps, width, colors = togif.next_settings(10, togif.MIN_WIDTH, 96, 2_000_000, 1_000_000)
		self.assertEqual((width, colors), (togif.MIN_WIDTH, 96))
		self.assertLess(fps, 10)
		_, _, colors = togif.next_settings(togif.MIN_FPS, togif.MIN_WIDTH, 96, 2_000_000, 1_000_000)
		self.assertEqual(colors, 48)
		self.assertIsNone(
			togif.next_settings(togif.MIN_FPS, togif.MIN_WIDTH, togif.MIN_COLORS, 2_000_000, 1_000_000)
		)


if __name__ == "__main__":
	unittest.main()
