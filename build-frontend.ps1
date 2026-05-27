# 构建前端并部署到后端

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  构建前端面板" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 进入前端目录
Set-Location "$PSScriptRoot\frontend"

# 检查 Node.js
try {
    $nodeVersion = node --version
    Write-Host "[OK] Node.js 版本: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未安装 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

# 安装依赖
if (-not (Test-Path "node_modules")) {
    Write-Host ""
    Write-Host "正在安装依赖..." -ForegroundColor Yellow
    npm install
}

# 构建
Write-Host ""
Write-Host "正在构建前端..." -ForegroundColor Yellow
npm run build

# 检查构建结果
if (Test-Path "dist") {
    Write-Host ""
    Write-Host "[OK] 构建成功！" -ForegroundColor Green
    Write-Host ""
    Write-Host "前端文件已生成到: frontend/dist/" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "现在可以启动后端服务，访问 http://localhost:8000 即可看到管理面板" -ForegroundColor Green
    Write-Host ""
    Write-Host "启动后端:" -ForegroundColor Yellow
    Write-Host "  python main.py" -ForegroundColor White
    Write-Host "  或" -ForegroundColor Gray
    Write-Host "  uvicorn api:app --port 8000" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "[错误] 构建失败！" -ForegroundColor Red
}
