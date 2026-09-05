@echo off
cd /d "%~dp0"
if not exist build mkdir build
javac --release 17 -d build *.java jobs\*.java
exit /b %ERRORLEVEL%
