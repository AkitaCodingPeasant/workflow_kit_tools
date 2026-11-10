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
7. **工具只處理「單一檔案」。** 多檔案、進度、結果畫面都由外層（`wkt.batch`、`wkt.launcher`、`core.ffmpeg`）負責，新工具不需要重複實作。

## 2. 開發環境

| 項目 | 說明 |
|---|---|
| Python | 3.10 以上。程式檔一律用 `from __future__ import annotations`，所以 `str \| None` 等型別寫法在 3.10 可用 |
| FFmpeg | 端對端測試與實際使用需要；找不到時相關測試會自動略過 |
| OpenCV／numpy | `pip install -r requirements.txt`；`to1080`、`to1088` 需要；找不到時相關測試會自動略過 |
| 編碼 | 所有文字檔使用 UTF-8（見 `.editorconfig`）；Python 讀寫檔案時請明確指定 `encoding="utf-8"` |
| 縮排 | `.py` 使用 **Tab**（沿用專案原本風格，`.editorconfig` 已設定） |

```
wkt dev test                             跑全部測試（可加 -v 或 -k 關鍵字）
py -3 -m wkt --help                      不經 wkt.cmd 直接執行
set WKT_DEBUG=1                          未預期的例外顯示完整 traceback（除錯用）
```

## 3. 專案結構

```
workflow_kit_tools/
├── wkt.cmd                  指令入口（右鍵選單與使用者都呼叫它）
├── install.cmd              一鍵安裝入口（唯一需要手動雙擊的檔案）
├── requirements.txt         選用相依套件（OpenCV、numpy）
├── README.md                使用說明
├── .editorconfig  .gitignore
│
├── wkt/                     ← 程式本體（Python 套件）
│   ├── __init__.py          版本號 __version__
│   ├── __main__.py          讓 `python -m wkt` 可用
│   ├── cli.py               統一入口：組 argparse、分派、處理錯誤
│   ├── registry.py          自動探索工具、檢查「指令契約」
│   ├── batch.py             多檔案批次：逐一執行並彙整成功／失敗
│   ├── launcher.py          右鍵選單執行階段：多選彙整、結果畫面、失敗停住
│   ├── menu.py              右鍵選單的設定（MENU）與註冊／解除／狀態
│   ├── doctor.py            wkt doctor：環境檢查與修復建議
│   ├── install.py           wkt install：重新執行安裝（修復用）
│   ├── dev.py               wkt dev：測試、打包、轉換圖示、更新
│   ├── core/                所有工具共用的功能（見第 6 節）
│   │   ├── errors.py        WktError
│   │   ├── args.py          共用的命令列參數（輸入檔）
│   │   ├── paths.py         輸入驗證、輸出路徑規則
│   │   ├── ffmpeg.py        找 ffmpeg、執行 ffmpeg（含進度條）、讀取影片長度
│   │   ├── ui.py            進度條、詳細模式、批次標籤
│   │   └── media.py         OpenCV 逐幀處理流程
│   └── tools/               ← 每個檔案 = 一個工具
│       ├── _template.py     新工具範本（底線開頭，不會被載入）
│       └── togif.py  reencode.py  tobt709.py  toframe.py  to1080.py  to1088.py
│
├── tests/                   單元測試與端對端測試
├── scripts/install.ps1      安裝程式本體（由 install.cmd 與 wkt install 呼叫）
├── docs/                    文件（本檔案）
├── assets/                  icon.png（原圖）與 icon.ico（右鍵選單用，由 wkt dev icon 產生）
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
| 維護／開發用的功能（測試、打包…） | `wkt/dev.py`，新增一個 `wkt dev` 動作 |
| 安裝流程的修改 | `scripts/install.ps1`（注意要保留 UTF-8 BOM） |
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
cli.dispatch(args)
   │  工具（args.input 是清單）→ wkt/batch.py: run_batch() 逐一呼叫 run()
   │  內建指令（menu、doctor）→ 直接呼叫 run()
   ▼
wkt/tools/togif.py: run(args)        ← 每次只拿到一個檔案（args.input 是字串）
   │  成功：印「完成：…」，回傳 None → 結束碼 0
   │  失敗：raise WktError → cli 印到 stderr，結束碼 = exc.exit_code
```

### 多檔案與批次（wkt/batch.py）

