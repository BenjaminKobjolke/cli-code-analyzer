import sys

from logger import Logger
from settings import Settings
from tool_descriptors import TOOLS_BY_NAME


class StdinStub:
    def __init__(self, terminal):
        self.terminal = terminal

    def isatty(self):
        return self.terminal


def test_watcher_prompt_accepts_answer_after_marker(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TICKETS_WATCHER_COMMAND_RUN", "1")
    monkeypatch.setattr(sys, "stdin", StdinStub(False))
    executable = tmp_path / "ruff.exe"
    executable.touch()

    def answer(*args):
        assert args == ()
        assert capsys.readouterr().out == (
            TOOLS_BY_NAME["ruff"].prompt_msg + "\n::tw-input-line::\n"
        )
        return str(executable)

    monkeypatch.setattr("builtins.input", answer)
    settings = Settings(str(tmp_path / "settings.ini"), Logger(quiet=True))

    assert settings.prompt_and_save("ruff") == str(executable)
    assert settings.get_path("ruff") == str(executable)
    assert "ruff_path" in (tmp_path / "settings.ini").read_text()


def test_non_terminal_prompt_fails_fast(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TICKETS_WATCHER_COMMAND_RUN", raising=False)
    monkeypatch.setattr(sys, "stdin", StdinStub(False))
    monkeypatch.setattr("builtins.input", lambda *_args: 1 / 0)
    settings_file = tmp_path / "settings.ini"
    settings = Settings(str(settings_file), Logger())

    assert settings.prompt_and_save("ruff") is None
    output = capsys.readouterr().out
    assert "[ruff] ruff_path" in output
    assert str(settings_file) in output


def test_missing_stdin_fails_fast(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TICKETS_WATCHER_COMMAND_RUN", raising=False)
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr("builtins.input", lambda *_args: 1 / 0)
    settings_file = tmp_path / "settings.ini"
    settings = Settings(str(settings_file), Logger())

    assert settings.prompt_and_save("ruff") is None
    output = capsys.readouterr().out
    assert "[ruff] ruff_path" in output
    assert str(settings_file) in output


def test_terminal_prompt_has_no_marker(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TICKETS_WATCHER_COMMAND_RUN", raising=False)
    monkeypatch.setattr(sys, "stdin", StdinStub(True))
    executable = tmp_path / "ruff.exe"
    executable.touch()

    def answer(prompt):
        assert prompt == TOOLS_BY_NAME["ruff"].prompt_msg
        return str(executable)

    monkeypatch.setattr("builtins.input", answer)
    settings = Settings(str(tmp_path / "settings.ini"), Logger(quiet=True))

    assert settings.prompt_and_save("ruff") == str(executable)
    assert "::tw-input-line::" not in capsys.readouterr().out


def test_watcher_eof_fails_fast(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TICKETS_WATCHER_COMMAND_RUN", "1")
    monkeypatch.setattr(sys, "stdin", StdinStub(False))

    def cancel(*_args):
        raise EOFError

    monkeypatch.setattr("builtins.input", cancel)
    settings = Settings(str(tmp_path / "settings.ini"), Logger())

    assert settings.prompt_and_save("ruff") is None
    assert "[ruff] ruff_path" in capsys.readouterr().out
