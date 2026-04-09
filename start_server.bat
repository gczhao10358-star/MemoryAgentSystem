@echo off
chcp 65001 >nul
echo ======================================
echo    智忆助理 (MemoryMate) 服务启动器
echo ======================================
echo.

REM 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先创建虚拟环境
    echo 运行: uv venv
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
.venv\Scripts\python.exe -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [信息] 安装 FastAPI 依赖...
    uv pip install fastapi uvicorn pydantic python-multipart pyyaml
)

echo [2/3] 检查数据目录...
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo [3/3] 启动服务...
echo.
echo ======================================
echo  服务启动成功
echo  API文档: http://localhost:8000/docs
echo  前端界面: http://localhost:8000/app
echo ======================================
echo.
echo 按 Ctrl+C 停止服务
echo.

REM 启动服务
.venv\Scripts\python.exe api.py

pause
