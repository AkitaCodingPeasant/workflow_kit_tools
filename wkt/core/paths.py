from __future__ import annotations

from pathlib import Path

from wkt.core.errors import WktError


def require_input_file(raw: str) -> Path:
	"""驗證輸入必須是存在的檔案，回傳 Path。"""
	path = Path(raw).expanduser()
	if not path.exists():
		raise WktError(f"找不到輸入檔案：{path}")
	if not path.is_file():
		raise WktError(f"輸入路徑不是檔案：{path}")
	return path


def derive_output(
	input_path: Path,
	output_arg: str | None,
	*,
	tag: str | None = None,
	suffix: str | None = None,
	out_dir: str | None = None,
) -> Path:
	"""決定輸出路徑。

	- 使用者有指定 -o 時一律照用。
	- 否則輸出在輸入檔同一層：檔名加上 _<tag>，副檔名預設沿用輸入檔，
	  指定 suffix（例如 ".gif"）時改用該副檔名。
	"""
	if output_arg and out_dir:
		raise WktError("-o／--output 與 --out-dir 不能同時指定")
	if output_arg:
		return Path(output_arg).expanduser()
	name = input_path.stem + (f"_{tag}" if tag else "")
	parent = Path(out_dir).expanduser() if out_dir else input_path.parent
	return parent / (name + (input_path.suffix if suffix is None else suffix))


def ensure_output_available(output_path: Path, force: bool, *, directory: bool = False) -> None:
	"""確認既有輸出是否可安全使用；不建立或刪除任何路徑。"""
	if output_path.parent.exists() and not output_path.parent.is_dir():
		raise WktError(f"輸出資料夾路徑已存在但不是資料夾：{output_path.parent}")
	if not output_path.exists():
		return
	if directory:
		if not output_path.is_dir():
			raise WktError(f"輸出路徑已存在但不是資料夾：{output_path}")
		if any(output_path.iterdir()) and not force:
			raise WktError(f"輸出資料夾已存在且不是空的：{output_path}（加上 --force 可覆蓋）")
	else:
		if not output_path.is_file():
			raise WktError(f"輸出路徑已存在但不是檔案：{output_path}")
		if not force:
			raise WktError(f"輸出檔案已存在：{output_path}（加上 --force 可覆蓋）")


def output_status(output_path: Path) -> str:
	if not output_path.exists():
		return "新增"
	if output_path.is_dir() and not any(output_path.iterdir()):
		return "新增"
	return "覆蓋"


def ensure_not_same(input_path: Path, output_path: Path) -> None:
	"""避免輸出覆蓋到輸入檔。"""
	if input_path.resolve() == output_path.resolve():
		raise WktError("輸出路徑不能和輸入路徑相同")
