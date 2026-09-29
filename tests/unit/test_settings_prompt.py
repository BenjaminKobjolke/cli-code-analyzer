from logger import Logger
from settings import Settings


def test_watcher_prompt_emits_flushed_marker_even_when_quiet(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TICKETS_WATCHER_COMMAND_RUN", "1")

    def answer(_prompt):
        assert capsys.readouterr().out.splitlines() == ["::tw-input-line::"]
        return ""

    monkeypatch.setattr("builtins.input", answer)
    settings = Settings(str(tmp_path / "settings.ini"), Logger(quiet=True))

    assert settings.prompt_and_save("ruff") is None


def test_terminal_prompt_has_no_marker(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TICKETS_WATCHER_COMMAND_RUN", raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    settings = Settings(str(tmp_path / "settings.ini"), Logger(quiet=True))

    assert settings.prompt_and_save("ruff") is None
    assert "::tw-input-line::" not in capsys.readouterr().out
