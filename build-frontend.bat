@echo off
chcp 65001 >nul

echo =====================================
echo   构建前端面板
echo =====================================
echo.

:: 进入前端目录
cd /d "%~dp0\frontend"

:: 安装依赖
if not exist "node_modules" (
    echo 正在安装依赖...
    call npm install
)

:: 构建
echo.
echo 正在构建前端...
call npm run build

:: 检查结果
if exist "dist" (
    echo.
    echo [OK] 构建成功！
    echo.
    echo 前端文件已生成到: frontend/dist/
    echo.
    echo 现在可以启动后端服务，访问 http://localhost:8000 即可看到管理面板
    echo.
    echo 启动后端:
    echo   python main.py
) else (
    echo.
    echo [错误] 构建失败！
)

pause
