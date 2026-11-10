"""wkt dev：開發與維護用的指令（原本散落在 scripts/ 的腳本）。

	wkt dev test [-v] [-k 關鍵字]   執行測試
	wkt dev build                   產生可攜式安裝包 dist/WKT-portable.zip
	wkt dev icon                    由 assets/icon.png 產生選單圖示 assets/icon.ico
	wkt dev update                  測試 → 打包 → 重新註冊右鍵選單（一次完成）
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from wkt.core.errors import WktError


NAME = "dev"
SUMMARY = "開發用：測試、打包、轉換選單圖示、更新（test／build／icon／update）"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PORTABLE_OUTPUT = PROJECT_ROOT / "dist" / "WKT-portable.zip"
ICON_SOURCE = PROJECT_ROOT / "assets" / "icon.png"
ICON_OUTPUT = PROJECT_ROOT / "assets" / "icon.ico"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

# 可攜式安裝包中，wkt/ 套件以外一定要包含的檔案。新增了需要一起發佈的檔案時，加在這裡。
EXTRA_FILES = (
	"wkt.cmd",
	"install.cmd",
	"scripts/install.ps1",
	"requirements.txt",
	"README.md",
	"docs/DEVELOPMENT.md",
	"assets/icon.png",
	"assets/icon.ico",
)


# ── build ────────────────────────────────────────────────────────────────
def collect_files(root: Path = PROJECT_ROOT) -> list[Path]:
	"""要放進安裝包的檔案：EXTRA_FILES + wkt/ 底下所有 .py。缺少任何必要檔案就 WktError。"""
	extra = [root / relative for relative in EXTRA_FILES]
	missing = [str(path) for path in extra if not path.is_file()]
	if missing:
		raise WktError("安裝包缺少必要檔案：\n  " + "\n  ".join(missing))
	package = sorted(path for path in (root / "wkt").rglob("*.py") if "__pycache__" not in path.parts)
	return [*extra, *package]


def build_portable(output: Path = PORTABLE_OUTPUT, root: Path = PROJECT_ROOT) -> int:
	files = collect_files(root)
	output.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
		for path in files:
			archive.write(path, path.relative_to(root).as_posix())
	return len(files)


# ── icon ─────────────────────────────────────────────────────────────────
def build_ico(png_images: list[tuple[int, bytes]]) -> bytes:
	"""組出 .ico 檔：每個尺寸都以 PNG 編碼（Vista 以上支援）。"""
	header = struct.pack("<HHH", 0, 1, len(png_images))
	offset = 6 + 16 * len(png_images)
	entries = b""
	payload = b""
	for size, data in png_images:
		dimension = 0 if size >= 256 else size  # ICO 以 0 代表 256
		entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset + len(payload))
		payload += data
	return header + entries + payload


def make_icon(source: Path = ICON_SOURCE, output: Path = ICON_OUTPUT) -> None:
	"""由 PNG 產生多尺寸 .ico：置中放進透明底的正方形再縮放。需要 OpenCV 與 numpy。"""
	from wkt.core.media import load_cv2, load_numpy

	cv2, np = load_cv2(), load_numpy()
	image = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
	if image is None:
		raise WktError(f"無法讀取圖示原圖：{source}")
	if image.ndim == 2:
		image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
	elif image.shape[2] == 3:
		image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

	height, width = image.shape[:2]
	side = max(width, height)
	square = np.zeros((side, side, 4), dtype=np.uint8)
	top, left = (side - height) // 2, (side - width) // 2
	square[top:top + height, left:left + width] = image

	png_images = []
	for size in ICON_SIZES:
		resized = cv2.resize(square, (size, size), interpolation=cv2.INTER_AREA)
		ok, encoded = cv2.imencode(".png", resized)
		if not ok:
			raise WktError(f"PNG 編碼失敗（{size}px）")
		png_images.append((size, encoded.tobytes()))
	output.write_bytes(build_ico(png_images))


# ── test ─────────────────────────────────────────────────────────────────
def run_tests(verbose: bool = False, keyword: str | None = None) -> None:
	tests_dir = PROJECT_ROOT / "tests"
	if not tests_dir.is_dir():
		raise WktError("找不到 tests 資料夾（可攜式安裝包不含測試；請在原始專案執行）。")
	command = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
	if verbose:
		command.append("-v")
	if keyword:
		command.extend(["-k", keyword])
	code = subprocess.run(command, cwd=PROJECT_ROOT).returncode
	if code != 0:
		raise WktError("測試未通過。", exit_code=code)


# ── 指令 ─────────────────────────────────────────────────────────────────
def _do_update() -> None:
	from wkt import menu

	run_tests()
	print(f"已建立：{PORTABLE_OUTPUT}（{build_portable()} 個檔案）")
	menu.register()


def configure_parser(parser: argparse.ArgumentParser) -> None:
	actions = parser.add_subparsers(dest="dev_action", metavar="<動作>", required=True)

	test = actions.add_parser("test", help="執行測試")
	test.add_argument("-v", "--verbose", dest="test_verbose", action="store_true", help="顯示每個測試")
	test.add_argument("-k", "--keyword", help="只執行名稱含此關鍵字的測試")

	actions.add_parser("build", help="產生可攜式安裝包 dist/WKT-portable.zip")
	actions.add_parser("icon", help="由 assets/icon.png 產生選單圖示 assets/icon.ico")
	actions.add_parser("update", help="測試 → 打包 → 重新註冊右鍵選單（測試失敗就中止）")


def run(args: argparse.Namespace) -> None:
	action = args.dev_action
	if action == "test":
		run_tests(args.test_verbose, args.keyword)
	elif action == "build":
		print(f"已建立：{PORTABLE_OUTPUT}（{build_portable()} 個檔案）")
	elif action == "icon":
		make_icon()
		print(f"已建立：{ICON_OUTPUT}（{', '.join(str(size) for size in ICON_SIZES)} px）")
	else:
		_do_update()
