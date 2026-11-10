"""CLI 行為與端對端測試。

端對端測試需要 ffmpeg／OpenCV；沒安裝時會自動略過，不會讓整組測試失敗。
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from wkt.cli import main
from wkt.core.errors import WktError
from wkt.core.ffmpeg import find_ffmpeg, run_ffmpeg


def _ffmpeg_or_none() -> str | None:
	try:
		return find_ffmpeg()
	except WktError:
		return None


FFMPEG = _ffmpeg_or_none()
try:
	import cv2  # noqa: F401
	import numpy  # noqa: F401

	HAS_OPENCV = True
except ImportError:
	HAS_OPENCV = False


def run_cli(*argv: str) -> tuple[int, str, str]:
	out, err = io.StringIO(), io.StringIO()
	with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
		try:
			code = main(list(argv))
		except SystemExit as exc:  # argparse 的 --help／參數錯誤
			code = int(exc.code or 0)
	return code, out.getvalue(), err.getvalue()


class CliBehaviorTests(unittest.TestCase):
	def test_no_args_prints_help(self) -> None:
		code, out, _ = run_cli()
		self.assertEqual(code, 0)
		for name in ("togif", "to1080", "menu"):
			self.assertIn(name, out)

	def test_help_word(self) -> None:
		self.assertEqual(run_cli("help")[0], 0)

	def test_tool_help(self) -> None:
		code, out, _ = run_cli("togif", "--help")
		self.assertEqual(code, 0)
		self.assertIn("--fps", out)

	def test_unknown_tool_is_error(self) -> None:
		self.assertNotEqual(run_cli("nosuchtool")[0], 0)

	def test_tool_name_is_case_insensitive(self) -> None:
		self.assertEqual(run_cli("TOGIF", "--help")[0], 0)

	def test_missing_input_reports_error(self) -> None:
		code, _, err = run_cli("reencode", "does_not_exist.mp4")
		self.assertEqual(code, 1)
		self.assertIn("找不到輸入檔案", err)

	def test_version(self) -> None:
		self.assertEqual(run_cli("--version")[0], 0)


@unittest.skipUnless(FFMPEG, "需要 ffmpeg")
class EndToEndTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls._tmp = tempfile.TemporaryDirectory()
		cls.tmp = Path(cls._tmp.name)
		cls.video = cls.tmp / "clip.mp4"
		run_ffmpeg(
			[FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
			 "testsrc=size=320x240:rate=10:duration=1", "-pix_fmt", "yuv420p", str(cls.video)]
		)

	@classmethod
	def tearDownClass(cls) -> None:
		cls._tmp.cleanup()

	def test_togif(self) -> None:
		code, out, err = run_cli("togif", str(self.video), "--width", "160")
		self.assertEqual(code, 0, err)
		gif = self.video.with_suffix(".gif")
		self.assertTrue(gif.is_file() and gif.stat().st_size > 0)
		self.assertEqual(gif.read_bytes()[:3], b"GIF")
		self.assertEqual([p.name for p in self.tmp.glob(".*.tmp.gif")], [])  # 暫存檔已清掉

	def test_reencode(self) -> None:
		code, _, err = run_cli("reencode", str(self.video), "--preset", "ultrafast")
		self.assertEqual(code, 0, err)
		self.assertTrue((self.tmp / "clip_reencoded.mp4").is_file())

	def test_tobt709(self) -> None:
		code, _, err = run_cli("tobt709", str(self.video), "--preset", "ultrafast")
		self.assertEqual(code, 0, err)
		self.assertTrue((self.tmp / "clip_bt709.mp4").is_file())

	def test_toframe(self) -> None:
		out_dir = self.tmp / "frames"
		code, out, err = run_cli("toframe", str(self.video), "-o", str(out_dir))
		self.assertEqual(code, 0, err)
		self.assertEqual(len(list(out_dir.glob("*.png"))), 10)
		self.assertIn("10 幀", out)
		# 輸出資料夾非空時要拒絕，避免覆蓋
		code, _, err = run_cli("toframe", str(self.video), "-o", str(out_dir))
		self.assertEqual(code, 1)
		self.assertIn("不是空的", err)

	def _make_image(self, name: str, *extra: str) -> Path:
		path = self.tmp / name
		run_ffmpeg([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
		            "testsrc=size=64x48:rate=1:duration=1", "-frames:v", "1", *extra, str(path)])
		return path

	def test_topng_converts_jpeg_and_bmp(self) -> None:
		for name in ("photo.jpeg", "pic.bmp"):
			with self.subTest(name=name):
				source = self._make_image(name)
				code, _, err = run_cli("topng", str(source))
				self.assertEqual(code, 0, err)
				png = source.with_suffix(".png")
				self.assertEqual(png.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

	def test_topng_converts_webp_when_encoder_available(self) -> None:
		try:
			source = self._make_image("anim.webp")
		except WktError:
			self.skipTest("此 ffmpeg 沒有 webp 編碼器")
		code, _, err = run_cli("topng", str(source))
		self.assertEqual(code, 0, err)
		self.assertEqual(source.with_suffix(".png").read_bytes()[:4], b"\x89PNG")

	def test_topng_refuses_png_input_and_existing_output(self) -> None:
		png = self._make_image("already.png")
		code, _, err = run_cli("topng", str(png))
		self.assertEqual(code, 1)
		self.assertIn("已經是 PNG", err)

		source = self._make_image("clash.jpg")
		source.with_suffix(".png").write_bytes(b"keep me")
		code, _, err = run_cli("topng", str(source))
		self.assertEqual(code, 1)
		self.assertIn("已存在", err)
		self.assertEqual(source.with_suffix(".png").read_bytes(), b"keep me")  # 沒被覆蓋
		code, _, err = run_cli("topng", str(source), "--force")
		self.assertEqual(code, 0, err)
		self.assertEqual(source.with_suffix(".png").read_bytes()[:4], b"\x89PNG")

	def test_ffmpeg_failure_exit_code(self) -> None:
		bad = self.tmp / "bad.mp4"
		bad.write_bytes(b"not a video")
		code, _, err = run_cli("reencode", str(bad))
		self.assertNotEqual(code, 0)
		self.assertIn("ffmpeg 結束碼", err)


@unittest.skipUnless(FFMPEG and HAS_OPENCV, "需要 ffmpeg 與 opencv-python")
class FrameToolTests(unittest.TestCase):
	def setUp(self) -> None:
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.tmp = Path(self._tmp.name)

	def _make_image(self, size: str) -> Path:
		path = self.tmp / "frame.png"
		run_ffmpeg([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
		            f"testsrc=size={size}:rate=1:duration=1", "-frames:v", "1", str(path)])
		return path

	def test_to1080_then_to1088_roundtrip_sizes(self) -> None:
		import cv2

		source = self._make_image("1920x1088")
		code, _, err = run_cli("to1080", str(source))
		self.assertEqual(code, 0, err)
		cropped = self.tmp / "frame_1080.png"
		self.assertEqual(cv2.imread(str(cropped)).shape[:2], (1080, 1920))

		code, _, err = run_cli("to1088", str(cropped))
		self.assertEqual(code, 0, err)
		self.assertEqual(cv2.imread(str(self.tmp / "frame_1080_1088.png")).shape[:2], (1088, 1920))

	def test_wrong_size_is_rejected(self) -> None:
		source = self._make_image("640x360")
		code, _, err = run_cli("to1080", str(source))
		self.assertEqual(code, 1)
		self.assertIn("尺寸必須是 1920x1088", err)

	def test_video_input(self) -> None:
		import cv2

		video = self.tmp / "v.mp4"
		run_ffmpeg([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
		            "testsrc=size=1920x1088:rate=5:duration=1", "-pix_fmt", "yuv420p", str(video)])
		code, _, err = run_cli("to1080", str(video))
		self.assertEqual(code, 0, err)
		capture = cv2.VideoCapture(str(self.tmp / "v_1080.mp4"))
		self.addCleanup(capture.release)
		self.assertEqual(int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), 1080)


if __name__ == "__main__":
	unittest.main()
