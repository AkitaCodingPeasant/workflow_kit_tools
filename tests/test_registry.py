from __future__ import annotations

import importlib
import struct
import types
import unittest

from wkt import menu, registry


# 新增或移除工具、或調整分類時，必須同步更新這份清單（防止工具被意外遺漏、誤刪或被悄悄換分類）。
EXPECTED_TOOLS = {
	"togif": "general",
	"toframe": "general",
	"topng": "general",
	"reencode": "general",
	"to1080": "special",
	"to1088": "special",
	"tobt709": "special",
}


class RegistryTests(unittest.TestCase):
	def test_discovers_all_expected_tools(self) -> None:
		self.assertEqual(registry.tool_categories(), EXPECTED_TOOLS)

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
		bad_name.NAME, bad_name.SUMMARY, bad_name.CATEGORY = "Bad-Name", "x", "general"
		bad_name.configure_parser = bad_name.run = lambda *_: None
		missing_run = types.ModuleType("missing_run")
		missing_run.NAME, missing_run.SUMMARY, missing_run.CATEGORY = "ok", "x", "general"
		missing_run.configure_parser = lambda *_: None
		no_category = types.ModuleType("no_category")
		no_category.NAME, no_category.SUMMARY = "ok", "x"
		no_category.configure_parser = no_category.run = lambda *_: None
		wrong_category = types.ModuleType("wrong_category")
		wrong_category.NAME, wrong_category.SUMMARY, wrong_category.CATEGORY = "ok", "x", "misc"
		wrong_category.configure_parser = wrong_category.run = lambda *_: None
		for module in (bad_name, missing_run, no_category, wrong_category):
			with self.subTest(module=module.__name__):
				with self.assertRaises(ValueError):
					registry.validate_command(module)


class CategoryTests(unittest.TestCase):
	def test_categories_are_defined_in_display_order(self) -> None:
		self.assertEqual(list(registry.CATEGORIES), ["general", "special", "manage"])

	def test_builtins_are_manage_and_tools_never_are(self) -> None:
		builtins, tools = registry.load_commands()
		self.assertTrue(all(module.CATEGORY == "manage" for module in builtins))
		self.assertFalse(any(module.CATEGORY == "manage" for module in tools))

	def test_group_by_category_sorts_and_keeps_empty_groups(self) -> None:
		builtins, tools = registry.load_commands()
		grouped = registry.group_by_category([*tools, *builtins])
		self.assertEqual(list(grouped), list(registry.CATEGORIES))
		for key, modules in grouped.items():
			self.assertEqual([m.NAME for m in modules], sorted(m.NAME for m in modules), key)
		self.assertEqual([m.NAME for m in grouped["special"]], ["to1080", "to1088", "tobt709"])
		self.assertEqual(registry.group_by_category([])["special"], [])

	def test_template_defaults_to_general(self) -> None:
		template = importlib.import_module("wkt.tools._template")
		self.assertEqual(template.CATEGORY, "general")


class MenuConfigTests(unittest.TestCase):
	def test_menu_only_references_existing_tools(self) -> None:
		menu.check_menu_config()

	def test_menu_contains_only_general_tools(self) -> None:
		categories = registry.tool_categories()
		for items in menu.MENU.values():
			for item in items:
				self.assertEqual(categories[item.tool], "general", f"{item.tool} 不是通用工具，不能放進右鍵選單")

	def test_special_tool_in_menu_is_rejected(self) -> None:
		from unittest import mock

		from wkt.core.errors import WktError

		bad = {".mp4": (menu.MenuItem("to1080", "裁切"),)}
		with mock.patch.dict(menu.MENU, bad, clear=True):
			with self.assertRaises(WktError) as ctx:
				menu.check_menu_config()
		self.assertIn("特殊用途", ctx.exception.message)

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

	def test_builtin_commands(self) -> None:
		builtins, _ = registry.load_commands()
		self.assertEqual({module.NAME for module in builtins}, {"menu", "doctor", "install", "dev"})


if __name__ == "__main__":
	unittest.main()
