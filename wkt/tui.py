"""互動式 TUI：在終端機輸入不帶參數的 wkt 時開啟。

TUI 只負責「收集選擇、組出 argv」，實際執行一律交給 wkt.cli.main()，
所以 TUI 與命令列只有同一條執行路徑，行為不會分岔。

流程：主選單 → 選工具 → 選檔案（貼路徑／從資料夾挑選）→ 調整參數 → 確認（預覽／執行）。
畫面上按 Esc 回上一層，Ctrl+C 離開。

純函式（parse_paths、list_media、reflect_fields、build_argv…）與畫面分開，方便測試；
questionary 只在真正開啟 TUI 時才載入，沒安裝時 wkt 的其他功能完全不受影響。
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from wkt import __version__
from wkt.core.errors import WktError
from wkt.registry import CATEGORIES, group_by_category, load_commands


NO_TUI_ENV = "WKT_NO_TUI"
NO_TUI_FLAG = "--no-tui"
RECENT_LIMIT = 3
LIST_LIMIT = 200  # 資料夾挑選最多列出的檔案數，避免畫面被塞爆

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".wmv")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
# 沒列在這裡的工具，資料夾挑選時顯示所有影片與圖片
INPUT_EXTENSIONS = {
	"topng": IMAGE_EXTENSIONS,
	"to1080": (".png", *VIDEO_EXTENSIONS),
	"to1088": (".png", *VIDEO_EXTENSIONS),
}
SKIPPED_DESTS = {"help", "input", "dry_run"}  # 不在參數表單裡問的項目（--dry-run 由確認畫面處理）

BACK = object()  # 使用者按了 Esc


def recent_file() -> Path:
	base = os.environ.get("APPDATA") or str(Path.home())
	return Path(base) / "WKT" / "recent.json"


@dataclass(frozen=True)
class Field:
	dest: str
	option: str  # 命令列旗標，例如 --fps
	kind: str  # flag／choice／text
	help: str
	default: object = None
	choices: tuple[str, ...] = ()
	type: type | None = None  # int／float／None（字串）


@dataclass
class Selection:
	tool: str
	inputs: list[str] = field(default_factory=list)
	values: dict[str, object] = field(default_factory=dict)  # dest → 使用者設定的值
	extra: list[str] = field(default_factory=list)  # 自行輸入的額外參數


def should_launch_tui(argv: list[str], environ=os.environ, stdin=None, stdout=None) -> bool:
	"""只有「完全沒給參數、stdin／stdout 都是終端機、也沒關閉」才開 TUI。"""
	stdin = sys.stdin if stdin is None else stdin
	stdout = sys.stdout if stdout is None else stdout
	if argv or environ.get(NO_TUI_ENV) == "1":
		return False
	return bool(stdin.isatty() and stdout.isatty())


def parse_paths(text: str) -> list[str]:
	"""把貼上或拖入的文字拆成路徑。

	拖入檔案時 Windows Terminal 會用雙引號包住含空白的路徑，所以以引號為單位拆；
	沒有引號時，若整行本身就是存在的檔案（路徑含空白）就當成單一路徑。
	"""
	text = text.strip()
	if not text:
		return []
	if '"' not in text and Path(text).expanduser().exists():
		return [text]
	paths: list[str] = []
	token = ""
	in_quote = False
	for char in text:
		if char == '"':
			in_quote = not in_quote
			if not in_quote and token:
				paths.append(token)
				token = ""
		elif char.isspace() and not in_quote:
			if token:
				paths.append(token)
				token = ""
		else:
			token += char
	if token:
		paths.append(token)
	return paths


def missing_files(paths: list[str]) -> list[str]:
	return [raw for raw in paths if not Path(raw).expanduser().is_file()]


def extensions_for(tool: str) -> tuple[str, ...]:
	return INPUT_EXTENSIONS.get(tool, (*VIDEO_EXTENSIONS, *IMAGE_EXTENSIONS))


def list_media(folder: Path, extensions: tuple[str, ...], limit: int = LIST_LIMIT) -> list[Path]:
	"""資料夾內（不含子資料夾）符合副檔名的檔案，依名稱排序。"""
	found = [
		entry
		for entry in folder.iterdir()
		if entry.is_file() and entry.suffix.lower() in extensions and not entry.name.startswith(".")
	]
	found.sort(key=lambda entry: entry.name.lower())
	return found[:limit]


def reflect_fields(parser: argparse.ArgumentParser) -> list[Field]:
	"""從工具自己的 argparse 定義推出參數表單；工具不需要為 TUI 做任何事。"""
	fields = []
	for action in parser._actions:
		if action.dest in SKIPPED_DESTS or not action.option_strings:
			continue
		option = next((flag for flag in action.option_strings if flag.startswith("--")), action.option_strings[0])
		help_text = (action.help or "").replace("%(default)s", str(action.default))
		if isinstance(action, argparse._StoreTrueAction):
			fields.append(Field(action.dest, option, "flag", help_text))
		elif action.choices:
			fields.append(
				Field(action.dest, option, "choice", help_text, action.default, tuple(str(c) for c in action.choices))
			)
		elif action.nargs is None and isinstance(action, argparse._StoreAction):
			fields.append(Field(action.dest, option, "text", help_text, action.default, type=action.type))
	return fields


def coerce(value: str, kind: type | None) -> object:
	"""依欄位型別轉換輸入；失敗 raise ValueError。"""
	return kind(value) if kind else value


def build_argv(selection: Selection, fields: list[Field]) -> list[str]:
	argv = [selection.tool, *selection.inputs]
	by_dest = {item.dest: item for item in fields}
	for dest, value in selection.values.items():
		item = by_dest[dest]
		if item.kind == "flag":
			if value:
				argv.append(item.option)
		elif value not in (None, "") and str(value) != str(item.default):
			argv.extend([item.option, str(value)])
	argv.extend(selection.extra)
	return argv


def equivalent_command(argv: list[str]) -> str:
	return "wkt " + subprocess.list2cmdline(argv)


def recent_tools(modules: list[ModuleType], recent: list[str]) -> list[ModuleType]:
	"""依最近使用順序回傳仍然存在的工具（工具被刪除或改名時自動略過）。"""
	by_name = {module.NAME: module for module in modules}
	return [by_name[name] for name in recent if name in by_name]


def load_recent(path: Path | None = None) -> list[str]:
	try:
		data = json.loads((path or recent_file()).read_text(encoding="utf-8"))
		return [name for name in data if isinstance(name, str)][:RECENT_LIMIT]
	except (OSError, ValueError, TypeError):
		return []


def save_recent(tool: str, path: Path | None = None) -> None:
	"""記錄最近使用的工具；寫不進去就算了，不影響主流程。"""
	target = path or recent_file()
	names = [tool, *[name for name in load_recent(target) if name != tool]][:RECENT_LIMIT]
	try:
		target.parent.mkdir(parents=True, exist_ok=True)
		target.write_text(json.dumps(names), encoding="utf-8")
	except OSError:
		pass


def ffmpeg_warning() -> str | None:
	from wkt.core.ffmpeg import find_ffmpeg

	try:
		find_ffmpeg()
	except WktError:
		return "找不到 ffmpeg，多數工具無法使用。安裝：winget install Gyan.FFmpeg（安裝後重新開啟終端機）"
	return None


# ---------------------------------------------------------------- 以下是畫面 ----


def _load_questionary():
	try:
		import questionary
	except ImportError:
		return None
	return questionary


class Screen:
	"""包裝 questionary：每個提示都支援 Esc 返回（回傳 BACK），Ctrl+C 往上拋 KeyboardInterrupt。"""

	def __init__(self, questionary) -> None:
		self.q = questionary
		self.style = questionary.Style(
			[("qmark", "fg:ansicyan bold"), ("highlighted", "fg:ansicyan bold"), ("pointer", "fg:ansicyan bold")]
		)

	def ask(self, question):
		from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings

		bindings = KeyBindings()

		@bindings.add("escape", eager=True)
		def _(event) -> None:
			event.app.exit(result=BACK)

		app = question.application
		app.key_bindings = merge_key_bindings([app.key_bindings, bindings])
		return question.unsafe_ask()

	def select(self, message: str, choices: list, default=None):
		return self.ask(
			self.q.select(
				message,
				choices=choices,
				default=default,
				style=self.style,
				instruction="（↑↓ 選擇，Enter 確認，Esc 返回）",
			)
		)

	def checkbox(self, message: str, choices: list):
		return self.ask(
			self.q.checkbox(
				message,
				choices=choices,
				style=self.style,
				instruction="（空白鍵勾選，Enter 確認，Esc 返回）",
			)
		)

	def text(self, message: str, default: str = ""):
		return self.ask(self.q.text(message, default=default, style=self.style, instruction="（Esc 返回）"))

	def pause(self) -> None:
		self.ask(self.q.press_any_key_to_continue("按任意鍵返回選單…", style=self.style))


def pick_files(screen: Screen, tool: str) -> list[str] | object:
	"""回傳檔案路徑清單；Esc 回傳 BACK。"""
	method = "paste"
	while True:
		method = screen.select(
			f"{tool}：要處理哪些檔案？",
			[
				screen.q.Choice("貼上或拖入檔案路徑（可多個）", "paste"),
				screen.q.Choice("從資料夾挑選", "folder"),
			],
			default=method,
		)
		if method is BACK:
			return BACK
		picked = _paste_paths(screen) if method == "paste" else _pick_from_folder(screen, tool)
		if picked is not BACK:
			return picked


def _paste_paths(screen: Screen) -> list[str] | object:
	while True:
		answer = screen.text("檔案路徑（拖入檔案或貼上；含空白的路徑請用雙引號包住）")
		if answer is BACK:
			return BACK
		paths = parse_paths(answer)
		if not paths:
			print("請輸入至少一個檔案路徑。")
			continue
		missing = missing_files(paths)
		if missing:
			print("找不到下列檔案：\n  " + "\n  ".join(missing))
			continue
		return paths


def _pick_from_folder(screen: Screen, tool: str) -> list[str] | object:
	folder_text = str(Path.cwd())
	while True:
		answer = screen.text("資料夾路徑", default=folder_text)
		if answer is BACK:
			return BACK
		folder_text = answer.strip().strip('"')
		folder = Path(folder_text).expanduser()
		if not folder.is_dir():
			print(f"不是資料夾：{folder_text}")
			continue
		try:
			entries = list_media(folder, extensions_for(tool))
		except OSError as exc:
			print(f"無法讀取資料夾：{exc}")
			continue
		if not entries:
			print(f"此資料夾沒有 {tool} 能處理的檔案（{'、'.join(extensions_for(tool))}）。")
			continue
		chosen = screen.checkbox(
			f"挑選檔案（共 {len(entries)} 個）",
			[screen.q.Choice(entry.name, str(entry)) for entry in entries],
		)
		if chosen is BACK:
			continue  # 回到資料夾輸入
		if not chosen:
			print("尚未勾選任何檔案（空白鍵勾選）。")
			continue
		return chosen


def ask_value(screen: Screen, item: Field):
	"""問單一參數的值；回傳 BACK 表示取消這一項。"""
	label = f"{item.option}：{item.help}"
	if item.kind == "flag":
		return screen.select(label, [screen.q.Choice("開啟", True), screen.q.Choice("關閉", False)])
	if item.kind == "choice":
		return screen.select(label, [screen.q.Choice(choice, choice) for choice in item.choices])
	default = "" if item.default is None else str(item.default)
	while True:
		answer = screen.text(label, default=default)
		if answer is BACK:
			return BACK
		answer = answer.strip()
		if not answer:
			return ""
		try:
			coerce(answer, item.type)
		except ValueError:
			print(f"請輸入有效的{'整數' if item.type is int else '數字'}。")
			continue
		return answer


def edit_params(screen: Screen, selection: Selection, fields: list[Field]) -> bool:
	"""讓使用者挑選要調整的參數；Esc 回傳 False（回上一步）。"""
	if not fields:
		return True
	choices = [screen.q.Choice(f"{item.option}  {item.help}", item.dest) for item in fields]
	chosen = screen.checkbox("要調整哪些參數？（不勾選直接 Enter＝全部使用預設值）", choices)
	if chosen is BACK:
		return False
	by_dest = {item.dest: item for item in fields}
	selection.values = {}
	for dest in chosen:
		value = ask_value(screen, by_dest[dest])
		if value is BACK:
			continue
		selection.values[dest] = value
	extra = screen.text("其他參數（進階，直接輸入，例如 --start 3；不需要請留白）")
	if extra is BACK:
		return False
	selection.extra = shlex.split(extra, posix=False) if extra.strip() else []
	return True


def has_input(parser: argparse.ArgumentParser) -> bool:
	"""有 input 參數的才是處理檔案的工具；doctor、menu、dev 這類管理指令沒有。"""
	return any(action.dest == "input" for action in parser._actions)


def confirm_and_run(screen: Screen, selection: Selection, fields: list[Field], previewable: bool = True) -> str:
	"""回傳 done（已執行）／back（回上一步）。"""
	from wkt.cli import main

	while True:
		argv = build_argv(selection, fields)
		print(f"\n等同指令：{equivalent_command(argv)}\n")
		choices = [screen.q.Choice("執行", "run")]
		if previewable:
			choices.append(screen.q.Choice("預覽輸出路徑與衝突（--dry-run）", "preview"))
		choices.append(screen.q.Choice("返回修改", "back"))
		action = screen.select("確認", choices)
		if action in (BACK, "back"):
			return "back"
		if action == "preview":
			print()
			main([*argv, "--dry-run"])
			continue
		print()
		main(argv)
		save_recent(selection.tool)
		print()
		screen.pause()
		return "done"


def tool_flow(screen: Screen, module: ModuleType) -> None:
	parser = argparse.ArgumentParser(prog=module.NAME)
	module.configure_parser(parser)
	fields = reflect_fields(parser)
	selection = Selection(module.NAME)
	if not has_input(parser):
		manage_flow(screen, selection, parser)
		return
	step = "files"
	while True:
		if step == "files":
			files = pick_files(screen, module.NAME)
			if files is BACK:
				return
			selection.inputs = list(files)
			step = "params"
		elif step == "params":
			step = "confirm" if edit_params(screen, selection, fields) else "files"
		else:
			if confirm_and_run(screen, selection, fields) == "done":
				return
			step = "params"


def manage_flow(screen: Screen, selection: Selection, parser: argparse.ArgumentParser) -> None:
	"""管理指令：顯示它自己的說明，讓使用者輸入參數（例如 menu 的 register）。"""
	print("\n" + parser.format_help())
	while True:
		answer = screen.text(f"{selection.tool} 的參數（不需要請留白）")
		if answer is BACK:
			return
		selection.extra = shlex.split(answer, posix=False) if answer.strip() else []
		if confirm_and_run(screen, selection, [], previewable=False) == "done":
			return


def _tool_choice(screen: Screen, module: ModuleType, mark: str = "") -> object:
	return screen.q.Choice(f"{mark}{module.NAME:<9} {module.SUMMARY}", module)


def category_flow(screen: Screen, key: str, modules: list[ModuleType]) -> None:
	while True:
		picked = screen.select(CATEGORIES[key], [_tool_choice(screen, module) for module in modules])
		if picked is BACK:
			return
		tool_flow(screen, picked)


def run_tui() -> int:
	questionary = _load_questionary()
	if questionary is None:
		print("TUI 需要 questionary 套件：py -3 -m pip install -r requirements.txt", file=sys.stderr)
		print("改用命令列：wkt help", file=sys.stderr)
		return 1

	builtins, tools = load_commands()
	grouped = group_by_category([*tools, *builtins])
	screen = Screen(questionary)
	warning = ffmpeg_warning()
	try:
		while True:
			print(f"\nWKT 工具箱 v{__version__}")
			if warning:
				print(f"⚠ {warning}")
			recent = recent_tools([m for key in CATEGORIES for m in grouped[key]], load_recent())
			choices = [questionary.Separator("── 最近使用 ──")] if recent else []
			choices += [_tool_choice(screen, module, "↻ ") for module in recent]
			if recent:
				choices.append(questionary.Separator("── 分類 ──"))
			choices += [
				questionary.Choice(f"{CATEGORIES[key]}（{len(grouped[key])}）", key)
				for key in CATEGORIES
				if grouped[key]
			]
			choices.append(questionary.Choice("離開", "quit"))
			picked = screen.select("要做什麼？", choices)
			if picked is BACK or picked == "quit":
				return 0
			if isinstance(picked, str):
				category_flow(screen, picked, grouped[picked])
			else:
				tool_flow(screen, picked)
	except KeyboardInterrupt:
		print("已離開。")
		return 130
