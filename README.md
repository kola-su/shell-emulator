# Эмулятор UNIX-подобной командной оболочки

Практическая работа, вариант 9. Этап 3 — VFS.

## 1. Общее описание

К эмулятору подключена виртуальная файловая система (VFS). Её источник —
JSON-файл из параметра `--vfs`. Файл один раз читается в память, дальше
все операции идут только с памятью: файл не распаковывается и не
изменяется. Приглашение показывает текущий каталог VFS:

```text
korsh@COMP:/$
```

При запуске отладка дополнительно показывает число узлов и глубину
загруженного дерева. Если файл не найден или JSON повреждён, текст
ошибки выводится в окно, а эмулятор работает с пустым корнем.

Команды `ls` и `cd` на этом этапе ещё заглушки, их логика появится
на этапе 4. Окно, парсер, `--script` и `exit` сохранены.

Код находится в `src/emulator.py`, тесты — в `tests/test_emulator.py`.

## 2. Функции и настройки

Параметры командной строки:

- `--vfs ПУТЬ` — JSON-файл VFS; без него используется пустой корень;
- `--script ПУТЬ` — стартовый скрипт, комментарии начинаются с `#`.

Формат JSON:

```json
{
  "root": {
    "type": "directory",
    "children": [
      {"name": "a.txt", "type": "file", "content": "текст"},
      {"name": "b.bin", "type": "file", "encoding": "base64",
       "content": "aGVsbG8="}
    ]
  }
}
```

- `root` — корневой каталог;
- каталог: `"type": "directory"` и список `children`;
- файл: `"type": "file"` и текст в `content`;
- двоичные данные: `"encoding": "base64"`.

Варианты VFS в каталоге `vfs`:

- `minimal.json` — минимальный: пустой корень;
- `files.json` — несколько файлов;
- `deep.json` — не менее 3 уровней файлов и папок, файл в base64;
- `broken.json` — повреждённый JSON для проверки ошибки.

Основные функции: `load_vfs` читает JSON, `build_node` строит дерево
из узлов `Node`, `path_of` возвращает путь узла.

## 3. Сборка и тесты

Сборка не нужна, требуется Python 3 со стандартной библиотекой.

Запуск:

```bat
run.bat --vfs vfs\deep.json --script scripts\startup.txt
```

Тесты:

```bat
python -m unittest discover -s tests -v
```

Скрипты Windows для каждого варианта VFS. Каждый вызывает эмулятор
со всеми сочетаниями параметров; после закрытия окна идёт следующий:

```bat
os_scripts\test_minimal.bat
os_scripts\test_files.bat
os_scripts\test_deep.bat
os_scripts\test_bad_vfs.bat
```

`scripts/startup.txt` проверяет все команды этапов 1–3 и ошибки,
`scripts/startup_errors.txt` — только ошибочные строки.

## 4. Примеры использования

```bat
run.bat --vfs vfs\deep.json --script scripts\startup.txt
```

```text
[debug] Путь к VFS: vfs\deep.json
[debug] Стартовый скрипт: scripts\startup.txt
[debug] VFS в памяти: узлов=9, глубина=5

korsh@COMP:/$ ls /home/user
ls: /home/user
korsh@COMP:/$ foo
Ошибка: неизвестная команда 'foo'
```

С повреждённым файлом:

```text
[debug] Ошибка загрузки VFS: Expecting property name enclosed in ...
```
