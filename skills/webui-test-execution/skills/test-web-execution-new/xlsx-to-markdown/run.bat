@echo off
REM XLSX to Markdown 转换工具 - Windows 批处理包装器

set PYTHON_CMD=python
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

set SCRIPT_DIR=%~dp0
"%PYTHON_CMD%" "%SCRIPT_DIR%xlsx_to_markdown.py" %*
