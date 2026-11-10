"""右鍵選單執行階段：佇列、領導者鎖，以及「多個程序同時啟動只有一個負責處理」。"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wkt import launcher


ROOT = Path(__file__).resolve().parent.parent


class QueueTests(unittest.TestCase):
	def setUp(self) -> None:
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.queue = Path(self._tmp.name) / "q"

	def test_enqueue_and_drain_keep_order_and_remove_jobs(self) -> None:
		launcher.enqueue(self.queue, ["a.mp4", "b.mp4"])
		launcher.enqueue(self.queue, ["c.mp4"])
		self.assertEqual(launcher.drain(self.queue), ["a.mp4", "b.mp4", "c.mp4"])
		self.assertEqual(launcher.drain(self.queue), [])
		self.assertEqual(list(self.queue.glob("*.job")), [])

	def test_paths_with_unicode_and_spaces_survive(self) -> None:
		name = r"C:\影片 資料夾\測試 檔案.mp4"
		launcher.enqueue(self.queue, [name])
		self.assertEqual(launcher.drain(self.queue), [name])

	def test_leader_lock_is_exclusive_and_releasable(self) -> None:
		first = launcher.try_lock(self.queue)
		self.assertIsNotNone(first)
		self.assertIsNone(launcher.try_lock(self.queue))  # 第二個拿不到
		launcher.unlock(first)
		second = launcher.try_lock(self.queue)
		self.assertIsNotNone(second)
		launcher.unlock(second)


def _env(local_app_data: str) -> dict[str, str]:
	env = dict(os.environ)
	env["LOCALAPPDATA"] = local_app_data
	env["PYTHONIOENCODING"] = "utf-8"  # 子程序的輸出固定用 UTF-8，測試才能穩定比對中文
	env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
	return env


def _spawn(local_app_data: str, tool: str, *files: Path) -> subprocess.Popen:
	return subprocess.Popen(
		[sys.executable, "-m", "wkt", "--from-menu", tool, *map(str, files)],
		env=_env(local_app_data),
		stdin=subprocess.DEVNULL,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True,
		encoding="utf-8",
		errors="replace",
		cwd=ROOT,
	)


try:
	from wkt.core.ffmpeg import find_ffmpeg

	FFMPEG: str | None = find_ffmpeg()
except Exception:
	FFMPEG = None


@unittest.skipUnless(FFMPEG, "需要 ffmpeg")
class MenuSessionTests(unittest.TestCase):
	def setUp(self) -> None:
		self._tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmp.cleanup)
		self.tmp = Path(self._tmp.name)
		self.appdata = str(self.tmp / "appdata")

	def _make_jpg(self, name: str) -> Path:
		path = self.tmp / name
		subprocess.run(
			[FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
			 "testsrc=size=32x24:rate=1:duration=1", "-frames:v", "1", str(path)],
			check=True,
		)
		return path

	def test_simultaneous_launches_are_merged_and_all_processed(self) -> None:
		files = [self._make_jpg(f"p{i}.jpg") for i in range(6)]
		processes = [_spawn(self.appdata, "topng", file) for file in files]  # 模擬 Explorer 同時啟動 6 個程序
		results = [(p.wait(timeout=120), *p.communicate()) for p in processes]

		for file in files:
			self.assertTrue(file.with_suffix(".png").is_file(), f"沒有被處理：{file.name}")
		self.assertTrue(all(code == 0 for code, _, _ in results), results)
		queue_dir = Path(self.appdata) / "WKT" / "queue" / "topng"
		self.assertEqual(list(queue_dir.glob("*.job")), [], "佇列應該被清空")
		# 只有領導者會顯示結果；絕大多數視窗應該是靜默結束（允許偶發的第二批領導者）
		silent = sum(1 for _, out, err in results if not out.strip() and not err.strip())
		self.assertGreaterEqual(silent, 3)

	def test_failure_returns_nonzero_and_shows_reason(self) -> None:
		process = _spawn(self.appdata, "topng", self.tmp / "missing.jpg")
		code = process.wait(timeout=60)
		out, err = process.communicate()
		self.assertEqual(code, 1)
		self.assertIn("找不到輸入檔案", out + err)

	def test_success_path_returns_zero(self) -> None:
		jpg = self._make_jpg("solo.jpg")
		process = _spawn(self.appdata, "topng", jpg)
		self.assertEqual(process.wait(timeout=60), 0)
		self.assertTrue(jpg.with_suffix(".png").is_file())
		out, _ = process.communicate()
		self.assertIn("全部完成", out)


if __name__ == "__main__":
	unittest.main()
