"""wkt.core.env：Python 安裝方式（全域／虛擬環境）的記錄檔讀取。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wkt import doctor
from wkt.core import env


class ConfiguredModeTests(unittest.TestCase):
	def _read(self, content: bytes | None) -> str:
		with tempfile.TemporaryDirectory() as tmp:
			path = Path(tmp) / ".wkt-env"
			if content is not None:
				path.write_bytes(content)
			return env.configured_mode(path)

	def test_missing_file_means_global(self) -> None:
		self.assertEqual(self._read(None), env.GLOBAL)

	def test_reads_venv_with_whitespace_case_and_bom(self) -> None:
		self.assertEqual(self._read(b"venv\r\n"), env.VENV)
		self.assertEqual(self._read(b"\xef\xbb\xbf VENV \n"), env.VENV)

	def test_unknown_value_falls_back_to_global(self) -> None:
		self.assertEqual(self._read(b"conda"), env.GLOBAL)

	def test_pip_hint_follows_mode(self) -> None:
		with mock.patch.object(env, "configured_mode", return_value=env.VENV):
			self.assertIn(".venv", env.pip_install_hint())
		with mock.patch.object(env, "configured_mode", return_value=env.GLOBAL):
			self.assertTrue(env.pip_install_hint().startswith("py -3"))


class DoctorInstallModeTests(unittest.TestCase):
	def test_global_mode_is_ok(self) -> None:
		with mock.patch.object(env, "configured_mode", return_value=env.GLOBAL):
			self.assertEqual(doctor.check_install_mode().status, doctor.OK)

	def test_venv_mode_without_venv_fails_with_fix(self) -> None:
		with mock.patch.object(env, "configured_mode", return_value=env.VENV), \
			mock.patch.object(env, "VENV_PYTHON", Path("no_such_dir/python.exe")):
			check = doctor.check_install_mode()
		self.assertEqual(check.status, doctor.FAIL)
		self.assertIn("--mode venv", check.fix)

	def test_venv_mode_outside_venv_warns(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			python = Path(tmp) / "python.exe"
			python.write_bytes(b"")
			with mock.patch.object(env, "configured_mode", return_value=env.VENV), \
				mock.patch.object(env, "VENV_PYTHON", python), \
				mock.patch.object(env, "running_in_venv", return_value=False):
				self.assertEqual(doctor.check_install_mode().status, doctor.WARN)


if __name__ == "__main__":
	unittest.main()
