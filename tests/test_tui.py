"""TUI 的純函式測試（不需要 questionary，也不需要真的終端機）。"""

from __future__ import annotations

import argparse
import io
import tempfile
import unittest
from pathlib import Path

from wkt import tui
from wkt.cli import main
from wkt.registry import load_commands


class FakeStream(io.StringIO):
	def __init__(self, tty: bool) -> None:
		super().__init__()
		self._tty = tty

	def isatty(self) -> bool:
		return self._tty


class LaunchRuleTests(unittest.TestCase):
	def test_only_interactive_empty_argv_opens_tui(self) -> None:
		tty, pipe = FakeStream(True), FakeStream(False)
		self.assertTrue(tui.should_launch_tui([], {}, tty, tty))
		self.assertFalse(tui.should_launch_tui([], {}, pipe, tty))  # 輸入被導向
		self.assertFalse(tui.should_launch_tui([], {}, tty, pipe))  # 輸出被導向
		self.assertFalse(tui.should_launch_tui(["-h"], {}, tty, tty))
		self.assertFalse(tui.should_launch_tui([], {tui.NO_TUI_ENV: "1"}, tty, tty))

	def test_no_tui_flag_prints_help(self) -> None:
		out = io.StringIO()
		import contextlib

		with contextlib.redirect_stdout(out):
			self.assertEqual(main(["--no-tui"]), 0)
		self.assertIn("togif", out.getvalue())


class ParsePathTests(unittest.TestCase):
	def test_quoted_and_plain_paths(self) -> None:
		self.assertEqual(tui.parse_paths(r'"C:\a b\x.mp4" C:\y.mp4'), [r"C:\a b\x.mp4", r"C:\y.mp4"])
		self.assertEqual(tui.parse_paths("  "), [])

	def test_unquoted_path_with_spaces_when_it_exists(self) -> None:
		with tempfile.TemporaryDirectory() as raw:
			path = Path(raw) / "my clip.mp4"
			path.write_bytes(b"x")
			self.assertEqual(tui.parse_paths(str(path)), [str(path)])
			self.assertEqual(tui.missing_files([str(path), str(path) + ".no"]), [str(path) + ".no"])


class ListMediaTests(unittest.TestCase):
	def test_filters_by_extension_sorts_and_skips_hidden(self) -> None:
		with tempfile.TemporaryDirectory() as raw:
			root = Path(raw)
			for name in ("b.MP4", "a.mp4", "c.txt", ".hidden.mp4", "d.png"):
				(root / name).write_bytes(b"x")
			(root / "sub.mp4").mkdir()  # 資料夾不算
			names = [p.name for p in tui.list_media(root, tui.extensions_for("togif"))]
			self.assertEqual(names, ["a.mp4", "b.MP4", "d.png"])
			self.assertEqual([p.name for p in tui.list_media(root, tui.extensions_for("topng"))], ["d.png"])


class FormTests(unittest.TestCase):
	def reflect(self, name: str):
		_, tools = load_commands()
		module = next(m for m in tools if m.NAME == name)
		parser = argparse.ArgumentParser()
		module.configure_parser(parser)
		return tui.reflect_fields(parser)

	def test_reflects_tool_options(self) -> None:
		fields = {item.dest: item for item in self.reflect("togif")}
		self.assertEqual(fields["profile"].kind, "choice")
		self.assertEqual(fields["profile"].choices, ("small", "standard", "high"))
		self.assertEqual(fields["fps"].type, int)
		self.assertEqual(fields["force"].kind, "flag")
		self.assertNotIn("input", fields)
		self.assertNotIn("dry_run", fields)

	def test_build_argv_only_emits_changed_values(self) -> None:
		fields = self.reflect("reencode")
		selection = tui.Selection(
			"reencode", ["a.mp4"], {"crf": "18", "preset": "slow", "force": True, "audio_bitrate": ""}, ["--x", "1"]
		)
		self.assertEqual(
			tui.build_argv(selection, fields), ["reencode", "a.mp4", "--preset", "slow", "--force", "--x", "1"]
		)

	def test_equivalent_command_quotes_spaces(self) -> None:
		self.assertEqual(tui.equivalent_command(["togif", "a b.mp4"]), 'wkt togif "a b.mp4"')

	def test_manage_commands_have_no_input(self) -> None:
		builtins, tools = load_commands()
		for module in (*builtins, *tools):
			parser = argparse.ArgumentParser()
			module.configure_parser(parser)
			self.assertEqual(tui.has_input(parser), module in tools, module.NAME)


class RecentTests(unittest.TestCase):
	def test_recent_roundtrip_dedupes_and_limits(self) -> None:
		with tempfile.TemporaryDirectory() as raw:
			path = Path(raw) / "sub" / "recent.json"
			self.assertEqual(tui.load_recent(path), [])
			for name in ("a", "b", "c", "d", "b"):
				tui.save_recent(name, path)
			self.assertEqual(tui.load_recent(path), ["b", "d", "c"])

	def test_corrupt_file_is_ignored(self) -> None:
		with tempfile.TemporaryDirectory() as raw:
			path = Path(raw) / "recent.json"
			path.write_text("{not json", encoding="utf-8")
			self.assertEqual(tui.load_recent(path), [])

	def test_recent_tools_skip_unknown_names(self) -> None:
		_, tools = load_commands()
		result = tui.recent_tools(tools, ["gone", "togif"])
		self.assertEqual([m.NAME for m in result], ["togif"])


if __name__ == "__main__":
	unittest.main()
