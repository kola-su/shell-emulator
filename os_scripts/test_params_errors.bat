@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo === скрипт с ошибками ===
python src\emulator.py --script scripts\startup_errors.txt
echo === скрипт не найден ===
python src\emulator.py --script scripts\missing.txt
echo === VFS и скрипт с ошибками ===
python src\emulator.py --vfs vfs\sample.json --script scripts\startup_errors.txt
