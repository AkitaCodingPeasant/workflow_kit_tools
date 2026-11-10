# WKT 開發指南

這份文件說明專案的結構、慣例，以及「新增功能時該照著做的標準步驟」。
只想使用工具請看 [README.md](../README.md)。

目錄

1. [設計原則](#1-設計原則)
2. [開發環境](#2-開發環境)
3. [專案結構](#3-專案結構)
4. [運作原理](#4-運作原理)
5. [程式碼慣例](#5-程式碼慣例)
6. [核心函式庫（wkt.core）](#6-核心函式庫wktcore)
7. [標準步驟：新增一個工具](#7-標準步驟新增一個工具)
8. [標準步驟：新增右鍵選單項目](#8-標準步驟新增右鍵選單項目)
9. [標準步驟：修改既有工具或核心](#9-標準步驟修改既有工具或核心)
10. [測試指南](#10-測試指南)
11. [發佈與更新](#11-發佈與更新)
12. [右鍵選單的限制與設計決策](#12-右鍵選單的限制與設計決策)
13. [疑難排解](#13-疑難排解)
14. [提交前檢查清單](#14-提交前檢查清單)
15. [附錄：重構對照表](#15-附錄重構對照表)

---

## 1. 設計原則

1. **一個工具一個檔案。** 新增工具只要在 `wkt/tools/` 放一個 `.py`，不需要改任何登記表。
2. **共用的事只寫一次。** 找 ffmpeg、驗證輸入、決定輸出檔名、錯誤處理，都在 `wkt/core/`。工具檔只寫自己獨有的邏輯。
3. **工具不自己結束程式。** 失敗時 `raise WktError(...)`，由 `wkt/cli.py` 統一印訊息與決定結束碼。
4. **純函式優先。** 「組 ffmpeg 指令」、「算輸出路徑」這類邏輯寫成不做 I/O 的函式，才能不靠 ffmpeg 就測試。
5. **需要才 import。** OpenCV、numpy、winreg 都在函式內才載入，沒用到它們的功能不需要安裝。
6. **不需要權限。** 所有功能都在使用者層級運作，不寫 HKLM、不裝憑證。

## 2. 開發環境

| 項目 | 說明 |
|---|---|
| Python | 3.10 以上。程式檔一律用 `from __future__ import annotations`，所以 `str \| None` 等型別寫法在 3.10 可用 |
| FFmpeg | 端對端測試與實際使用需要；找不到時相關測試會自動略過 |
| OpenCV／numpy | `pip install -r requirements.txt`；`to1080`、`to1088` 需要；找不到時相關測試會自動略過 |
| 編碼 | 所有文字檔使用 UTF-8（見 `.editorconfig`）；Python 讀寫檔案時請明確指定 `encoding="utf-8"` |
| 縮排 | `.py` 使用 **Tab**（沿用專案原本風格，`.editorconfig` 已設定） |

```
scripts\test.cmd                         跑全部測試
py -3 -m wkt --help                      不經 wkt.cmd 直接執行
set WKT_DEBUG=1                          未預期的例外顯示完整 traceback（除錯用）
```

## 3. 專案結構

```
workflow_kit_tools/
├── wkt.cmd                  指令入口（右鍵選單與使用者都呼叫它）
├── requirements.txt         選用相依套件（OpenCV、numpy）
├── README.md                使用說明
├── .editorconfig  .gitignore
│
├── wkt/                     ← 程式本體（Python 套件）
│   ├── __init__.py          版本號 __version__
│   ├── __main__.py          讓 `python -m wkt` 可用
│   ├── cli.py               統一入口：組 argparse、分派、處理錯誤
│   ├── registry.py          自動探索工具、檢查「指令契約」
│   ├── menu.py              右鍵選單的設定（MENU）與註冊／解除
│   ├── core/                所有工具共用的功能（見第 6 節）
│   │   ├── errors.py        WktError
│   │   ├── paths.py         輸入驗證、輸出路徑規則
│   │   ├── ffmpeg.py        找 ffmpeg、執行 ffmpeg
│   │   └── media.py         OpenCV 逐幀處理流程
│   └── tools/               ← 每個檔案 = 一個工具
│       ├── _template.py     新工具範本（底線開頭，不會被載入）
│       └── togif.py  reencode.py  tobt709.py  toframe.py  to1080.py  to1088.py
│
├── tests/                   單元測試與端對端測試
├── scripts/                 維護用腳本（註冊選單、測試、打包、更新）
├── docs/                    文件（本檔案）
├── assets/                  icon.png（原圖）與 icon.ico（右鍵選單用，由 make_icon.py 產生）
├── dist/                    打包輸出（自動產生，不納入版本控制）
└── archive/                 舊檔備份（不納入版本控制）
```

**「這個東西該放哪？」速查**

| 我要… | 放在 |
|---|---|
| 新增一個指令 | `wkt/tools/<name>.py` |
| 兩個以上工具都用得到的函式 | `wkt/core/` |
| 只有單一工具用的函式 | 留在該工具檔內 |
| 新增右鍵選單項目 | `wkt/menu.py` 的 `MENU` |
| 維護用的批次檔或腳本 | `scripts/` |
| 測試 | `tests/test_<主題>.py` |
| 文件 | `docs/` |

## 4. 運作原理

```
wkt.cmd togif input.mp4 --fps 12
   │  設定 PYTHONPATH 後執行 `py -3 -m wkt ...`
   ▼
wkt/__main__.py → wkt/cli.py: main()
   │  build_parser() ← wkt/registry.py: load_commands()
   │       ├ 內建指令：wkt/menu.py
   │       └ 工具：自動掃描 wkt/tools/*.py（略過 _ 開頭）
   │  每個指令模組變成一個 argparse 子指令（module.configure_parser）
   ▼
args.handler(args)  =  wkt/tools/togif.py: run(args)
   │  成功：印「完成：…」，回傳 None → 結束碼 0
   │  失敗：raise WktError → cli 印到 stderr，結束碼 = exc.exit_code
```

### 指令模組契約

`wkt/tools/` 下的每個模組都必須提供這四個名稱，`registry.validate_command()` 與測試會檢查：

| 名稱 | 型別 | 說明 |
|---|---|---|
| `NAME` | `str` | 指令名稱。小寫英數字、英文字母開頭；慣例上與檔名相同 |
| `SUMMARY` | `str` | 一行說明，顯示在 `wkt --help` |
| `configure_parser(parser)` | 函式 | 把這個工具自己的參數加到 `parser`（不要再建立新的 ArgumentParser） |
| `run(args)` | 函式 | 執行工具。成功回傳 `None`；失敗 `raise WktError` |

指令名稱不可重複（包含內建的 `menu`），重複時載入就會報錯。

## 5. 程式碼慣例

**檔案開頭**：每個 `.py` 以 `from __future__ import annotations` 開頭。

**命名**

- 工具檔名＝指令名稱，全小寫（`togif.py`、`tobt709.py`）。
- 模組層級常數全大寫：`DEFAULT_FPS`、`TAG`。
- 純函式用動詞開頭：`build_ffmpeg_command`、`derive_output`、`validate_args`。

**預設輸出檔名**（沒指定 `-o` 時，一律輸出在輸入檔同一層，用 `derive_output` 產生）

| 情況 | 規則 | 範例 |
|---|---|---|
| 同格式轉換 | `<檔名>_<TAG><原副檔名>` | `a.mp4` → `a_reencoded.mp4` |
| 換格式 | `<檔名><新副檔名>` | `a.mp4` → `a.gif` |
| 輸出多個檔案 | 同層同名資料夾 | `a.mp4` → `a/000000.png` |

`TAG` 是模組內的常數，並要在 `-o` 的說明文字中寫出（例如 `未指定時會自動加上 _reencoded`）。

**使用者訊息**（皆為繁體中文）

| 時機 | 格式 | 輸出到 |
|---|---|---|
| 成功 | `print(f"完成：{輸出路徑}")` | stdout |
| 失敗 | `raise WktError("具體原因")`，訊息要說明問題與對象，例如 `找不到輸入檔案：{path}` | stderr（由 cli 負責） |
| 非致命提醒 | `print(訊息, file=sys.stderr)` | stderr |

**錯誤處理與結束碼**

| 結束碼 | 意義 |
|---|---|
| 0 | 成功 |
| 1 | 一般失敗（`WktError` 預設值、未預期的例外） |
| ffmpeg 的結束碼 | ffmpeg 執行失敗時沿用（由 `run_ffmpeg` 設定） |
| 2 | 命令列參數錯誤（argparse 的標準行為） |
| 130 | 使用者以 Ctrl+C 中止 |

- 可預期的失敗一律 `WktError`；不要 `print` 後 `return 1`，也不要 `sys.exit()`。
- 不要用 `except Exception` 吞掉錯誤；`cli.main` 已有最外層的保底處理。

**其他**

- 需要 OpenCV／numpy 時，使用 `core.media.load_cv2()`／`load_numpy()`，不要在檔案頂端 `import cv2`。
- 呼叫 ffmpeg 一律透過 `core.ffmpeg.find_ffmpeg()` 與 `run_ffmpeg()`，不要寫死 `"ffmpeg"`。
- 不修改使用者的輸入檔；輸出前確認不與輸入相同（`ensure_not_same`）。
- 寫到使用者資料夾的檔案若需要暫存，先寫暫存檔、成功後再 `replace`，失敗時要清掉暫存檔（參考 `togif.py`）。

## 6. 核心函式庫（wkt.core）

### `core/errors.py`

```python
WktError(message: str, exit_code: int = 1)
```

可預期的失敗。`message` 會原樣印到 stderr。

### `core/paths.py`

| 函式 | 用途 |
|---|---|
| `require_input_file(raw) -> Path` | 輸入必須存在且是檔案，否則 `WktError` |
| `derive_output(input_path, output_arg, *, tag=None, suffix=None) -> Path` | 決定輸出路徑。有 `-o` 就用它；否則依 `tag` 與 `suffix` 規則（見第 5 節）產生 |
| `ensure_not_same(input_path, output_path)` | 輸出與輸入相同時 `WktError` |

### `core/ffmpeg.py`

| 函式 | 用途 |
|---|---|
| `find_ffmpeg() -> str` | 依 PATH → WinGet → 常見資料夾的順序找 ffmpeg；找不到 `WktError` |
| `run_ffmpeg(command, *, stdout=None)` | 執行指令；ffmpeg 失敗時 `WktError`，結束碼沿用 ffmpeg 的 |

### `core/media.py`（OpenCV 逐幀處理）

| 名稱 | 用途 |
|---|---|
| `load_cv2()`／`load_numpy()` | 延遲載入；缺套件時給出安裝提示 |
| `add_media_arguments(parser, tag)` | 加上 `input`、`-o`、`--type` 三個共用參數 |
| `run_frame_tool(args, *, tag, frame_fn, expected_size, output_size)` | 完整流程：驗證 → 判斷圖片／影片 → 逐幀套用 `frame_fn` → 輸出 |
| `detect_media_type`、`transform_image`、`transform_video` | 上面流程用到的零件，也可單獨使用 |

`frame_fn` 接收一幀（numpy 陣列）並回傳處理後的一幀。`to1080.py` 與 `to1088.py` 是完整範例。

## 7. 標準步驟：新增一個工具

> 以下以新增「`tomp3`：把影片的聲音轉成 MP3」為例。請依序完成每一步。

### 步驟 1：複製範本

複製 `wkt/tools/_template.py` 為 `wkt/tools/tomp3.py`（檔名不可底線開頭、全小寫）。

### 步驟 2：填寫契約

- `NAME = "tomp3"`（與檔名一致）
- `SUMMARY = "將影片的聲音轉成 MP3"`

### 步驟 3：寫純函式（組指令）

```python
def build_ffmpeg_command(ffmpeg_path: str, input_path: Path, output_path: Path, bitrate: str) -> list[str]:
	return [
		ffmpeg_path, "-hide_banner", "-y",
		"-i", str(input_path),
		"-vn", "-c:a", "libmp3lame", "-b:a", bitrate,
		str(output_path),
	]
```

第一個參數固定是 `ffmpeg_path`，不做任何 I/O，方便測試。

### 步驟 4：定義參數

```python
def configure_parser(parser: argparse.ArgumentParser) -> None:
	parser.add_argument("input", help="輸入影片或音訊路徑")
	parser.add_argument("-o", "--output", help="輸出路徑；未指定時會使用同層同名 .mp3")
	parser.add_argument("--bitrate", default=DEFAULT_BITRATE, help=f"MP3 位元率，預設 {DEFAULT_BITRATE}")
```

- 輸入檔參數固定叫 `input`，輸出固定是 `-o/--output`（輸出多個檔案時用 `-o/--output-dir`）。
- 每個選項的預設值都要寫在 `help` 裡。

### 步驟 5：寫 `run`

```python
def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	output_path = derive_output(input_path, args.output, suffix=".mp3")
	ensure_not_same(input_path, output_path)

	run_ffmpeg(build_ffmpeg_command(find_ffmpeg(), input_path, output_path, args.bitrate))
	print(f"完成：{output_path}")
```

這個流程（驗證輸入 → 決定輸出 → 防止覆蓋 → 執行 → 回報）是所有 ffmpeg 類工具的標準骨架。
如果是 OpenCV 逐幀類工具，改成呼叫 `run_frame_tool`（見 `to1080.py`）。

### 步驟 6：寫測試

在 `tests/test_commands.py` 加入（純函式測試，不需要 ffmpeg）：

```python
def test_tomp3(self) -> None:
	cmd = tomp3.build_ffmpeg_command(FFMPEG, SRC, Path("out.mp3"), "128k")
	self.assertIn("libmp3lame", cmd)
	self.assertEqual(cmd[cmd.index("-b:a") + 1], "128k")
	self.assertEqual(cmd[-1], "out.mp3")
```

並記得在檔案頂端 `from wkt.tools import ... tomp3`。若工具有端對端行為，在 `tests/test_cli.py` 的 `EndToEndTests` 加一個用 `run_cli("tomp3", ...)` 的測試。

### 步驟 7：更新工具清單測試

在 `tests/test_registry.py` 把 `"tomp3"` 加進 `EXPECTED_TOOLS`。
（這份清單是刻意要求手動維護的：新增或誤刪工具時測試都會提醒你。）

### 步驟 8：執行驗證

```
scripts\test.cmd                       全部測試必須通過
wkt tomp3 --help                       確認參數說明正確
wkt tomp3 某個影片.mp4                  實際跑一次，確認輸出檔案
wkt tomp3 不存在.mp4                    確認錯誤訊息與結束碼（echo %errorlevel% 應為 1）
```

### 步驟 9：更新文件

- `README.md` 的工具表加一列（工具、功能、預設輸出）。
- 若新增了選用相依套件，加進 `requirements.txt` 並在 README 的需求說明。

### 步驟 10（選用）：加到右鍵選單

見下一節。

**新增工具的完成標準**：契約齊全、有測試、`scripts\test.cmd` 通過、實際跑過一次、README 已更新。

## 8. 標準步驟：新增右鍵選單項目

只需要修改 `wkt/menu.py` 最上方的 `MENU`：

```python
MENU: dict[str, tuple[MenuItem, ...]] = {
	".mp4": (
		MenuItem("togif", "轉換成 .gif"),
		MenuItem("reencode", "重新編碼"),
		MenuItem("tomp3", "轉成 MP3"),        # ← 新增一行
	),
	".mov": (                                # ← 新增檔案類型
		MenuItem("reencode", "重新編碼"),
	),
}
```

1. `MenuItem` 的第一個參數必須是 `wkt/tools/` 裡已存在的 `NAME`；打錯時註冊與測試（`test_menu_only_references_existing_tools`）都會失敗。
2. 順序即選單顯示順序。
3. 副檔名必須以 `.` 開頭。
4. 重新註冊：`wkt menu register`（或雙擊 `scripts\register_menu.cmd`）。註冊會先清掉該副檔名舊的項目再寫入，所以刪掉的項目也會一併消失。
5. 在檔案總管對該類型檔案按右鍵 →「顯示更多選項」→ **WKT**，確認項目出現並實際點一次。
6. 若是**移除某個副檔名**：先 `wkt menu unregister`（趁它還在 `MENU` 裡），再從 `MENU` 刪除，最後 `wkt menu register`。否則舊副檔名的項目會殘留在 registry。

選單項目實際執行的指令是 `"<專案>\wkt.cmd" <工具> "%1"`，`%1` 是被點選的檔案。

## 9. 標準步驟：修改既有工具或核心

1. **先跑測試**，確認修改前是綠燈。
2. **修改 `wkt/core/` 前，先搜尋有哪些工具在用它**（搜尋函式名稱）。核心函式的行為變更會影響所有工具。
3. **預設值、預設輸出檔名、參數名稱視為對外介面**：使用者的腳本與右鍵選單依賴它們。要改請在文件中註明，並提高版本號（見第 11 節）。
4. 修改完成後：新增或更新對應測試 → `scripts\test.cmd` → 實際跑一次受影響的工具。
5. 行為有變更時更新 `README.md` 與本文件。

**判斷要不要抽到 `core/`**：同樣的程式碼在第二個工具出現時，才抽出來；只有一個工具用就留在該工具檔內。

## 10. 測試指南

```
scripts\test.cmd                                  全部測試
py -3 -m unittest tests.test_commands -v          單一檔案
py -3 -m unittest discover -s tests -k togif      以關鍵字篩選
```

| 檔案 | 測什麼 | 需要 ffmpeg／OpenCV |
|---|---|---|
| `tests/test_registry.py` | 指令契約、名稱不重複、`MENU` 引用的工具存在、`_template.py` 合規 | 否 |
| `tests/test_core.py` | `core/paths.py` 的規則 | 否 |
| `tests/test_commands.py` | 各工具「組 ffmpeg 指令」的純函式 | 否 |
| `tests/test_cli.py` | CLI 行為、各工具端對端（用 ffmpeg 即時產生測試影片） | 是，沒裝會自動略過 |

撰寫原則：

- **能用純函式測就不要跑 ffmpeg。** 純函式測試快、不依賴環境。
- 端對端測試用 `testsrc` 即時產生小檔案，不在 repo 放影片素材。
- 測試只寫到暫存資料夾（`tempfile`），不要碰專案目錄。
- 測試**不要**呼叫 `wkt menu register`，避免改到真實的 registry。

## 11. 發佈與更新

**版本號**：`wkt/__init__.py` 的 `__version__`（`wkt --version` 會顯示）。

- 修正錯誤：第三位（1.0.0 → 1.0.1）
- 新增工具或選項：第二位（1.0.0 → 1.1.0）
- 改變既有預設值、參數名稱或輸出檔名：第一位（1.0.0 → 2.0.0）

**在這台電腦更新**：雙擊 `scripts\update.cmd`。它會依序：跑測試（失敗就中止）→ 產生 `dist\WKT-portable.zip` → 重新註冊右鍵選單。

**打包**：`py -3 scripts\build_portable.py` 產生 `dist\WKT-portable.zip`。內容是 `wkt/` 底下所有 `.py`、`wkt.cmd`、`requirements.txt`、README、本文件，以及兩個選單腳本。新增了需要一起打包的非 `.py` 檔案時，要把它加進 `scripts/build_portable.py` 的 `EXTRA_FILES`。

**在其他電腦安裝**：

1. 解壓縮到固定資料夾（之後不要搬動）。
2. 確認有 Python 3.10+ 與 ffmpeg；需要 `to1080`／`to1088` 就 `pip install -r requirements.txt`。
3. 雙擊 `scripts\register_menu.cmd`。

**更新其他電腦**：覆蓋解壓縮到原位置即可。選單設定（`MENU`）有變動時，再執行一次 `scripts\register_menu.cmd`。只改工具邏輯不需要重新註冊。

## 12. 右鍵選單的限制與設計決策

- **只有第二層（傳統選單）。** 原因：Windows 11 的第一層新式選單需要「套件身分」，也就是簽章的 MSIX 套件。這代表要建立自簽憑證、把它加入整台電腦的信任清單、並依賴特定版本的 Windows SDK 工具，部署與散布都複雜，也有安全顧慮。本專案已決定不採用，並移除所有相關程式。若未來要重新評估，需要正式的程式碼簽章憑證。
- **只寫入 HKCU**：`HKCU\Software\Classes\SystemFileAssociations\<副檔名>\shell\WorkflowKitTools`。不需要管理員權限，也只影響目前使用者。
- **選單圖示**：registry 的 `Icon` 不支援 PNG，只吃 `.ico`／exe／dll。圖示的來源是 `assets/icon.png`，由 `scripts/make_icon.py` 轉成 `assets/icon.ico`（含 16～256px 多種尺寸，透明底、圖案置中）。**更換圖示的步驟**：換掉 `assets/icon.png` → `py -3 scripts\make_icon.py` → `wkt menu register`。`icon.ico` 要一併保留，因為註冊時直接使用它，不需要 OpenCV。
- **路徑是絕對路徑**：選單指令寫死了 `wkt.cmd` 的位置，所以專案資料夾移動後要重新註冊。
- **解除安裝**：`wkt menu unregister`（或 `scripts\unregister_menu.cmd`），再刪除專案資料夾即可，沒有其他殘留。

## 13. 疑難排解

| 症狀 | 原因與處理 |
|---|---|
| 選單沒有圖示 | 確認 `assets/icon.ico` 存在（沒有就執行 `py -3 scripts\make_icon.py`），再 `wkt menu register`；圖示若沒更新，重新啟動檔案總管 |
| 右鍵選單看不到 WKT | Windows 11 要按「顯示更多選項」或 Shift+F10；再用 `wkt menu status` 確認是否已註冊 |
| 移動資料夾後選單沒反應 | 重新執行 `scripts\register_menu.cmd` |
| 找不到 ffmpeg | 安裝 ffmpeg（例如 `winget install Gyan.FFmpeg`）並重新開啟終端機，使 PATH 生效 |
| `缺少 opencv-python` | `pip install -r requirements.txt` |
| 尺寸必須是 1920x1088 | `to1080` 只接受 1920x1088；`to1088` 只接受 1920x1080 |
| 從選單執行時視窗一閃而過 | 在終端機直接執行同一個指令，就能看到完整訊息 |
| 看到簡短錯誤想知道細節 | `set WKT_DEBUG=1` 後重跑，會顯示完整 traceback |
| `ValueError: ... NAME 必須是…` | 新工具不符合指令契約，見第 4 節 |
| `ValueError: 指令名稱重複` | 兩個模組的 `NAME` 相同，改掉其中一個 |

## 14. 提交前檢查清單

- [ ] `scripts\test.cmd` 全部通過
- [ ] 新增／修改的行為有對應測試
- [ ] 實際執行過受影響的工具
- [ ] 新工具符合契約，檔名＝`NAME`，且 `EXPECTED_TOOLS` 已更新
- [ ] 錯誤一律 `raise WktError`，沒有 `sys.exit` 或自己 `return 1`
- [ ] 沒有在檔案頂端 `import cv2` / `numpy` / `winreg`
- [ ] 沒有寫死 `"ffmpeg"`（使用 `find_ffmpeg()`）
- [ ] `README.md` 的工具表與本文件已同步
- [ ] 預設值／參數／輸出檔名有變動時，已調整 `__version__`
- [ ] 檔案為 UTF-8，`.py` 用 Tab 縮排

## 15. 附錄：重構對照表

本專案原本所有檔案散落在根目錄。重構後的對應如下：

| 舊位置 | 新位置 |
|---|---|
| `wkt.py` | `wkt/cli.py`、`wkt/registry.py`（工具改為自動探索） |
| `togif.py` `reencode.py` `tobt709.py` `toframe.py` `to1080.py` `to1088.py` | `wkt/tools/` 內同名檔案 |
| `register_wkt_mp4.py` | `wkt/menu.py`（`wkt menu register`） |
| `register_wkt_mp4.cmd` | `scripts/register_menu.cmd` |
| `update_wkt.cmd` | `scripts/update.cmd` |
| `wkt_shell/build_portable.py` | `scripts/build_portable.py` |
| `WKT-portable-win11-x64.zip` | `dist/WKT-portable.zip` |
| `icon.png` | `assets/icon.png`（現在用於右鍵選單圖示，見第 12 節） |
| `wkt_shell/` 其餘（MSIX、DLL、簽章） | 已移除（見第 12 節） |

**行為差異**（重構時刻意調整的）：

- 所有 ffmpeg 工具都改用 `find_ffmpeg()`（原本只有 `togif` 會搜尋 WinGet 安裝位置）。
- `to1080`／`to1088` 現在也會檢查輸入是檔案、輸出不會覆蓋輸入。
- 輸入了不存在的指令時，結束碼由 1 改為 2（argparse 標準行為）。
- `togif` 失敗時會清掉暫存檔。
- 指令名稱仍不分大小寫；原本用來去除舊檔名前綴的相容寫法（`wkt toimg` 等）已移除。
- `wkt menu register` 會先清除該副檔名舊的選單項目再寫入。

舊檔案的完整備份在 `archive/pre-refactor-backup.zip`。
