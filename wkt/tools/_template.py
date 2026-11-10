"""新工具範本：複製此檔、改名（不要底線開頭），再依註解修改即可。

檔名會成為指令名稱的慣例（wkt/tools/foo.py → NAME = "foo"）。
底線開頭的檔案不會被自動載入，所以這份範本不會出現在 wkt 的工具清單中。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wkt.core.args import add_input_argument
from wkt.core.ffmpeg import find_ffmpeg, probe_duration, run_ffmpeg
from wkt.core.paths import derive_output, ensure_not_same, require_input_file


# ── 1. 工具資訊（registry 會檢查這五個名稱都存在）──────────────────────────
NAME = "template"  # 指令名稱：小寫英數字，開頭為英文字母，且不可與其他工具重複
SUMMARY = "範例工具：把影片複製一份"  # 一行說明，會顯示在 `wkt --help`
# 分類：任何影片／圖片都可能用到 → "general"（出現在預設的 wkt --help）；
# 只在特定規格或情境才用得到 → "special"（只出現在 wkt help special，也不能放進右鍵選單）。
# 工具不可使用 "manage"（那是 menu／doctor 這類內建指令專用）。
CATEGORY = "general"

DEFAULT_TAG = "copy"  # 預設輸出檔名後綴，例如 input_copy.mp4


# ── 2. 純函式：組指令、算路徑。不做 I/O，才能寫單元測試 ──────────────────────
def build_ffmpeg_command(ffmpeg_path: str, input_path: Path, output_path: Path) -> list[str]:
	return [
		ffmpeg_path,
		"-hide_banner",
		"-y",
		"-i",
		str(input_path),
		"-c",
		"copy",
		str(output_path),
	]


# ── 3. 命令列參數：只定義這個工具自己的參數 ─────────────────────────────────
def configure_parser(parser: argparse.ArgumentParser) -> None:
	add_input_argument(parser, "輸入影片路徑")  # 固定用這個：支援多個檔案，批次由 wkt.batch 處理
	parser.add_argument("-o", "--output", help=f"輸出路徑；未指定時會自動加上 _{DEFAULT_TAG}")


# ── 4. 執行：成功就印「完成：…」；失敗一律 raise WktError，不要自己 print／exit ──
# 注意：run() 每次只會拿到「一個」檔案（args.input 是字串）。多檔案由 wkt.batch 逐一呼叫，
# 工具本身不需要處理迴圈、不需要處理 -o 與多檔案的衝突。
def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	output_path = derive_output(input_path, args.output, tag=DEFAULT_TAG)
	ensure_not_same(input_path, output_path)

	ffmpeg_path = find_ffmpeg()
	# duration（秒）讓 run_ffmpeg 能顯示進度條；輸出是圖片等「沒有長度」的工具可以省略
	run_ffmpeg(
		build_ffmpeg_command(ffmpeg_path, input_path, output_path),
		duration=probe_duration(ffmpeg_path, input_path),
	)
	print(f"完成：{output_path}")