- 所有工具的輸入參數都用 `add_input_argument()` 宣告（`nargs="+"`），所以 `wkt togif a.mp4 b.mp4 c.mp4` 可以一次處理多個。
- 只有一個檔案：行為和以前完全一樣（錯誤直接往上拋、結束碼沿用）。
- 多個檔案：逐一執行，顯示 `[i/n]`；**某個檔案失敗不會中斷後面的**；最後顯示「完成 x／n」與失敗清單，只要有失敗結束碼就是 1。
- 多個檔案時不能指定 `-o`／`--output-dir`（會拒絕），輸出放在各檔案旁邊。

### 右鍵選單的執行階段（wkt/launcher.py）

選單登記的指令是 `"wkt.cmd" --from-menu <工具> "%1"`。Explorer 多選 N 個檔案時會**同時啟動 N 個程序**，所以：

```
N 個程序各自：① 把自己的檔案寫進佇列 %LOCALAPPDATA%\WKT\queue\<工具>\
              ② 搶「領導者鎖」（msvcrt.locking，程序結束時由作業系統自動釋放）
搶到的（1 個）：等 0.5 秒收集大家的檔案 → 一次批次處理 → 顯示結果
沒搶到的（N-1 個）：直接結束，視窗立刻關閉
```

- **不會漏檔**：每個程序一定是「先登記、再搶鎖」，領導者放開鎖之後會再檢查一次佇列。
- **結果畫面**：全部成功 → 顯示結果，3 秒後自動關閉；有任何失敗 → 停住顯示原因，按 Enter 才關閉。
- 進度條：ffmpeg 類工具依影片長度、OpenCV 類工具依幀數顯示；只在互動式終端機顯示，`wkt -v` 或重新導向時不顯示。

### 指令模組契約

`wkt/tools/` 下的每個模組（以及內建的 `menu`、`doctor`）都必須提供這四個名稱，`registry.validate_command()` 與測試會檢查：

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
| `run_ffmpeg(command, *, stdout=None, duration=None)` | 執行指令。預設隱藏 ffmpeg 日誌並顯示進度條（`duration` 為輸出總秒數，沒給就不顯示進度）；失敗時印出 ffmpeg 的錯誤並 `WktError`，結束碼沿用 ffmpeg 的；`wkt -v` 下原樣顯示完整輸出 |
| `probe_duration(ffmpeg_path, input_path) -> float \| None` | 讀取媒體長度（秒）；圖片或讀不到時回傳 `None` |
| `parse_timecode(text) -> float \| None` | `"3"`、`"00:00:05"`、`"1:02.5"` → 秒數 |

### `core/args.py`

| 函式 | 用途 |
|---|---|
| `add_input_argument(parser, help_text)` | 宣告「一個或多個輸入檔」。**所有工具都要用它**，才會自動支援多檔案；`run()` 仍然只會拿到單一檔案 |

### `core/ui.py`

| 名稱 | 用途 |
|---|---|
| `Progress(total, label=None)` | 單行進度條；`total` 是 `None` 時不顯示；只在互動式終端機且非詳細模式時顯示。`update(value)`／`close()` |
| `set_verbose()`／`is_verbose()` | 詳細模式（`wkt -v` 或環境變數 `WKT_VERBOSE=1`） |
| `set_label(text)` | 批次處理時進度條前面的文字（由 `wkt.batch` 設定，工具不需要碰） |

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
	add_input_argument(parser, "輸入影片或音訊路徑")
	parser.add_argument("-o", "--output", help="輸出路徑；未指定時會使用同層同名 .mp3")
	parser.add_argument("--bitrate", default=DEFAULT_BITRATE, help=f"MP3 位元率，預設 {DEFAULT_BITRATE}")
```

- 輸入檔一律用 `add_input_argument()`（來自 `wkt.core.args`），不要自己 `add_argument("input")`：這樣才會自動支援多檔案。輸出固定是 `-o/--output`（輸出一個資料夾時用 `-o/--output-dir`）。
- 每個選項的預設值都要寫在 `help` 裡。

### 步驟 5：寫 `run`

```python
def run(args: argparse.Namespace) -> None:
	input_path = require_input_file(args.input)
	output_path = derive_output(input_path, args.output, suffix=".mp3")
	ensure_not_same(input_path, output_path)

	ffmpeg_path = find_ffmpeg()
	run_ffmpeg(
		build_ffmpeg_command(ffmpeg_path, input_path, output_path, args.bitrate),
		duration=probe_duration(ffmpeg_path, input_path),
	)
	print(f"完成：{output_path}")
