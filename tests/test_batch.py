from __future__ import annotations

import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from wkt.batch import is_batchable, run_batch
from wkt.core.args import add_input_argument
from wkt.core.errors import WktError


def make_args(inputs: list[str], **extra) -> argparse.Namespace:
	return argparse.Namespace(input=inputs, output=None, output_dir=None, **extra)


def quiet(func, *args):
	out, err = io.StringIO(), io.StringIO()
	with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
		result = func(*args)
	return result, out.getvalue(), err.getvalue()


class BatchTests(unittest.TestCase):
	def test_add_input_argument_accepts_many(self) -> None:
		parser = argparse.ArgumentParser()
		add_input_argument(parser, "輸入")
		self.assertEqual(parser.parse_args(["a", "b", "c"]).input, ["a", "b", "c"])
		with self.assertRaises(SystemExit):
			parser.parse_args([])  # 至少要一個

	def test_is_batchable(self) -> None:
		self.assertTrue(is_batchable(make_args(["a"])))
		self.assertFalse(is_batchable(argparse.Namespace(input="a")))
		self.assertFalse(is_batchable(argparse.Namespace()))

	def test_single_input_passes_a_string_and_propagates_errors(self) -> None:
		seen = []
		code, _, _ = quiet(run_batch, lambda a: seen.append(a.input), make_args(["only.mp4"]))
		self.assertEqual((code, seen), (0, ["only.mp4"]))

		def failing(args):
			raise WktError("壞了", exit_code=7)

		with self.assertRaises(WktError) as ctx:
			quiet(run_batch, failing, make_args(["x.mp4"]))
		self.assertEqual(ctx.exception.exit_code, 7)

	def test_many_inputs_run_each_and_summarize(self) -> None:
		seen = []
		code, out, _ = quiet(run_batch, lambda a: seen.append(a.input), make_args(["a", "b", "c"]))
		self.assertEqual((code, seen), (0, ["a", "b", "c"]))
		self.assertIn("[2/3]", out)
		self.assertIn("完成 3／3", out)

	def test_failure_does_not_stop_the_rest(self) -> None:
		seen = []

		def run(args):
			seen.append(args.input)
			if args.input == "b":
				raise WktError("找不到輸入檔案：b")
			if args.input == "c":
				raise RuntimeError("意外")

		code, out, err = quiet(run_batch, run, make_args(["a", "b", "c", "d"]))
		self.assertEqual(code, 1)
		self.assertEqual(seen, ["a", "b", "c", "d"])  # 全部都有嘗試
		self.assertIn("完成 2／4", out)
		self.assertIn("失敗的檔案", err)
		self.assertIn("找不到輸入檔案：b", err)
		self.assertIn("處理失敗：意外", err)

	def test_output_option_rejected_for_many_inputs_but_ok_for_one(self) -> None:
		with self.assertRaises(WktError):
			quiet(run_batch, lambda a: None, argparse.Namespace(input=["a", "b"], output="x.mp4", output_dir=None))
		with self.assertRaises(WktError):
			quiet(run_batch, lambda a: None, argparse.Namespace(input=["a", "b"], output=None, output_dir="d"))
		code, _, _ = quiet(run_batch, lambda a: None, argparse.Namespace(input=["a"], output="x.mp4", output_dir=None))
		self.assertEqual(code, 0)

	def test_dry_run_previews_without_running_and_reports_existing_output(self) -> None:
		with tempfile.TemporaryDirectory() as raw:
			root = Path(raw)
			(root / "a.jpg").write_bytes(b"a")
			(root / "b.jpg").write_bytes(b"b")
			(root / "b.png").write_bytes(b"keep")
			seen = []
			args = make_args([str(root / "a.jpg"), str(root / "b.jpg")])
			args.force = False
			args.dry_run = True
			args.planner = lambda item: Path(item.input).with_suffix(".png")
			code, out, _ = quiet(run_batch, lambda item: seen.append(item.input), args)
			self.assertEqual(code, 1)
			self.assertEqual(seen, [])
			self.assertIn("新增", out)
			self.assertIn("衝突（需 --force）", out)
			self.assertFalse((root / "a.png").exists())
			self.assertEqual((root / "b.png").read_bytes(), b"keep")

	def test_batch_rejects_duplicate_targets_before_running(self) -> None:
		with tempfile.TemporaryDirectory() as raw:
			root = Path(raw)
			inputs = []
			for folder in ("left", "right"):
				parent = root / folder
				parent.mkdir()
				file = parent / "same.jpg"
				file.write_bytes(b"x")
				inputs.append(str(file))
			args = make_args(inputs)
			args.planner = lambda item: root / "out" / "same.png"
			seen = []
			with self.assertRaisesRegex(WktError, "輸出路徑重複"):
				quiet(run_batch, lambda item: seen.append(item.input), args)
			self.assertEqual(seen, [])
			args.dry_run = True
			args.force = False
			code, out, _ = quiet(run_batch, lambda item: seen.append(item.input), args)
			self.assertEqual(code, 1)
			self.assertEqual(seen, [])
			self.assertEqual(out.count("  → "), 2)
			self.assertIn("批次輸出重複", out)


if __name__ == "__main__":
	unittest.main()
