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
) -> Path:
	"""決定輸出路徑。

	- 使用者有指定 -o 時一律照用。
	- 否則輸出在輸入檔同一層：檔名加上 _<tag>，副檔名預設沿用輸入檔，
	  指定 suffix（例如 ".gif"）時改用該副檔名。
	"""
	if output_arg:
		return Path(output_arg).expanduser()
	name = input_path.stem + (f"_{tag}" if tag else "")
	return input_path.with_name(name + (input_path.suffix if suffix is None else suffix))


def ensure_not_same(input_path: Path, output_path: Path) -> None:
	"""避免輸出覆蓋到輸入檔。"""
	if input_path.resolve() == output_path.resolve():
		raise WktError("輸出路徑不能和輸入路徑相同")