```

這個流程（驗證輸入 → 決定輸出 → 防止覆蓋 → 執行 → 回報）是所有 ffmpeg 類工具的標準骨架。

- `run()` **每次只會拿到一個檔案**（`args.input` 是字串），不要自己寫迴圈；多檔案由 `wkt.batch` 處理。
- `duration` 讓 `run_ffmpeg` 能顯示進度條。輸出是圖片、沒有「長度」的工具（如 `topng`）可以省略。
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
wkt dev test                           全部測試必須通過
wkt tomp3 --help                       確認參數說明正確
wkt tomp3 某個影片.mp4                  實際跑一次，確認輸出檔案
wkt tomp3 不存在.mp4                    確認錯誤訊息與結束碼（echo %errorlevel% 應為 1）
```

### 步驟 9：更新文件

- `README.md` 的工具表加一列（工具、功能、預設輸出）。
- 若新增了選用相依套件，加進 `requirements.txt` 並在 README 的需求說明。

### 步驟 10（選用）：加到右鍵選單

見下一節。

**新增工具的完成標準**：契約齊全、有測試、`wkt dev test` 通過、實際跑過一次、README 已更新。

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
4. 重新註冊：`wkt menu register`。註冊會先清掉該副檔名舊的項目再寫入，所以刪掉的項目也會一併消失。
5. 在檔案總管對該類型檔案按右鍵 →「顯示更多選項」→ **WKT**，確認項目出現並實際點一次。
6. 若是**移除某個副檔名**：先 `wkt menu unregister`（趁它還在 `MENU` 裡），再從 `MENU` 刪除，最後 `wkt menu register`。否則舊副檔名的項目會殘留在 registry。

選單項目實際執行的指令是 `"<專案>\wkt.cmd" <工具> "%1"`，`%1` 是被點選的檔案。

## 9. 標準步驟：修改既有工具或核心

1. **先跑測試**，確認修改前是綠燈。
2. **修改 `wkt/core/` 前，先搜尋有哪些工具在用它**（搜尋函式名稱）。核心函式的行為變更會影響所有工具。
3. **預設值、預設輸出檔名、參數名稱視為對外介面**：使用者的腳本與右鍵選單依賴它們。要改請在文件中註明，並提高版本號（見第 11 節）。
4. 修改完成後：新增或更新對應測試 → `wkt dev test` → 實際跑一次受影響的工具。
5. 行為有變更時更新 `README.md` 與本文件。

**判斷要不要抽到 `core/`**：同樣的程式碼在第二個工具出現時，才抽出來；只有一個工具用就留在該工具檔內。

## 10. 測試指南

```
wkt dev test                                      全部測試
py -3 -m unittest tests.test_commands -v          單一檔案
py -3 -m unittest discover -s tests -k togif      以關鍵字篩選
```

| 檔案 | 測什麼 | 需要 ffmpeg／OpenCV |
|---|---|---|
| `tests/test_registry.py` | 指令契約、名稱不重複、`MENU` 引用的工具存在、`_template.py` 合規 | 否 |
| `tests/test_core.py` | `core/paths.py` 的規則、時間碼解析、進度條 | 否 |
| `tests/test_batch.py` | 批次執行：單檔／多檔／失敗不中斷／`-o` 衝突 | 否 |
| `tests/test_doctor.py` | `wkt doctor` 的檢查與結束碼 | 否 |
| `tests/test_dev.py` | `wkt dev`（打包、圖示）與 `wkt install`；防止 `install.ps1` 遺失 BOM | 部分需要 OpenCV |
| `tests/test_commands.py` | 各工具「組 ffmpeg 指令」的純函式 | 否 |
| `tests/test_cli.py` | CLI 行為、各工具端對端、批次、進度條（用 ffmpeg 即時產生測試影片） | 是，沒裝會自動略過 |
| `tests/test_launcher.py` | 佇列、領導者鎖；實際同時啟動多個程序，驗證只有一個負責處理（約 8 秒） | 部分需要 ffmpeg |

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

**在這台電腦更新**：`wkt dev update`。它會依序：跑測試（失敗就中止）→ 產生 `dist\WKT-portable.zip` → 重新註冊右鍵選單。

