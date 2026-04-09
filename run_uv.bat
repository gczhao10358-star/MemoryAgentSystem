@echo off
chcp 65001 > nul
echo 智忆助理 (MemoryMate) - UV启动器
echo =================================
echo.

:: 检查uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: 未找到uv，请先安装uv
    echo 安装命令: pip install uv
    pause
    exit /b 1
)

:: 创建数据目录
if not exist data mkdir data

echo.
echo 选择运行模式:
echo 1. 交互模式 (与AI对话)
echo 2. 演示模式 (自动演示)
echo 3. 系统测试 (验证安装)
echo.

set /p choice=请输入选项 (1/2/3):

if "%choice%"=="1" goto interactive
if "%choice%"=="2" goto demo
if "%choice%"=="3" goto test
goto end

:interactive
echo.
echo 启动交互模式...
uv run main.py
goto end

:demo
echo.
echo 启动演示模式...
uv run main.py --demo
goto end

:test
echo.
echo 运行系统测试...
uv run test_system.py
goto end

:end
echo.
pause
