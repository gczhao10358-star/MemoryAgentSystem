@echo off
chcp 65001 >nul
echo ======================================
echo    智忆助理 (MemoryMate) 启动器
echo ======================================
echo.

REM 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在
    pause
    exit /b 1
)

echo [1/2] 检查前端构建...
if not exist "frontend\dist\index.html" (
    echo [信息] 前端未构建，正在构建...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

echo [2/2] 启动服务...
echo.
echo ======================================
echo  服务地址: http://localhost:3000
echo  前端界面: http://localhost:3000/app
echo  API文档: http://localhost:3000/docs
echo ======================================
echo.

REM 使用端口 3000（避免 8000 被占用）
.venv\Scripts\python.exe api.py

pause
