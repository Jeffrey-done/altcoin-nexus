@echo off
chcp 65001 >nul

echo =====================================
echo   Altcoin Nexus 前端开发服务器
echo =====================================
echo.

:: 进入前端目录
cd /d "%~dp0\frontend"

:: 检查依赖
if not exist "node_modules" (
    echo 正在安装依赖...
    call npm install
)

:: 启动开发服务器
echo.
echo 启动开发服务器...
echo 访问地址: http://localhost:3000
echo.
call npm run dev

pause
