"""Тесты эмулятора командной оболочки."""

import importlib
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
emulator = importlib.import_module("emulator")


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

    def setUp(self):
        """Создаёт новую оболочку для каждого теста."""
        self.shell = emulator.Shell()

    def test_title(self):
        """Заголовок окна строится из имени пользователя и компьютера."""
        shell = self.shell
        expected = f"Эмулятор - [{shell.username}@{shell.hostname}]"
        self.assertEqual(shell.title(), expected)

    def test_errors(self):
        """Неизвестная команда, кавычки и лишние аргументы exit."""
        cmd = self.shell.execute
        self.assertIn("неизвестная команда 'foo'", cmd("foo"))
        self.assertIn("незакрытые кавычки", cmd('ls "abc'))
        self.assertIn("не принимает аргументы", cmd("exit 1"))
        self.assertTrue(self.shell.running)

    def test_exit(self):
        """exit без аргументов останавливает оболочку."""
        self.assertEqual(self.shell.execute("exit"), "Выход из эмулятора.")
        self.assertFalse(self.shell.running)

    def test_stubs(self):
        """ls и cd печатают своё имя и аргументы."""
        cmd = self.shell.execute
        self.assertEqual(cmd("ls"), "ls")
        self.assertEqual(cmd('ls "my dir" b'), "ls: my dir b")
        self.assertEqual(cmd("cd /home"), "cd: /home")

    def test_window(self):
        """Окно открывается с заголовком ОС и списком команд."""
        gui = emulator.ShellGUI(self.shell)
        gui.print_banner()
        title = gui.root.title()
        text = gui.output.get("1.0", "end")
        gui.root.destroy()
        self.assertEqual(title, self.shell.title())
        self.assertIn("ls, cd", text)


if __name__ == "__main__":
    unittest.main()
