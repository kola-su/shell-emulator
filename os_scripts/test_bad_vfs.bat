@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo === повреждённый JSON ===
python src\emulator.py --vfs vfs\broken.json
echo === файл не найден ===
python src\emulator.py --vfs vfs\missing.json
echo === повреждённый JSON и скрипт ===
python src\emulator.py --vfs vfs\broken.json --script scripts\startup.txt
echo === файл не найден и скрипт с ошибками ===
python src\emulator.py --vfs vfs\missing.json --script scripts\startup_errors.txt
