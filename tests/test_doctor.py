from __future__ import annotations

import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from wkt import doctor
from wkt.core.errors import WktError


def run_doctor(checks: list[doctor.Check]) -> tuple[str, WktError | None]:
	out = io.StringIO()
	error = None
	with contextlib.redirect_stdout(out):
		try:
			doctor.run(argparse.Namespace(), checker=lambda: checks)
		except WktError as exc:
			error = exc
	return out.getvalue(), error


class DoctorTests(unittest.TestCase):
	def test_real_checks_return_well_formed_results(self) -> None:
		checks = doctor.run_checks()
		names = [check.name for check in checks]
		for expected in ("Python", "ffmpeg", "OpenCV／numpy", "PATH"):
			self.assertIn(expected, names)
		for check in checks:
			self.assertIn(check.status, (doctor.OK, doctor.WARN, doctor.FAIL))
			self.assertTrue(check.detail)
			if check.status != doctor.OK:
				self.assertTrue(check.fix, f"{check.name} 失敗或警告時必須附修復建議")

	def test_python_check_passes_on_supported_interpreter(self) -> None:
		self.assertEqual(doctor.check_python().status, doctor.OK)

	def test_all_ok_exits_cleanly(self) -> None:
		out, error = run_doctor([doctor.Check("A", doctor.OK, "好")])
		self.assertIsNone(error)
		self.assertIn("全部通過", out)

	def test_warnings_do_not_fail(self) -> None:
		out, error = run_doctor([doctor.Check("A", doctor.WARN, "小問題", "照做")])
		self.assertIsNone(error)
		self.assertIn("1 項警告", out)
		self.assertIn("修復：照做", out)

	def test_failure_raises_with_exit_code_1(self) -> None:
		out, error = run_doctor([
			doctor.Check("A", doctor.OK, "好"),
			doctor.Check("B", doctor.FAIL, "壞了", "wkt menu register"),
		])
		self.assertIsNotNone(error)
		self.assertEqual(error.exit_code, 1)
		self.assertIn("1 項失敗", error.message)
		self.assertIn("[失敗] B", out)

	def test_render_uses_ascii_safe_markers(self) -> None:
		for marker in doctor.LABELS.values():
			self.assertTrue(marker.startswith("["))

	def test_find_on_path_only_searches_given_folders(self) -> None:
		with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
			(Path(tmp) / "wkt.cmd").write_text("@echo off\n")
			self.assertEqual(doctor.find_on_path("wkt", tmp), str(Path(tmp) / "wkt.cmd"))
			self.assertIsNone(doctor.find_on_path("wkt", other))
			self.assertIsNone(doctor.find_on_path("wkt", ""))


if __name__ == "__main__":
	unittest.main()
