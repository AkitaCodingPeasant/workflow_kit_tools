"""wkt dev／wkt install：原本散落在 scripts/ 的維護功能。"""

from __future__ import annotations

import argparse
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from wkt import dev, install
from wkt.core.errors import WktError


ROOT = Path(__file__).resolve().parent.parent

try:
	import cv2  # noqa: F401
	import numpy  # noqa: F401

	HAS_OPENCV = True
except ImportError:
	HAS_OPENCV = False


class BuildTests(unittest.TestCase):
	def test_collect_files_has_extras_and_every_package_module(self) -> None:
		relative = {path.relative_to(ROOT).as_posix() for path in dev.collect_files()}
		for expected in dev.EXTRA_FILES:
			self.assertIn(expected, relative)
		for module in ("wkt/cli.py", "wkt/dev.py", "wkt/install.py", "wkt/tools/togif.py", "wkt/core/ui.py"):
			self.assertIn(module, relative)
		self.assertFalse([name for name in relative if "__pycache__" in name or name.startswith("tests/")])

	def test_build_portable_writes_a_valid_zip(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			output = Path(tmp) / "out" / "pkg.zip"
			count = dev.build_portable(output)
			with zipfile.ZipFile(output) as archive:
				names = archive.namelist()
				self.assertIsNone(archive.testzip())
			self.assertEqual(len(names), count)
			self.assertIn("install.cmd", names)
			self.assertIn("scripts/install.ps1", names)
			self.assertNotIn("TODO.md", names)

	def test_missing_required_file_is_reported(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			(Path(tmp) / "wkt").mkdir()
			with self.assertRaises(WktError) as ctx:
				dev.collect_files(Path(tmp))
			self.assertIn("缺少必要檔案", ctx.exception.message)


class IconTests(unittest.TestCase):
	def test_build_ico_structure(self) -> None:
		data = dev.build_ico([(16, b"AAAA"), (256, b"BBBBBB")])
		self.assertEqual(struct.unpack("<HHH", data[:6]), (0, 1, 2))
		first = struct.unpack("<BBBBHHII", data[6:22])
		second = struct.unpack("<BBBBHHII", data[22:38])
		self.assertEqual((first[0], second[0]), (16, 0))  # 256 以 0 表示
		self.assertEqual(data[first[7]:first[7] + first[6]], b"AAAA")
		self.assertEqual(data[second[7]:second[7] + second[6]], b"BBBBBB")

	@unittest.skipUnless(HAS_OPENCV, "需要 opencv-python")
	def test_make_icon_from_non_square_png(self) -> None:
		import cv2
		import numpy as np

		with tempfile.TemporaryDirectory() as tmp:
			source, output = Path(tmp) / "wide.png", Path(tmp) / "wide.ico"
			cv2.imwrite(str(source), np.full((30, 90, 4), 200, dtype=np.uint8))
			dev.make_icon(source, output)
			data = output.read_bytes()
			self.assertEqual(struct.unpack("<HHH", data[:6]), (0, 1, len(dev.ICON_SIZES)))

	def test_make_icon_missing_source(self) -> None:
		if not HAS_OPENCV:
			self.skipTest("需要 opencv-python")
		with self.assertRaises(WktError):
			dev.make_icon(Path("no_such_icon.png"), Path("unused.ico"))

	def test_committed_icon_is_present(self) -> None:
		self.assertTrue(dev.ICON_OUTPUT.is_file())


class InstallTests(unittest.TestCase):
	def _args(self, **flags) -> argparse.Namespace:
		return argparse.Namespace(**{"yes": False, "no_path": False, "no_menu": False, **flags})

	def test_command_translates_flags(self) -> None:
		plain = install.powershell_command(self._args())
		self.assertEqual(plain[:5], ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"])
		self.assertEqual(plain[-1], str(install.SCRIPT))
		full = install.powershell_command(self._args(yes=True, no_path=True, no_menu=True))
		self.assertEqual(full[-3:], ["-Yes", "-NoPath", "-NoMenu"])

	def test_installer_files_exist_and_ps1_has_bom(self) -> None:
		self.assertTrue((ROOT / "install.cmd").is_file())
		self.assertTrue(install.SCRIPT.is_file())
		# Windows PowerShell 5.1 沒有 BOM 會把 UTF-8 當 ANSI 讀，中文訊息會變亂碼
		self.assertEqual(install.SCRIPT.read_bytes()[:3], b"\xef\xbb\xbf")

	def test_install_cmd_calls_the_ps1(self) -> None:
		text = (ROOT / "install.cmd").read_text(encoding="utf-8")
		self.assertIn(r"scripts\install.ps1", text)


if __name__ == "__main__":
	unittest.main()
