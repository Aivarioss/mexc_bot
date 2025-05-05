@echo off
cd /d "%~dp0"

echo ✅ Startējam bota ciklu...
start cmd /k python main.py
start cmd /k python tracker_loop.py

pause
