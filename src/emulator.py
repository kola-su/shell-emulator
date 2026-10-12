"""Эмулятор UNIX-подобной командной оболочки. Вариант 9."""

import argparse
import base64
import json
import os
import shlex
import socket
import tkinter as tk
from tkinter import scrolledtext

DIR = "directory"
FILE = "file"


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


def stub(name, args):
    """Ответ команды-заглушки: её имя и переданные аргументы."""
    if args:
        return f"{name}: {' '.join(args)}"
    return name


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


class Shell:
    """Состояние оболочки и выполнение команд."""

    def __init__(self, root=None):
        """Запоминает пользователя, компьютер, корень VFS и команды."""
        self.username = get_username()
        self.hostname = socket.gethostname()
        self.running = True
        self.root = root if root is not None else Node("", DIR)
        self.cwd = self.root
        self.commands = {
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
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

    def cmd_ls(self, args):
        """Заглушка ls: печатает имя команды и аргументы."""
        return stub("ls", args)

    def cmd_cd(self, args):
        """Заглушка cd: печатает имя команды и аргументы."""
        return stub("cd", args)


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
