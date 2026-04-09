@echo off
chcp 65001 > nul
echo 智忆助理 (MemoryMate) 启动器
echo ================================
echo.

:: 检查Python
python --version > nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请安装Python 3.8+
    pause
    exit /b 1
)

:: 检查依赖
echo 检查依赖...
pip show openai > nul 2>&1
if errorlevel 1 (
    echo 安装依赖...
    pip install -r requirements.txt
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
python main.py
goto end

:demo
echo.
echo 启动演示模式...
python main.py --demo
goto end

:test
echo.
echo 运行系统测试...
python test_system.py
goto end

:end
echo.
pause
