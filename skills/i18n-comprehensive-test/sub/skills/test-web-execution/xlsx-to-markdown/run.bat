@echo off
REM XLSX to Markdown 转换工具 - Windows 批处理包装器
REM 此脚本确保在 Windows 上正确调用 Python 脚本

REM 检测并设置 Python 路径
set PYTHON_CMD=python

REM 检查常见 Python 安装位置
if not exist "%PYTHON_CMD%" (
    if exist "C:\Python310\python.exe" (
        set PYTHON_CMD=C:\Python310\python.exe
    ) else if exist "C:\Python39\python.exe" (
        set PYTHON_CMD=C:\Python39\python.exe
    ) else if exist "C:\Python38\python.exe" (
        set PYTHON_CMD=C:\Python38\python.exe
    ) else if exist "%SystemRoot%\System32\python.exe" (
        set PYTHON_CMD=%SystemRoot%\System32\python.exe
    )
)

REM 获取当前脚本所在目录
set SCRIPT_DIR=%~dp0

REM 调用 Python 脚本，传递所有参数
"%PYTHON_CMD%" "%SCRIPT_DIR%xlsx_to_markdown.py" %*
