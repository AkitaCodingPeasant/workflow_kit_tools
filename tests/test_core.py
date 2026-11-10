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


if __name__ == "__main__":
	unittest.main()