**打包**：`wkt dev build` 產生 `dist\WKT-portable.zip`。內容是 `wkt/` 底下所有 `.py`，加上 `wkt/dev.py` 裡 `EXTRA_FILES` 列出的檔案（`wkt.cmd`、`install.cmd`、`scripts/install.ps1`、`requirements.txt`、README、本文件、圖示）。新增了需要一起打包的非 `.py` 檔案時，要把它加進 `EXTRA_FILES`（缺檔時打包會直接失敗並列出缺少的檔案）。

**在其他電腦安裝**：

1. 解壓縮到固定資料夾（之後不要搬動）。
2. 雙擊根目錄的 `install.cmd`（**整個流程唯一需要手動點的一步**，之後都用 `wkt` 指令）。它會依序：補齊 Python 與 ffmpeg（`winget`）和 OpenCV（`pip`）→ 把專案資料夾加入使用者 PATH → 註冊右鍵選單 → 執行 `wkt doctor` 確認。開始前會列出將要做的事並詢問確認。

`install.cmd` 的參數：`-CheckOnly`（只檢查，不改任何東西）、`-Yes`（不詢問）、`-NoPath`（不改 PATH）、`-NoMenu`（不註冊選單）。裝好之後要修復或重裝，用 `wkt install`（參數 `--yes`、`--no-path`、`--no-menu`）；只想檢查用 `wkt doctor`。第一次安裝必須是 `install.cmd`，因為那時電腦上可能還沒有 Python。

安裝後 PATH 要**重新開啟終端機**才會生效，在那之前請用完整路徑或 `.\wkt`。
沒有 `winget` 的電腦（舊版 Windows 10）請手動安裝 Python、ffmpeg 後再執行。剛用 winget 裝好的程式，若目前視窗還找不到，請關掉視窗重新執行一次。

**更新其他電腦**：覆蓋解壓縮到原位置即可。選單設定（`MENU`）或選單指令格式有變動時，再執行一次 `wkt menu register`（`wkt doctor` 會在選單設定過舊時提醒）。只改工具邏輯不需要重新註冊。

## 12. 右鍵選單的限制與設計決策

- **只有第二層（傳統選單）。** 原因：Windows 11 的第一層新式選單需要「套件身分」，也就是簽章的 MSIX 套件。這代表要建立自簽憑證、把它加入整台電腦的信任清單、並依賴特定版本的 Windows SDK 工具，部署與散布都複雜，也有安全顧慮。本專案已決定不採用，並移除所有相關程式。若未來要重新評估，需要正式的程式碼簽章憑證。
- **只寫入 HKCU**：`HKCU\Software\Classes\SystemFileAssociations\<副檔名>\shell\WorkflowKitTools`。不需要管理員權限，也只影響目前使用者。
- **選單圖示**：registry 的 `Icon` 不支援 PNG，只吃 `.ico`／exe／dll。圖示的來源是 `assets/icon.png`，由 `wkt dev icon` 轉成 `assets/icon.ico`（含 16～256px 多種尺寸，透明底、圖案置中）。**更換圖示的步驟**：換掉 `assets/icon.png` → `wkt dev icon` → `wkt menu register`。`icon.ico` 要一併保留，因為註冊時直接使用它，不需要 OpenCV。
- **路徑是絕對路徑**：選單指令寫死了 `wkt.cmd` 的位置，所以專案資料夾移動後要重新註冊。`wkt menu status`／`wkt doctor` 會區分兩種狀況：**設定較舊**（指令格式更新，舊指令仍可用，只是警告）與**位置不存在**（資料夾被搬走，選單已失效，視為失敗）。
- **多選與結果畫面**見第 4 節「右鍵選單的執行階段」。這套機制只在選單指令（`--from-menu`）啟用；在終端機直接執行 `wkt` 時不會有 0.5 秒的收集等待，也不會有自動關閉的倒數。
- **解除安裝**：`wkt menu unregister`，再刪除專案資料夾即可，沒有其他殘留。

## 13. 疑難排解

