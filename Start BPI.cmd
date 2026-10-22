@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" src\start_frontend_pilot.py
if errorlevel 1 pause
