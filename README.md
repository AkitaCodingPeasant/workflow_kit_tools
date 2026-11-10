# WKT — Workflow Kit Tools

影片與圖片的小型命令列工具箱，並可加到檔案總管的右鍵選單。

## 需求

- Windows 10／11
- Python 3.10 以上（`py -3` 可執行）
- [FFmpeg](https://ffmpeg.org/)（`ffmpeg` 可在命令列執行，或以 WinGet 安裝）
- 只有 `to1080`、`to1088` 需要 OpenCV：`pip install -r requirements.txt`

不需要管理員權限，也不需要憑證或簽章。

## 安裝

雙擊根目錄的 **`install.cmd`**（**這是唯一需要手動點的一步**，之後所有操作都用 `wkt` 指令），它會：

1. 補齊缺少的 Python、ffmpeg（用 `winget`）與 OpenCV（用 `pip`）
2. 把專案資料夾加入使用者 PATH，讓終端機可直接輸入 `wkt`
3. 註冊右鍵選單
4. 執行 `wkt doctor` 確認結果

開始前會列出將要做的事並詢問確認。想先看看環境有沒有問題：`install.cmd -CheckOnly` 或 `wkt doctor`（都不會修改任何東西）。

安裝後請**重新開啟終端機**，PATH 才會生效。

## 使用

管理指令：`wkt doctor`（檢查環境）、`wkt install`（修復安裝）、`wkt menu`（右鍵選單）、`wkt dev`（開發用）。其餘都是處理檔案的工具。

```
wkt                      列出所有指令
wkt <工具> --help        查看某個工具的參數
wkt togif input.mp4      範例：影片轉 GIF
wkt togif a.mp4 b.mp4    一次處理多個檔案（顯示 [1/2]…並彙整成功／失敗）
wkt -v reencode a.mp4    顯示 ffmpeg 的完整輸出（預設只顯示進度條）
wkt doctor               檢查執行環境，並對每個問題給出修復指令
```

| 工具 | 功能 | 預設輸出 |
|---|---|---|
| `togif` | 將影片壓成小尺寸 GIF | `input.gif` |
| `reencode` | 重新編碼成 H.264/AAC | `input_reencoded.mp4` |
| `tobt709` | BT.601 色域轉 BT.709 | `input_bt709.mp4` |
| `topng` | `.webp`／`.jpg`／`.bmp` 等圖片轉 PNG | `input.png` |
| `toframe` | 影片拆幀成 PNG | 同名資料夾 |
| `to1080` | 1920x1088 裁成 1920x1080 | `input_1080.ext` |
| `to1088` | 1920x1080 補成 1920x1088 | `input_1088.ext` |

也可以用 `python -m wkt <工具> ...`，效果相同。

## 右鍵選單

```
wkt menu register               註冊（.mp4 右鍵 →「顯示更多選項」→ WKT）
wkt menu unregister             解除
wkt menu status                 查看目前是否已註冊
```

多選檔案按右鍵只會開**一個**視窗並依序處理；全部成功會顯示結果、3 秒後自動關閉，有失敗則停住讓你看原因。選單圖示使用 `assets/icon.ico`（由 `assets/icon.png` 轉換而來，換圖示請見開發指南）。選單只寫入目前使用者（HKCU）。Windows 11 的選單在第二層「顯示更多選項」，也可按 Shift+F10。
移動專案資料夾後，請重新執行 `wkt menu register`。

## 開發

新增工具、修改程式、發佈更新，請看 **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**。

```
wkt dev test                     執行測試
wkt dev build                    產生可攜式安裝包 dist\WKT-portable.zip
wkt dev update                   測試 → 打包 → 重新註冊選單
wkt dev icon                     由 assets/icon.png 重新產生選單圖示
```