| 症狀 | 原因與處理 |
|---|---|
| 選單沒有圖示 | 確認 `assets/icon.ico` 存在（沒有就執行 `wkt dev icon`），再 `wkt menu register`；圖示若沒更新，重新啟動檔案總管 |
| 右鍵選單看不到 WKT | Windows 11 要按「顯示更多選項」或 Shift+F10；再用 `wkt menu status` 確認是否已註冊 |
| 移動資料夾後選單沒反應 | 重新執行 `wkt menu register` |
| 找不到 ffmpeg | 安裝 ffmpeg（例如 `winget install Gyan.FFmpeg`）並重新開啟終端機，使 PATH 生效 |
| `缺少 opencv-python` | `pip install -r requirements.txt` |
| 尺寸必須是 1920x1088 | `to1080` 只接受 1920x1088；`to1088` 只接受 1920x1080 |
| 從選單執行時視窗一閃而過 | 全部成功時會顯示結果、3 秒後自動關閉；失敗則會停住等你按 Enter。若連失敗都一閃而過，先執行 `wkt doctor`，再在終端機直接執行同一個指令查看 |
| 不確定環境哪裡有問題 | 執行 `wkt doctor`：逐項檢查並附修復指令；`install.cmd -CheckOnly` 效果相同 |
| 沒有看到進度條 | 進度條只在互動式終端機顯示；使用了 `-v`、或輸出被重新導向時不會顯示 |
| 想看 ffmpeg 完整輸出 | `wkt -v <工具> ...`，或設定環境變數 `WKT_VERBOSE=1` |
| 多選檔案時有些檔案沒處理 | 先看結果視窗的「失敗的檔案」清單；多選時所有檔案由同一個視窗處理，不會每個檔案各開一個 |
| 看到簡短錯誤想知道細節 | `set WKT_DEBUG=1` 後重跑，會顯示完整 traceback |
| `ValueError: ... NAME 必須是…` | 新工具不符合指令契約，見第 4 節 |
| `ValueError: 指令名稱重複` | 兩個模組的 `NAME` 相同，改掉其中一個 |

## 14. 提交前檢查清單

- [ ] `wkt dev test` 全部通過
- [ ] 新增／修改的行為有對應測試
- [ ] 實際執行過受影響的工具
- [ ] 新工具符合契約，檔名＝`NAME`，且 `EXPECTED_TOOLS` 已更新
- [ ] 錯誤一律 `raise WktError`，沒有 `sys.exit` 或自己 `return 1`
- [ ] 沒有在檔案頂端 `import cv2` / `numpy` / `winreg`
- [ ] 沒有寫死 `"ffmpeg"`（使用 `find_ffmpeg()`）
- [ ] 輸入參數用 `add_input_argument()`，`run()` 沒有自己處理多檔案迴圈
- [ ] 修改選單指令格式時，確認 `wkt doctor` 會提示舊註冊「設定較舊」，並調整版本號
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
| `register_wkt_mp4.cmd` | `wkt menu register` |
| `update_wkt.cmd` | `wkt dev update` |
| `wkt_shell/build_portable.py` | `wkt dev build` |
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

**v1.2.0 的變更**（UX 優化）：

- 所有工具接受多個輸入檔；右鍵多選只開一個視窗並顯示 `[i/n]`。
- ffmpeg 預設只顯示進度條，失敗時才印出 ffmpeg 的錯誤；`wkt -v` 恢復完整輸出。
- 選單執行：全部成功自動關閉、有失敗就停住。選單登記的指令多了 `--from-menu`，**升級後要重新註冊**（`wkt doctor` 會提醒）。
- 新增 `wkt doctor` 與一鍵安裝 `install.cmd`。
- 找不到 ffmpeg 的訊息現在附上安裝指令。

**v1.3.0 的變更**（所有操作收進 `wkt` 指令）：

- 根目錄只剩 `install.cmd` 一個需要手動雙擊的入口；`scripts/` 只留 `install.ps1`。
- 新增 `wkt dev test｜build｜icon｜update`，取代原本的 `test.cmd`、`update.cmd`、`build_portable.py`、`make_icon.py`。
- 新增 `wkt install`（修復用）；註冊／解除選單原本就是 `wkt menu register｜unregister`，`register_menu.cmd`、`unregister_menu.cmd` 已移除。
- **已移除的腳本**：`scripts/register_menu.cmd`、`unregister_menu.cmd`、`test.cmd`、`update.cmd`、`build_portable.py`、`make_icon.py`。若有捷徑指向它們，請改用上述 `wkt` 指令。

舊檔案的完整備份在 `archive/pre-refactor-backup.zip`。
