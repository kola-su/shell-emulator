"""Тесты эмулятора командной оболочки."""

import importlib
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VFS = ROOT / "vfs"
sys.path.insert(0, str(ROOT / "src"))
emulator = importlib.import_module("emulator")


def deep_shell():
    """Возвращает новую оболочку с deep.json, загруженным в память."""
    root, _note = emulator.load_vfs(str(VFS / "deep.json"))
    return emulator.Shell(root)


class ParserTest(unittest.TestCase):
    """Проверяет кавычки и переменные окружения."""

    def test_quotes(self):
        """Аргумент в кавычках остаётся одним словом."""
        args = emulator.parse_line('ls "my dir" b')
        self.assertEqual(args, ["ls", "my dir", "b"])

    def test_env(self):
        """$VAR и ${VAR} раскрываются, в одинарных кавычках — нет."""
        os.environ["EMUL_DEMO"] = "docs"
        parse = emulator.parse_line
        self.assertEqual(parse("cd $EMUL_DEMO"), ["cd", "docs"])
        self.assertEqual(parse("cd ${EMUL_DEMO}/a"), ["cd", "docs/a"])
        self.assertEqual(parse("cd '$EMUL_DEMO'"), ["cd", "$EMUL_DEMO"])

    def test_unclosed_quote(self):
        """Незакрытая кавычка — ошибка разбора."""
        with self.assertRaises(ValueError):
            emulator.parse_line('ls "abc')


class ShellTest(unittest.TestCase):
    """Проверяет заголовок, exit и сообщения об ошибках."""

    def test_title(self):
        """Заголовок окна строится из имени пользователя и компьютера."""
        shell = emulator.Shell()
        expected = f"Эмулятор - [{shell.username}@{shell.hostname}]"
        self.assertEqual(shell.title(), expected)

    def test_errors(self):
        """Неизвестная команда, кавычки и лишние аргументы exit."""
        shell = emulator.Shell()
        cmd = shell.execute
        self.assertIn("неизвестная команда 'foo'", cmd("foo"))
        self.assertIn("незакрытые кавычки", cmd('ls "abc'))
        self.assertIn("не принимает аргументы", cmd("exit 1"))
        self.assertTrue(shell.running)

    def test_exit(self):
        """exit без аргументов останавливает оболочку."""
        shell = emulator.Shell()
        self.assertEqual(shell.execute("exit"), "Выход из эмулятора.")
        self.assertFalse(shell.running)

    def test_window(self):
        """Окно открывается с заголовком ОС и списком команд."""
        shell = emulator.Shell()
        gui = emulator.ShellGUI(shell)
        gui.print_banner()
        title = gui.root.title()
        text = gui.output.get("1.0", "end")
        gui.root.destroy()
        self.assertEqual(title, shell.title())
        self.assertIn("ls, cd", text)


class ScriptTest(unittest.TestCase):
    """Проверяет параметры запуска и стартовый скрипт."""

    def test_comments_skipped(self):
        """Пустые строки и строки-комментарии не выполняются."""
        sign = emulator.COMMENT_SIGN
        lines = [sign + " comment", "", "  ls  ", "   " + sign + " still"]
        self.assertEqual(emulator.script_commands(lines), ["ls"])

    def test_parse_args(self):
        """--vfs и --script читаются, по умолчанию пустые."""
        args = emulator.parse_args(["--vfs", "a.json", "--script", "s.txt"])
        self.assertEqual((args.vfs, args.script), ("a.json", "s.txt"))
        empty = emulator.parse_args([])
        self.assertIsNone(empty.vfs)
        self.assertIsNone(empty.script)

    def test_script_dialog(self):
        """В окне видны команды скрипта и их ответы, но не комментарии."""
        gui = emulator.ShellGUI(emulator.Shell())
        gui.run_script(str(ROOT / "scripts" / "startup.txt"))
        text = gui.output.get("1.0", "end")
        gui.root.destroy()
        self.assertIn("неизвестная команда", text)
        self.assertNotIn("эта строка не выполняется", text)

    def test_missing_script(self):
        """Отсутствующий скрипт даёт сообщение, а не падение."""
        gui = emulator.ShellGUI(emulator.Shell())
        gui.run_script(str(ROOT / "scripts" / "missing.txt"))
        text = gui.output.get("1.0", "end")
        gui.root.destroy()
        self.assertIn("Ошибка скрипта", text)


