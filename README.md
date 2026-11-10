# WKT — Workflow Kit Tools

影片與圖片的小型命令列工具箱，並可加到檔案總管的右鍵選單。

## 需求

- Windows 10／11
- Python 3.10 以上（`py -3` 可執行）
- [FFmpeg](https://ffmpeg.org/)（`ffmpeg` 可在命令列執行，或以 WinGet 安裝）
- 只有 `to1080`、`to1088` 需要 OpenCV：`pip install -r requirements.txt`

不需要管理員權限，也不需要憑證或簽章。

## 使用

```
wkt                      列出所有指令
wkt <工具> --help        查看某個工具的參數
wkt togif input.mp4      範例：影片轉 GIF
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
scripts\register_menu.cmd       註冊（.mp4 右鍵 →「顯示更多選項」→ WKT）
scripts\unregister_menu.cmd     解除
wkt menu status                 查看目前是否已註冊
```

選單圖示使用 `assets/icon.ico`（由 `assets/icon.png` 轉換而來，換圖示請見開發指南）。選單只寫入目前使用者（HKCU）。Windows 11 的選單在第二層「顯示更多選項」，也可按 Shift+F10。
移動專案資料夾後，請重新執行一次註冊。

## 開發

新增工具、修改程式、發佈更新，請看 **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**。

```
scripts\test.cmd                執行測試
```
