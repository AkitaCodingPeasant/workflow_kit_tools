"""各工具「組 ffmpeg 指令」的純函式測試：不需要安裝 ffmpeg。"""

from __future__ import annotations

import unittest
from pathlib import Path

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


if __name__ == "__main__":
	unittest.main()
