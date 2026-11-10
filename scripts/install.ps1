<#
.SYNOPSIS
  WKT 一鍵安裝：補齊 Python、ffmpeg、OpenCV，加入 PATH，註冊右鍵選單，最後執行 wkt doctor 確認。

.PARAMETER CheckOnly
  只執行 wkt doctor 檢查，不安裝或修改任何東西。
.PARAMETER Yes
  不詢問確認，直接執行。
.PARAMETER NoPath
  不修改使用者的 PATH。
.PARAMETER NoMenu
  不註冊右鍵選單。
#>
param(
	[switch]$CheckOnly,
	[switch]$Yes,
	[switch]$NoPath,
	[switch]$NoMenu
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$wkt = Join-Path $root 'wkt.cmd'

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Done($text) { Write-Host "    $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "    $text" -ForegroundColor Yellow }

function Update-SessionPath {
	# winget 安裝後，目前這個視窗的 PATH 不會自動更新，這裡重新讀取
	$machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
	$user = [Environment]::GetEnvironmentVariable('Path', 'User')
	$env:Path = "$machine;$user"
}

function Test-Native([scriptblock]$command) {
	# 執行外部程式並回傳是否成功；找不到程式也視為失敗，不拋例外
	try {
		& $command *> $null
		return ($LASTEXITCODE -eq 0)
	} catch {
		return $false
	}
}

function Test-Python {
	Test-Native { py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" }
}

function Test-FFmpeg {
	# 使用 WKT 自己的尋找邏輯（含 WinGet 安裝位置），結果與實際執行一致
	Test-Native { py -3 -c "import sys; sys.path.insert(0, sys.argv[1]); from wkt.core.ffmpeg import find_ffmpeg; find_ffmpeg()" $root }
}

function Test-OpenCV {
	Test-Native { py -3 -c "import cv2, numpy" }
}

function Test-InUserPath([string]$dir) {
	$raw = (Get-Item 'HKCU:\Environment').GetValue('Path', '', 'DoNotExpandEnvironmentNames')
	$entries = @($raw -split ';' | Where-Object { $_ })
	return [bool]($entries | Where-Object { $_.TrimEnd('\') -ieq $dir.TrimEnd('\') })
}

function Add-ToUserPath([string]$dir) {
	# 直接改 registry 並保留原本的 %變數% 寫法（SetEnvironmentVariable 會把它們展開成固定路徑）
	$key = Get-Item 'HKCU:\Environment'
	$raw = $key.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
	$entries = @($raw -split ';' | Where-Object { $_ })
	Set-ItemProperty -Path 'HKCU:\Environment' -Name 'Path' -Value (($entries + $dir) -join ';') -Type ExpandString

	# 通知 Explorer 與其他程式環境變數已變更，之後開啟的視窗才會讀到新的 PATH
	if (-not ('WktNative.Broadcast' -as [type])) {
		Add-Type -Namespace WktNative -Name Broadcast -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true, CharSet = System.Runtime.InteropServices.CharSet.Auto)]
public static extern System.IntPtr SendMessageTimeout(System.IntPtr hWnd, uint Msg, System.UIntPtr wParam, string lParam, uint fuFlags, uint uTimeout, out System.UIntPtr lpdwResult);
'@
	}
	$result = [UIntPtr]::Zero
	[void][WktNative.Broadcast]::SendMessageTimeout([IntPtr]0xffff, 0x1A, [UIntPtr]::Zero, 'Environment', 2, 5000, [ref]$result)
}

function Install-WithWinget([string]$id, [string]$displayName) {
	if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
		throw "找不到 winget，無法自動安裝 $displayName。請手動安裝後重新執行此腳本。"
	}
	& winget install --exact --id $id --accept-package-agreements --accept-source-agreements
	if ($LASTEXITCODE -ne 0) { throw "winget 安裝 $displayName 失敗（結束碼 $LASTEXITCODE）。" }
	Update-SessionPath
}

# ── 只檢查 ────────────────────────────────────────────────────────────────
if ($CheckOnly) {
	if (-not (Test-Python)) { Write-Host '找不到 Python 3.10 以上，無法執行檢查。請先執行不含 -CheckOnly 的安裝。' -ForegroundColor Red; exit 1 }
	& $wkt doctor
	exit $LASTEXITCODE
}

# ── 偵測現況並列出將要做的事 ───────────────────────────────────────────────
Write-Host "WKT 安裝（專案位置：$root）" -ForegroundColor White
$needPython = -not (Test-Python)
$needFFmpeg = $needPython -or -not (Test-FFmpeg)   # 沒有 Python 時無法判斷 ffmpeg，安裝完 Python 後再確認
$needOpenCV = $needPython -or -not (Test-OpenCV)
$needPath = (-not $NoPath) -and (-not (Test-InUserPath $root))

$plan = @()
if ($needPython) { $plan += '安裝 Python 3.12（winget）' }
if ($needFFmpeg) { $plan += '安裝 ffmpeg（winget；已安裝則略過）' }
if ($needOpenCV) { $plan += '安裝 OpenCV 與 numpy（pip，to1080／to1088 需要）' }
if ($needPath) { $plan += "把專案資料夾加入使用者 PATH，讓終端機可直接輸入 wkt" }
if (-not $NoMenu) { $plan += '註冊（或更新）檔案總管右鍵選單' }
$plan += '執行 wkt doctor 確認結果'

Write-Host '將執行：'
$plan | ForEach-Object { Write-Host "  - $_" }
if (-not $Yes) {
	$answer = Read-Host '繼續？(Y/n)'
	if ($answer -and $answer -notmatch '^[Yy]') { Write-Host '已取消。'; exit 1 }
}

# ── 安裝 ──────────────────────────────────────────────────────────────────
Write-Step 'Python'
if ($needPython) {
	Install-WithWinget 'Python.Python.3.12' 'Python'
	if (-not (Test-Python)) {
		throw 'Python 已安裝，但目前視窗還找不到。請關閉此視窗、重新執行 scripts\install.cmd。'
	}
}
Write-Done '可用'

Write-Step 'ffmpeg'
if (-not (Test-FFmpeg)) {
	Install-WithWinget 'Gyan.FFmpeg' 'ffmpeg'
	if (-not (Test-FFmpeg)) {
		throw 'ffmpeg 已安裝，但目前視窗還找不到。請關閉此視窗、重新執行 scripts\install.cmd。'
	}
}
Write-Done '可用'

Write-Step 'OpenCV／numpy'
if (-not (Test-OpenCV)) {
	& py -3 -m pip install -r (Join-Path $root 'requirements.txt')
	if ($LASTEXITCODE -ne 0) {
		Write-Warn '安裝失敗：to1080、to1088 暫時無法使用，其他功能不受影響。可稍後執行：py -3 -m pip install -r requirements.txt'
	} else {
		Write-Done '已安裝'
	}
} else {
	Write-Done '已安裝'
}

Write-Step 'PATH'
if ($NoPath) {
	Write-Warn '已略過（-NoPath）'
} elseif (Test-InUserPath $root) {
	Write-Done '專案資料夾已在使用者 PATH 中'
} else {
	Add-ToUserPath $root
	Write-Done '已加入使用者 PATH；請重新開啟終端機後，即可直接輸入 wkt'
}
if (-not (($env:Path -split ';') -contains $root)) { $env:Path = "$env:Path;$root" }  # 讓下方的 doctor 看得到

Write-Step '右鍵選單'
if ($NoMenu) {
	Write-Warn '已略過（-NoMenu）'
} else {
	& $wkt menu register
	if ($LASTEXITCODE -ne 0) { throw '註冊右鍵選單失敗。' }
}

Write-Step '最終檢查'
& $wkt doctor
exit $LASTEXITCODE
