# 打包脚本：用完整版 Python 生成单文件 Windows 可执行程序
$ErrorActionPreference = "Stop"

# 1) 定位完整版 Python（含 tkinter 运行库）
$py = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    throw "未找到完整版 Python：$py"
}

# 2) 确保依赖齐全
Write-Host "检查并安装依赖..."
& $py -m pip install akshare matplotlib pyinstaller --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败" }

# 3) 打包
$proj = "C:\xinwen-h\stock_monitor"
Push-Location $proj
try {
    Write-Host "开始打包（onefile 单文件 + collect akshare，可能需要几分钟）..."
    & $py -m PyInstaller --noconfirm --clean --windowed --onefile `
        --collect-all akshare `
        --name "股票盯盘助手" `
        --distpath "dist" --workpath "build" --specpath "." `
        main.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }
    Write-Host "打包完成：dist\股票盯盘助手.exe"
    Get-Item "dist\股票盯盘助手.exe" | Select-Object FullName, @{N='SizeMB';E={[math]::Round($_.Length/1MB,1)}}
}
finally {
    Pop-Location
}
