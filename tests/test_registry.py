from __future__ import annotations

import importlib
import struct
import types
import unittest

from wkt import menu, registry


# 新增或移除工具時，必須同步更新這份清單（防止工具被意外遺漏或誤刪）。
EXPECTED_TOOLS = {"reencode", "to1080", "to1088", "tobt709", "toframe", "togif", "topng"}


class RegistryTests(unittest.TestCase):
	def test_discovers_all_expected_tools(self) -> None:
		names = {module.NAME for module in registry.discover_tools()}
		self.assertEqual(names, EXPECTED_TOOLS)

	def test_every_command_satisfies_contract(self) -> None:
		builtins, tools = registry.load_commands()
		for module in (*builtins, *tools):
			with self.subTest(module=module.__name__):
				registry.validate_command(module)

	def test_template_satisfies_contract_but_is_not_discovered(self) -> None:
		template = importlib.import_module("wkt.tools._template")
		registry.validate_command(template)
		self.assertNotIn(template.NAME, registry.tool_names())

	def test_tool_name_matches_module_filename(self) -> None:
		for module in registry.discover_tools():
			with self.subTest(module=module.__name__):
				self.assertEqual(module.NAME, module.__name__.rsplit(".", 1)[-1])

	def test_validate_rejects_bad_modules(self) -> None:
		bad_name = types.ModuleType("bad_name")
		bad_name.NAME, bad_name.SUMMARY = "Bad-Name", "x"
		bad_name.configure_parser = bad_name.run = lambda *_: None
		missing_run = types.ModuleType("missing_run")
		missing_run.NAME, missing_run.SUMMARY = "ok", "x"
		missing_run.configure_parser = lambda *_: None
		for module in (bad_name, missing_run):
			with self.subTest(module=module.__name__):
				with self.assertRaises(ValueError):
					registry.validate_command(module)


class MenuConfigTests(unittest.TestCase):
	def test_menu_only_references_existing_tools(self) -> None:
		menu.check_menu_config()

	def test_menu_extensions_start_with_dot(self) -> None:
		for extension in menu.MENU:
			self.assertTrue(extension.startswith("."))

	def test_icon_is_a_valid_ico_file(self) -> None:
		data = menu.ICON.read_bytes()
		reserved, kind, count = struct.unpack("<HHH", data[:6])
		self.assertEqual((reserved, kind), (0, 1))
		self.assertGreaterEqual(count, 1)

	def test_command_line_quotes_launcher_and_path(self) -> None:
		line = menu.command_line("togif")
		self.assertTrue(line.startswith('"'))
		self.assertTrue(line.endswith(' --from-menu togif "%1"'))
		self.assertIn("wkt.cmd", line)

	def test_builtin_commands_include_menu_and_doctor(self) -> None:
		builtins, _ = registry.load_commands()
		self.assertEqual({module.NAME for module in builtins}, {"menu", "doctor"})


if __name__ == "__main__":
	unittest.main()
