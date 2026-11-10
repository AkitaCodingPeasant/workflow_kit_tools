"""建立可攜式安裝包 dist/WKT-portable.zip。

內容 = 程式本體（wkt/ 底下所有 .py）+ 啟動腳本 + 文件。
解壓到固定資料夾後執行 scripts/register_menu.cmd 即可使用。
"""

from __future__ import annotations

import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "dist" / "WKT-portable.zip"
EXTRA_FILES = (
	"wkt.cmd",
	"requirements.txt",
	"README.md",
	"docs/DEVELOPMENT.md",
	"assets/icon.png",
	"assets/icon.ico",
	"scripts/make_icon.py",
	"scripts/register_menu.cmd",
	"scripts/unregister_menu.cmd",
)


def collect_files() -> list[Path]:
	package_files = sorted(
		path
		for path in (ROOT / "wkt").rglob("*.py")
		if "__pycache__" not in path.parts
	)
	extra_files = [ROOT / relative for relative in EXTRA_FILES]
	missing = [path for path in extra_files if not path.is_file()]
	if missing:
		raise FileNotFoundError(", ".join(str(path) for path in missing))
	return [*extra_files, *package_files]


def main() -> None:
	files = collect_files()
	OUTPUT.parent.mkdir(exist_ok=True)
	with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
		for path in files:
			archive.write(path, path.relative_to(ROOT).as_posix())
	print(f"已建立：{OUTPUT}（{len(files)} 個檔案）")


if __name__ == "__main__":
	main()
