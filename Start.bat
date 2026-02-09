@echo off
chcp 65001 >nul
echo ====================================
echo 正在启动 SmartTavern 应用程序...
echo ====================================

REM 检查 uv 是否安装
where uv >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 uv，请先安装: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

REM 启动服务（自动构建前端 + 单端口运行）
echo 正在启动服务（首次运行会自动构建前端）...
uv run smarttavern --serve

pause
