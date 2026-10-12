@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo === без параметров ===
python src\emulator.py
echo === только VFS ===
python src\emulator.py --vfs vfs\files.json
echo === только скрипт ===
python src\emulator.py --script scripts\startup.txt
echo === VFS и скрипт ===
python src\emulator.py --vfs vfs\files.json --script scripts\startup.txt
