@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto launcher
python tools\verify_package.py
exit /b %ERRORLEVEL%
:launcher
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto missing
py -3 tools\verify_package.py
exit /b %ERRORLEVEL%
:missing
echo An approved Python 3.10 or later is required on PATH or via the py launcher.
echo No installation, execution-policy change, source repair, or retry was attempted.
exit /b 2
