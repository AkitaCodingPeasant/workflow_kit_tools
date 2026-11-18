<#
.SYNOPSIS
  WKT 一鍵安裝：選擇 Python 安裝方式（全域／虛擬環境），補齊 Python、ffmpeg、OpenCV，
  加入 PATH，註冊右鍵選單，最後執行 wkt doctor 確認。

.PARAMETER CheckOnly
  只執行 wkt doctor 檢查，不安裝或修改任何東西。
.PARAMETER Yes
  不詢問確認，直接執行。
.PARAMETER NoPath
  不修改使用者的 PATH。
.PARAMETER NoMenu
  不註冊右鍵選單。
.PARAMETER Mode
  Python 安裝方式：global（全域 Python）或 venv（專案內的 .venv 虛擬環境）。
  不指定時會詢問；搭配 -Yes 則沿用目前的方式（第一次安裝為 global）。
  已安裝後再次執行可切換安裝方式。
#>
param(
	[switch]$CheckOnly,
	[switch]$Yes,
	[switch]$NoPath,
	[switch]$NoMenu,
	[ValidateSet('', 'global', 'venv')]
	[string]$Mode = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$wkt = Join-Path $root 'wkt.cmd'
$modeFile = Join-Path $root '.wkt-env'
$venvDir = Join-Path $root '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$modeText = @{ global = '全域 Python'; venv = '虛擬環境（.venv）' }

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

function Invoke-TargetPython {
	# 用目前選定的安裝方式執行 Python：venv 用 .venv 的 python.exe，global 用 py -3
	if ($script:Mode -eq 'venv') { & $venvPython @args } else { & py -3 @args }
}

function Test-Venv {
	Test-Native { & $venvPython -c "import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)" }
}

function Test-Packages {
	# 有 .venv 但壞掉時也視為缺少，交給後面的步驟處理
	Test-Native { Invoke-TargetPython -c "import cv2, numpy, questionary" }
}

function Get-InstalledMode {
	# 回傳目前記錄的安裝方式；從未用新版安裝過時回傳 $null
	if (-not (Test-Path -LiteralPath $modeFile)) { return $null }
	$value = (Get-Content -LiteralPath $modeFile -Raw -Encoding UTF8).Trim().ToLower()
	if ($value -in @('global', 'venv')) { return $value }
	return $null
}

function Select-Mode([string]$current) {
	$default = if ($current) { $current } else { 'global' }
	Write-Host ''
	Write-Host 'Python 安裝方式：'
	Write-Host '  1) 全域 Python      套件裝進系統的 Python，與其他程式共用'
	Write-Host '  2) 虛擬環境（.venv） 套件裝在專案資料夾內，不影響系統 Python'
	if ($current) { Write-Host "  目前使用：$($modeText[$current])" -ForegroundColor DarkGray }
	$defaultKey = if ($default -eq 'venv') { '2' } else { '1' }
	while ($true) {
		$answer = (Read-Host "請選擇 (1/2，直接按 Enter = $defaultKey)").Trim()
		if (-not $answer) { return $default }
		if ($answer -eq '1') { return 'global' }
		if ($answer -eq '2') { return 'venv' }
		Write-Warn '請輸入 1 或 2。'
	}
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
$installedMode = Get-InstalledMode
if ($installedMode) { Write-Host "目前的 Python 安裝方式：$($modeText[$installedMode])" }
if (-not $Mode) {
	if ($Yes) {
		$Mode = if ($installedMode) { $installedMode } else { 'global' }
	} else {
		$Mode = Select-Mode $installedMode
	}
}
$previousMode = if ($installedMode) { $installedMode } else { 'global' }   # 舊版安裝沒有記錄檔，視為全域

$needPython = -not (Test-Python)
$needVenv = ($Mode -eq 'venv') -and ($needPython -or -not (Test-Venv))
$needFFmpeg = $needPython -or -not (Test-FFmpeg)   # 沒有 Python 時無法判斷 ffmpeg，安裝完 Python 後再確認
$needPackages = $needPython -or $needVenv -or -not (Test-Packages)
$needPath = (-not $NoPath) -and (-not (Test-InUserPath $root))

$plan = @()
if ($Mode -ne $previousMode) { $plan += "切換 Python 安裝方式：$($modeText[$previousMode]) → $($modeText[$Mode])" }
if ($needPython) { $plan += '安裝 Python 3.12（winget）' }
if ($needVenv) { $plan += "在專案資料夾建立虛擬環境：$venvDir" }
if ($needFFmpeg) { $plan += '安裝 ffmpeg（winget；已安裝則略過）' }
if ($needPackages) { $plan += "安裝 OpenCV、numpy、questionary 到$($modeText[$Mode])（pip）" }
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
		throw 'Python 已安裝，但目前視窗還找不到。請關閉此視窗、重新雙擊 install.cmd。'
	}
}
Write-Done '可用'

Write-Step "Python 安裝方式：$($modeText[$Mode])"
if ($Mode -eq 'venv') {
	if (-not (Test-Venv)) {
		& py -3 -m venv $venvDir
		if ($LASTEXITCODE -ne 0 -or -not (Test-Venv)) { throw "建立虛擬環境失敗：$venvDir" }
		Write-Done "已建立 $venvDir"
	} else {
		Write-Done "使用既有的 $venvDir"
	}
}
# 寫入記錄檔後，wkt.cmd（以及下方的右鍵選單註冊、doctor）就會改用對應的 Python
[IO.File]::WriteAllText($modeFile, "$Mode`r`n", (New-Object Text.UTF8Encoding $false))
if ($Mode -eq 'global' -and (Test-Path -LiteralPath $venvDir)) {
	Write-Warn ".venv 已不再使用，需要時可手動刪除：$venvDir"
}
Write-Done '已設定'

Write-Step 'ffmpeg'
if (-not (Test-FFmpeg)) {
	Install-WithWinget 'Gyan.FFmpeg' 'ffmpeg'
	if (-not (Test-FFmpeg)) {
		throw 'ffmpeg 已安裝，但目前視窗還找不到。請關閉此視窗、重新雙擊 install.cmd。'
	}
}
Write-Done '可用'

Write-Step 'OpenCV／numpy／questionary'
if (-not (Test-Packages)) {
	Invoke-TargetPython -m pip install -r (Join-Path $root 'requirements.txt')
	if ($LASTEXITCODE -ne 0) {
		$pipHint = if ($Mode -eq 'venv') { '.venv\Scripts\python.exe' } else { 'py -3' }
		Write-Warn "安裝失敗：to1080、to1088 與互動選單暫時無法使用，其他功能不受影響。可稍後執行：$pipHint -m pip install -r requirements.txt"
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
