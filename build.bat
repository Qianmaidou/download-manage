@echo off
chcp 65001 >nul
echo ========================================
echo   下载文件夹整理工具 — EXE 构建脚本
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.7+
    pause
    exit /b 1
)

:: 安装 PyInstaller
echo [1/3] 检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo        正在安装 PyInstaller...
    pip install pyinstaller
)

:: 清理旧构建
echo [2/3] 清理旧构建...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

:: 构建
echo [3/3] 开始构建 EXE...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "download-manage" ^
    --add-data "lib;lib" ^
    --hidden-import "tkinter" ^
    --hidden-import "lib.classifier" ^
    --hidden-import "lib.config_loader" ^
    --hidden-import "lib.file_ops" ^
    --hidden-import "lib.history" ^
    --hidden-import "lib.reporter" ^
    --hidden-import "lib.utils" ^
    --clean ^
    gui.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   构建成功！
    echo   输出: dist\download-manage.exe
    echo ========================================
    echo.
    echo 使用方法:
    echo   1. 将 dist\download-manage.exe 复制到任意位置
    echo   2. 将 config.json 放在同一目录下
    echo   3. 双击运行即可
) else (
    echo.
    echo [错误] 构建失败，请检查上方错误信息。
)

pause
