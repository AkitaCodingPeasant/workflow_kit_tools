from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wkt.core.errors import WktError
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


class PathsTests(unittest.TestCase):
	def setUp(self) -> None:
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.tmp = Path(self._tmp.name)

	def test_require_input_file_ok(self) -> None:
		path = self.tmp / "a.mp4"
		path.write_bytes(b"")
		self.assertEqual(require_input_file(str(path)), path)

	def test_require_input_file_missing(self) -> None:
		with self.assertRaises(WktError) as ctx:
			require_input_file(str(self.tmp / "nope.mp4"))
		self.assertIn("找不到輸入檔案", ctx.exception.message)

	def test_require_input_file_directory(self) -> None:
		with self.assertRaises(WktError) as ctx:
			require_input_file(str(self.tmp))
		self.assertIn("不是檔案", ctx.exception.message)

	def test_derive_output_default_tag_keeps_suffix(self) -> None:
		self.assertEqual(derive_output(Path("x/a.mp4"), None, tag="1080"), Path("x/a_1080.mp4"))

	def test_derive_output_new_suffix(self) -> None:
		self.assertEqual(derive_output(Path("x/a.mp4"), None, suffix=".gif"), Path("x/a.gif"))

	def test_derive_output_explicit_wins(self) -> None:
		self.assertEqual(derive_output(Path("x/a.mp4"), "out/b.mp4", tag="1080"), Path("out/b.mp4"))

	def test_ensure_not_same(self) -> None:
		path = self.tmp / "a.mp4"
		with self.assertRaises(WktError):
			ensure_not_same(path, path)
		ensure_not_same(path, self.tmp / "b.mp4")


class ProgressAndTimeTests(unittest.TestCase):
	def test_parse_timecode(self) -> None:
		from wkt.core.ffmpeg import parse_timecode

		self.assertEqual(parse_timecode("3"), 3.0)
		self.assertEqual(parse_timecode("00:00:05"), 5.0)
		self.assertEqual(parse_timecode("1:02.5"), 62.5)
		self.assertIsNone(parse_timecode(None))
		self.assertIsNone(parse_timecode("abc"))

	def test_progress_seconds_parsing(self) -> None:
		from wkt.core.ffmpeg import _progress_seconds

		self.assertEqual(_progress_seconds("out_time_us=1500000"), 1.5)
		self.assertEqual(_progress_seconds("out_time_ms=2000000"), 2.0)  # 名稱是 ms 但單位其實是微秒
		self.assertIsNone(_progress_seconds("out_time_us=N/A"))
		self.assertIsNone(_progress_seconds("frame=10"))

	def test_format_bar(self) -> None:
		from wkt.core.ui import format_bar

		self.assertIn("  0%", format_bar("", 0, width=10))
		self.assertIn("100%", format_bar("", 1, width=10))
		self.assertEqual(format_bar("", 0.5, width=10).count("█"), 5)
		self.assertTrue(format_bar("[2/5] a.mp4", 0.2).startswith("[2/5] a.mp4 ["))
		self.assertIn("100%", format_bar("", 9))  # 超過上限會夾住

	def test_progress_is_silent_when_not_a_tty_or_unknown_total(self) -> None:
		import contextlib
		import io

		from wkt.core.ui import Progress

		err = io.StringIO()  # StringIO.isatty() 為 False
		with contextlib.redirect_stderr(err):
			bar = Progress(10.0)
			bar.update(5)
			bar.close()
			Progress(None).update(1)
		self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
	unittest.main()
