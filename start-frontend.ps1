# 前端开发服务器启动脚本

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  Altcoin Nexus 前端开发服务器" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Node.js
try {
    $nodeVersion = node --version
    Write-Host "[OK] Node.js 版本: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未安装 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

# 进入前端目录
Set-Location "$PSScriptRoot\frontend"

# 检查依赖
if (-not (Test-Path "node_modules")) {
    Write-Host ""
    Write-Host "正在安装依赖..." -ForegroundColor Yellow
    npm install
}

# 启动开发服务器
Write-Host ""
Write-Host "启动开发服务器..." -ForegroundColor Green
Write-Host ""
Write-Host "访问地址: http://localhost:3000" -ForegroundColor Cyan
Write-Host "后端 API: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Gray
Write-Host ""

npm run dev
