"""Эмулятор UNIX-подобной командной оболочки. Вариант 9."""

import argparse
import base64
import json
import os
import shlex
import socket
import tkinter as tk
from datetime import datetime, timezone
from tkinter import scrolledtext

DIR = "directory"
FILE = "file"
MIN_CP_ARGS = 2


def get_username():
    """Возвращает имя пользователя из переменных окружения ОС."""
    return os.environ.get("USERNAME") or os.environ.get("USER") or "user"


def env_value(name):
    """Возвращает значение переменной окружения или пустую строку.

    Если HOME не задана (так бывает в Windows), берётся USERPROFILE.
    """
    value = os.environ.get(name, "")
    if name == "HOME" and not value:
        value = os.environ.get("USERPROFILE", "")
    return value


def read_var(line, start):
    """Читает имя после знака $ и возвращает (позиция, значение)."""
    if line.startswith("{", start):
        end = line.find("}", start)
        if end == -1:
            return len(line), ""
        return end + 1, env_value(line[start + 1:end])
    end = start
    while end < len(line) and (line[end].isalnum() or line[end] == "_"):
        end += 1
    if end == start:
        return start, "$"
    return end, env_value(line[start:end])


def next_quote(char, quote):
    """Возвращает открытую кавычку после символа char."""
    if quote is None and char in "'\"":
        return char
    if char == quote:
        return None
    return quote


def expand_vars(line):
    """Подставляет $ИМЯ и ${ИМЯ} везде, кроме одинарных кавычек."""
    result = []
    quote = None
    i = 0
    while i < len(line):
        char = line[i]
        if char == "$" and quote != "'":
            i, value = read_var(line, i + 1)
            result.append(value.replace("\\", "\\\\").replace('"', '\\"'))
            continue
        quote = next_quote(char, quote)
        result.append(char)
        i += 1
    return "".join(result)


def parse_line(line):
    """Разбивает строку на аргументы с учётом кавычек и переменных."""
    return shlex.split(expand_vars(line))


COMMENT_SIGN = chr(35)


def script_commands(lines):
    """Отбрасывает пустые строки и строки-комментарии стартового скрипта.

    Комментарий начинается со знака COMMENT_SIGN, как в Python.
    """
    commands = []
    for raw in lines:
        line = raw.strip()
        if line and not line.startswith(COMMENT_SIGN):
            commands.append(line)
    return commands


class Node:
    """Файл или каталог виртуальной файловой системы в памяти."""

    def __init__(self, name, kind):
        """Создаёт узел без содержимого и без родителя."""
        self.name = name
        self.kind = kind
        self.content = b""
        self.children = {}
        self.parent = None

    def is_dir(self):
        """Возвращает True, если узел является каталогом."""
        return self.kind == DIR


def path_of(node):
    """Возвращает абсолютный путь узла, например /home/user."""
    names = []
    while node.parent is not None:
        names.append(node.name)
        node = node.parent
    return "/" + "/".join(reversed(names))


def read_content(data):
    """Возвращает байты файла: текст UTF-8 или данные base64."""
    raw = data.get("content", "")
    if data.get("encoding") == "base64":
        return base64.b64decode(raw)
    return raw.encode("utf-8")


def build_node(name, data):
    """Строит узел и всех его потомков из словаря JSON."""
    node = Node(name, data.get("type", DIR))
    if node.kind == FILE:
        node.content = read_content(data)
        return node
    for item in data.get("children", []):
        child = build_node(item["name"], item)
        child.parent = node
        node.children[child.name] = child
    return node


def count_nodes(node):
    """Считает узлы дерева вместе с корнем."""
    return 1 + sum(count_nodes(child) for child in node.children.values())


def tree_depth(node):
    """Возвращает глубину дерева; у одного корня она равна 1."""
    if not node.children:
        return 1
    return 1 + max(tree_depth(child) for child in node.children.values())


