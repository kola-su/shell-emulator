# Эмулятор UNIX-подобной командной оболочки

Практическая работа, вариант 9. Этап 4 — основные команды.

## 1. Общее описание

Команды `ls` и `cd` теперь работают с VFS в памяти, добавлены `tree`
и `date`. Смена каталога меняет только состояние эмулятора и ничего
не записывает на диск. Окно, заголовок `Эмулятор - [username@hostname]`,
парсер с `$ИМЯ`, параметры `--vfs` и `--script` сохранены.

Код находится в `src/emulator.py`, тесты — в `tests/test_emulator.py`.

## 2. Функции и настройки

Параметры командной строки:

- `--vfs ПУТЬ` — JSON-файл VFS (формат описан на этапе 3);
- `--script ПУТЬ` — стартовый скрипт, комментарии начинаются с `#`.

Команды:

- `ls [-a] [-l] [ПУТЬ...]` — содержимое каталога. `-a` показывает имена
  на точку и записи `.` и `..`. `-l` выводит тип (`d` или `-`), размер
  и имя; размер каталога — число элементов, файла — число байт.
  Флаги можно объединять: `-la`.
- `cd [ПУТЬ]` — смена каталога. Без пути — переход в `/`, `..` — на
  уровень выше, `cd -` — в предыдущий каталог с выводом пути.
- `tree [-a] [-L N] [ПУТЬ]` — дерево каталогов. `-L` ограничивает
  глубину, допускается запись `-L 2` и `-L2`.
- `date [-u] [+ФОРМАТ]` — дата и время ОС. `-u` — в UTC, формат как
  у `strftime`, например `+%Y-%m-%d`.
- `exit` — выход.

Пути бывают абсолютными (`/home/user`) и относительными (`user`, `..`).

Ошибки: неизвестная команда, неверный флаг, нет такого файла или
каталога, путь не является каталогом, лишние аргументы `cd` и `exit`,
незакрытые кавычки.

## 3. Сборка и тесты

Сборка не нужна, требуется Python 3 со стандартной библиотекой.

Запуск:

```bat
run.bat --vfs vfs\deep.json --script scripts\startup.txt
```

```sh
sh run.sh --vfs vfs/deep.json --script scripts/startup.txt
```

Тесты:

```bat
python -m unittest discover -s tests -v
```

`scripts/startup.txt` содержит все режимы `ls`, `cd`, `tree`, `date`
и ошибочные вызовы. Скрипты Windows с разными VFS:

```bat
os_scripts\test_minimal.bat
os_scripts\test_files.bat
os_scripts\test_deep.bat
os_scripts\test_bad_vfs.bat
```

## 4. Примеры использования

```text
korsh@COMP:/$ ls
home  tmp
korsh@COMP:/$ ls -la /home
d        2 .
d        3 ..
-       11 readme.txt
d        2 user
korsh@COMP:/$ cd /home/user
korsh@COMP:/home/user$ tree
/home/user
├── photo.bin
└── projects
    └── lab.txt
korsh@COMP:/home/user$ cd -
/
korsh@COMP:/$ date +%Y
2026
korsh@COMP:/$ cd /home/readme.txt
cd: не каталог: /home/readme.txt
```