class VfsTest(unittest.TestCase):
    """Проверяет загрузку JSON в память."""

    def test_minimal(self):
        """Минимальная VFS — пустой корневой каталог."""
        root, note = emulator.load_vfs(str(VFS / "minimal.json"))
        self.assertEqual(root.children, {})
        self.assertIn("узлов=1", note)

    def test_files(self):
        """Несколько файлов читаются вместе с содержимым."""
        root, _note = emulator.load_vfs(str(VFS / "files.json"))
        self.assertIn("readme.txt", root.children)
        docs = root.children["docs"]
        self.assertEqual(docs.children["a.txt"].content, b"A")

    def test_deep_and_base64(self):
        """Три и более уровня вложенности, файл в base64."""
        root, _note = emulator.load_vfs(str(VFS / "deep.json"))
        self.assertGreaterEqual(emulator.tree_depth(root), 4)
        user = root.children["home"].children["user"]
        self.assertEqual(user.children["photo.bin"].content, b"hello")

    def test_bad_files(self):
        """Битый и отсутствующий JSON дают ошибку и пустой корень."""
        for name in ("broken.json", "missing.json"):
            root, note = emulator.load_vfs(str(VFS / name))
            self.assertIn("Ошибка загрузки VFS", note)
            self.assertEqual(root.children, {})

    def test_prompt_shows_path(self):
        """Приглашение содержит текущий каталог VFS."""
        root, _note = emulator.load_vfs(str(VFS / "deep.json"))
        shell = emulator.Shell(root)
        self.assertTrue(shell.prompt().endswith(":/$ "))


class CommandTest(unittest.TestCase):
    """Проверяет ls, cd, tree и date на глубокой VFS."""

    def test_ls(self):
        """ls скрывает имена на точку, -a их показывает, -l подробно."""
        cmd = deep_shell().execute
        self.assertEqual(cmd("ls"), "home  tmp")
        self.assertIn(".hidden", cmd("ls -a").split())
        self.assertIn("-       11 readme.txt", cmd("ls -l /home"))
        self.assertIn("неверный флаг", cmd("ls -x"))
        self.assertIn("нет такого файла", cmd("ls /missing"))

    def test_cd(self):
        """cd меняет каталог, cd - возвращает назад."""
        shell = deep_shell()
        cmd = shell.execute
        self.assertEqual(cmd("cd /home/user"), "")
        self.assertTrue(shell.prompt().endswith(":/home/user$ "))
        self.assertEqual(cmd("cd .."), "")
        self.assertEqual(cmd("cd -"), "/home/user")
        self.assertIn("не каталог", cmd("cd /home/readme.txt"))
        self.assertIn("нет такого файла", cmd("cd /no"))
        self.assertIn("слишком много", cmd("cd a b"))

    def test_tree(self):
        """tree ограничивает глубину и по -a показывает скрытое."""
        cmd = deep_shell().execute
        shallow = cmd("tree -L 1")
        self.assertIn("home", shallow)
        self.assertNotIn("user", shallow)
        self.assertNotIn(".hidden", shallow)
        self.assertIn(".hidden", cmd("tree -a -L1"))
        self.assertIn("projects", cmd("tree /home"))
        self.assertIn("нужно число", cmd("tree -L x"))
        self.assertIn("неверный флаг", cmd("tree -Z"))

    def test_date(self):
        """date печатает время ОС, UTC и свой формат."""
        cmd = deep_shell().execute
        full = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
        self.assertTrue(re.match(full, cmd("date")))
        self.assertTrue(re.match(full, cmd("date -u")))
        self.assertTrue(re.match(r"^\d{4}$", cmd("date +%Y")))
        self.assertIn("неверный аргумент", cmd("date --bad"))


class ChangeTest(unittest.TestCase):
    """Проверяет touch и cp: изменения только в памяти."""

    def test_touch(self):
        """touch создаёт пустой файл; -c и ошибки не создают."""
        cmd = deep_shell().execute
        self.assertEqual(cmd("touch /tmp/a.txt"), "")
        self.assertEqual(cmd("touch /tmp/a.txt"), "")
        self.assertEqual(cmd("touch -c /tmp/nope.txt"), "")
        self.assertEqual(cmd("ls /tmp"), "a.txt")
        self.assertIn("нельзя создать", cmd("touch /no/x.txt"))
        self.assertIn("не указан файл", cmd("touch"))
        self.assertIn("неверный флаг", cmd("touch -z a"))

    def test_cp(self):
        """cp копирует файл, каталог только с -r."""
        cmd = deep_shell().execute
        self.assertEqual(cmd("cp /home/readme.txt /tmp/c.txt"), "")
        self.assertIn("c.txt", cmd("ls /tmp"))
        self.assertIn("укажите -r", cmd("cp /home /tmp/h"))
        self.assertEqual(cmd("cp -r /home /tmp/h"), "")
        self.assertIn("photo.bin", cmd("ls /tmp/h/user"))

    def test_cp_errors(self):
        """Ошибки cp: мало аргументов, нет файла, копия в себя."""
        cmd = deep_shell().execute
        self.assertIn("недостаточно", cmd("cp /tmp"))
        self.assertIn("нет такого файла", cmd("cp /missing /tmp"))
        self.assertIn("самого себя", cmd("cp -r /home /home/user"))

    def test_memory_only(self):
        """Копия независима, а JSON на диске не меняется."""
        path = VFS / "deep.json"
        before = path.read_bytes()
        shell = deep_shell()
        cmd = shell.execute
        cmd("cp /home/readme.txt /tmp/c.txt")
        cmd("touch /tmp/new.txt")
        tmp = shell.root.children["tmp"]
        tmp.children["c.txt"].content = b"changed"
        home = shell.root.children["home"]
        self.assertEqual(home.children["readme.txt"].content, b"home readme")
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