def load_vfs(path):
    """Читает JSON в память и возвращает (корень, отладочная строка).

    Файл на диске только читается и никогда не изменяется.
    """
    if not path:
        return Node("", DIR), "VFS в памяти: пустой корень"
    try:
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
        root = build_node("", data["root"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        return Node("", DIR), f"Ошибка загрузки VFS: {error}"
    count, depth = count_nodes(root), tree_depth(root)
    return root, f"VFS в памяти: узлов={count}, глубина={depth}"


def split_flags(args):
    """Отделяет короткие флаги вида -al от остальных аргументов."""
    flags = ""
    rest = []
    for arg in args:
        if arg.startswith("-") and len(arg) > 1:
            flags += arg[1:]
        else:
            rest.append(arg)
    return flags, rest


def entries(node, show_all):
    """Возвращает пары (имя, узел) каталога; при -a добавляет . и .."""
    rows = []
    if show_all:
        rows = [(".", node), ("..", node.parent or node)]
    for name in sorted(node.children):
        if show_all or not name.startswith("."):
            rows.append((name, node.children[name]))
    return rows


def long_row(name, node):
    """Строка подробного формата ls -l: тип, размер и имя."""
    if node.is_dir():
        return f"d {len(node.children):8d} {name}"
    return f"- {len(node.content):8d} {name}"


def to_depth(text):
    """Переводит значение флага -L в число."""
    if not text.isdigit():
        raise ValueError("после -L нужно число")
    return int(text)


def parse_tree_args(args):
    """Разбирает флаги tree: -a, -L N, -LN и путь."""
    show_all = False
    limit = 32
    paths = []
    items = iter(args)
    for arg in items:
        if arg == "-a":
            show_all = True
        elif arg == "-L":
            limit = to_depth(next(items, ""))
        elif arg.startswith("-L"):
            limit = to_depth(arg[2:])
        elif arg.startswith("-"):
            raise ValueError(f"неверный флаг: {arg}")
        else:
            paths.append(arg)
    return show_all, limit, paths


def add_tree(lines, node, prefix, limit, show_all):
    """Добавляет в lines ветви дерева не глубже limit уровней."""
    if not node.is_dir() or limit < 1:
        return
    names = [n for n in sorted(node.children) if show_all or n[0] != "."]
    for index, name in enumerate(names):
        last = index == len(names) - 1
        lines.append(prefix + ("└── " if last else "├── ") + name)
        child = node.children[name]
        child_prefix = prefix + ("    " if last else "│   ")
        add_tree(lines, child, child_prefix, limit - 1, show_all)


def place(parent, node):
    """Кладёт узел в каталог, заменяя одноимённый."""
    node.parent = parent
    parent.children[node.name] = node


def clone(node, name):
    """Возвращает независимую копию узла и всех его потомков."""
    copy = Node(name, node.kind)
    copy.content = node.content
    for child in node.children.values():
        place(copy, clone(child, child.name))
    return copy


def is_inside(node, ancestor):
    """Возвращает True, если node совпадает с ancestor или лежит в нём."""
    while node is not None:
        if node is ancestor:
            return True
        node = node.parent
    return False


class Shell:
    """Состояние оболочки и выполнение команд."""

    def __init__(self, root=None):
        """Запоминает пользователя, компьютер, корень VFS и команды."""
        self.username = get_username()
        self.hostname = socket.gethostname()
        self.running = True
        self.root = root if root is not None else Node("", DIR)
        self.cwd = self.root
        self.previous = None
        self.commands = {
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "tree": self.cmd_tree,
            "date": self.cmd_date,
            "touch": self.cmd_touch,
            "cp": self.cmd_cp,
            "exit": self.cmd_exit,
        }

    def title(self):
        """Возвращает заголовок окна по данным текущей ОС."""
        return f"Эмулятор - [{self.username}@{self.hostname}]"

    def prompt(self):
        """Возвращает приглашение командной строки."""
        path = path_of(self.cwd)
        return f"{self.username}@{self.hostname}:{path}$ "

    def execute(self, line):
        """Выполняет одну строку и возвращает текст ответа."""
        try:
            args = parse_line(line)
        except ValueError:
            return "Ошибка разбора команды: незакрытые кавычки"
        if not args:
            return ""
        handler = self.commands.get(args[0])
        if handler is None:
            return f"Ошибка: неизвестная команда '{args[0]}'"
        return handler(args[1:])

    def cmd_exit(self, args):
        """Завершает работу оболочки, если аргументов нет."""
        if args:
            return "Ошибка: exit не принимает аргументы"
        self.running = False
        return "Выход из эмулятора."

    def resolve(self, path):
        """Находит узел по абсолютному или относительному пути."""
        node = self.root if path.startswith("/") else self.cwd
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                node = node.parent or node
            elif node.is_dir() and part in node.children:
                node = node.children[part]
            else:
                return None
        return node

    def cmd_ls(self, args):
        """Печатает содержимое каталогов; -a скрытые, -l подробно."""
        flags, paths = split_flags(args)
        bad = [flag for flag in flags if flag not in "al"]
        if bad:
            return f"ls: неверный флаг: -{bad[0]}"
        blocks = []
        for path in paths or [path_of(self.cwd)]:
            if len(paths) > 1:
                blocks.append(path + ":")
            blocks.append(self.list_one(path, flags))
        return "\n".join(block for block in blocks if block)

    def list_one(self, path, flags):
        """Возвращает содержимое одного каталога или имя файла."""
        node = self.resolve(path)
        if node is None:
            return f"ls: нет такого файла или каталога: {path}"
        if node.is_dir():
            rows = entries(node, "a" in flags)
        else:
            rows = [(node.name, node)]
        if "l" in flags:
            return "\n".join(long_row(name, item) for name, item in rows)
        return "  ".join(name for name, _item in rows)

    def cmd_cd(self, args):
        """Меняет текущий каталог; cd - возвращает предыдущий."""
        if len(args) > 1:
            return "cd: слишком много аргументов"
        if args and args[0] == "-":
            if self.previous is None:
                return "cd: нет предыдущего каталога"
            self.cwd, self.previous = self.previous, self.cwd
            return path_of(self.cwd)
        target = args[0] if args else "/"
        node = self.resolve(target)
        if node is None:
            return f"cd: нет такого файла или каталога: {target}"
        if not node.is_dir():
            return f"cd: не каталог: {target}"
        self.previous, self.cwd = self.cwd, node
        return ""

    def cmd_tree(self, args):
        """Печатает дерево каталогов; -a скрытые, -L глубина."""
        try:
            show_all, limit, paths = parse_tree_args(args)
        except ValueError as error:
            return f"tree: {error}"
        if len(paths) > 1:
            return "tree: слишком много аргументов"
        target = paths[0] if paths else path_of(self.cwd)
        node = self.resolve(target)
        if node is None:
            return f"tree: нет такого файла или каталога: {target}"
        lines = [path_of(node)]
        add_tree(lines, node, "", limit, show_all)
        return "\n".join(lines)

    def cmd_date(self, args):
        """Печатает дату и время ОС; -u в UTC, +ФОРМАТ как strftime."""
        utc = False
        fmt = "%Y-%m-%d %H:%M:%S"
        for arg in args:
            if arg == "-u":
                utc = True
            elif arg.startswith("+"):
                fmt = arg[1:]
            else:
                return f"date: неверный аргумент: {arg}"
        now = datetime.now(timezone.utc) if utc else datetime.now()
        try:
            return now.strftime(fmt)
        except ValueError as error:
            return f"date: {error}"

    def parent_and_name(self, path):
        """Возвращает каталог-родитель и последнее имя пути."""
        head, sep, name = path.rstrip("/").rpartition("/")
        if name in ("", ".", ".."):
            return None, name
        if not sep:
            return self.cwd, name
        parent = self.resolve(head or "/")
        if parent is None or not parent.is_dir():
            return None, name
        return parent, name

    def cmd_touch(self, args):
        """Создаёт пустые файлы в памяти; -c не создаёт новые."""
        flags, paths = split_flags(args)
        if flags.strip("c"):
            return f"touch: неверный флаг: -{flags}"
        if not paths:
            return "touch: не указан файл"
        errors = [self.touch_one(path, "c" in flags) for path in paths]
        return "\n".join(error for error in errors if error)

    def touch_one(self, path, no_create):
        """Создаёт один пустой файл, если такого имени ещё нет."""
        parent, name = self.parent_and_name(path)
        if parent is None:
            return f"touch: нельзя создать файл: {path}"
        if name not in parent.children and not no_create:
            place(parent, Node(name, FILE))
        return ""

    def find_source(self, path, recursive):
        """Возвращает (узел, "") или (None, текст ошибки) для cp."""
        source = self.resolve(path)
        if source is None:
            return None, f"cp: нет такого файла или каталога: {path}"
        if source.is_dir() and not recursive:
            return None, f"cp: {path}: каталог, укажите -r"
        return source, ""

    def cmd_cp(self, args):
        """Копирует файлы, а с флагом -r и каталоги, внутри VFS."""
        flags, paths = split_flags(args)
        if flags.strip("r"):
            return f"cp: неверный флаг: -{flags}"
        if len(paths) < MIN_CP_ARGS:
            return "cp: недостаточно аргументов"
        *sources, target = paths
        recursive = "r" in flags
        dest = self.resolve(target)
        if dest is not None and dest.is_dir():
            errors = [self.copy_into(s, dest, recursive) for s in sources]
            return "\n".join(error for error in errors if error)
        if len(sources) > 1:
            return "cp: цель не является каталогом"
        return self.copy_to(sources[0], target, recursive)

    def copy_into(self, path, folder, recursive):
        """Копирует источник внутрь существующего каталога."""
        source, error = self.find_source(path, recursive)
        if error:
            return error
        if is_inside(folder, source):
            return "cp: нельзя копировать каталог в самого себя"
        if folder.children.get(source.name) is source:
            return "cp: нельзя копировать файл сам в себя"
        place(folder, clone(source, source.name))
        return ""

    def copy_to(self, path, target, recursive):
        """Копирует источник под новым именем target."""
        source, error = self.find_source(path, recursive)
        if error:
            return error
        parent, name = self.parent_and_name(target)
        if parent is None:
            return f"cp: нельзя создать: {target}"
        if parent.children.get(name) is source:
            return "cp: нельзя копировать файл сам в себя"
        if is_inside(parent, source):
            return "cp: нельзя копировать каталог в самого себя"
        place(parent, clone(source, name))
        return ""


class ShellGUI:
    """Окно эмулятора: журнал сверху и поле ввода снизу."""

    def __init__(self, shell):
        """Создаёт окно с заголовком по данным ОС."""
        self.shell = shell
        self.root = tk.Tk()
        self.root.title(shell.title())
        self.root.geometry("800x500")
        self.output = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, font=("Consolas", 12)
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.entry = tk.Entry(self.root, font=("Consolas", 12))
        self.entry.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus()

    def print_text(self, text):
        """Добавляет текст в журнал и прокручивает его вниз."""
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def print_banner(self):
        """Печатает приветствие и список доступных команд."""
        names = ", ".join(self.shell.commands)
        self.print_text("Эмулятор UNIX-подобной командной оболочки\n")
        self.print_text(f"Доступные команды: {names}\n")

    def show_prompt(self):
        """Печатает приглашение командной строки."""
        self.print_text(self.shell.prompt())

    def run_line(self, line):
        """Печатает команду, выполняет её и печатает ответ."""
        self.print_text(line + "\n")
        result = self.shell.execute(line)
        if result:
            self.print_text(result + "\n")
        if not self.shell.running:
            self.entry.config(state=tk.DISABLED)

    def on_enter(self, _event=None):
        """Выполняет строку из поля ввода по нажатию Enter."""
        line = self.entry.get()
        self.entry.delete(0, tk.END)
        self.run_line(line)
        if self.shell.running:
            self.show_prompt()

    def run_script(self, path):
        """Выполняет стартовый скрипт, показывая ввод и вывод."""
        try:
            with open(path, encoding="utf-8-sig") as handle:
                lines = handle.read().splitlines()
        except OSError as error:
            self.print_text(f"Ошибка скрипта: {error}\n")
            return
        for line in script_commands(lines):
            if not self.shell.running:
                break
            self.show_prompt()
            self.run_line(line)


def parse_args(argv=None):
    """Читает параметры командной строки --vfs и --script."""
    parser = argparse.ArgumentParser(description="Эмулятор оболочки")
    parser.add_argument("--vfs", help="путь к физическому расположению VFS")
    parser.add_argument("--script", help="путь к стартовому скрипту")
    return parser.parse_args(argv)


def main(argv=None):
    """Читает параметры, печатает отладку и открывает окно."""
    args = parse_args(argv)
    root, note = load_vfs(args.vfs)
    shell = Shell(root)
    gui = ShellGUI(shell)
    gui.print_banner()
    gui.print_text(f"[debug] Путь к VFS: {args.vfs or 'не задан'}\n")
    gui.print_text(f"[debug] Стартовый скрипт: {args.script or 'не задан'}\n")
    gui.print_text(f"[debug] {note}\n")
    gui.print_text("\n")
    if args.script:
        gui.run_script(args.script)
    if shell.running:
        gui.show_prompt()
    gui.root.mainloop()


if __name__ == "__main__":
    main()
