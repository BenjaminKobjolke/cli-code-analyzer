import re
from pathlib import Path

import pytest

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.dart_unused_code import DartUnusedCodeRule


def _project(tmp_path: Path, files: dict[str, str]) -> Path:
    (tmp_path / 'pubspec.yaml').write_text('name: example\n', encoding='utf-8')
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return tmp_path


def _check(tmp_path: Path, monkeypatch, name: str, refs, *, source: str | None = None):
    declaration = tmp_path / (source or 'lib/keys.dart')
    monkeypatch.setattr('rules.dart_unused_code.HAS_DART_LSP', True)
    def symbols(path):
        if path != str(declaration):
            return []
        content = declaration.read_text(encoding='utf-8')
        return [{'name': match.group(1), 'kind': 'class',
                 'line': content[:match.start()].count('\n') + 1, 'col': 1}
                for match in re.finditer(r'^class (\w+)', content, re.MULTILINE)]

    monkeypatch.setattr('rules.dart_unused_code.get_document_symbols', symbols, raising=False)

    def find(_path, _line, _col):
        if isinstance(refs, Exception):
            raise refs
        return refs

    monkeypatch.setattr('rules.dart_unused_code.find_references', find, raising=False)
    rule = DartUnusedCodeRule(RuleContext(config={}, base_path=tmp_path, logger=Logger()))
    return rule._run(declaration)


def _declaration(tmp_path: Path, line: int = 1) -> dict:
    return {'file': str(tmp_path / 'lib/keys.dart'), 'line': line}


def test_lsp_usage_is_not_reported(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Keys {}\n', 'lib/app.dart': 'void app() {}\n'})
    result = _check(tmp_path, monkeypatch, 'Keys', [_declaration(tmp_path), {'file': 'lib/app.dart', 'line': 1}])
    assert result.status == RuleStatus.OK
    assert result.violations == []


def test_unique_unused_class_is_reported(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Keys {}\n'})
    result = _check(tmp_path, monkeypatch, 'Keys', [_declaration(tmp_path)])
    assert result.status == RuleStatus.OK
    assert [v.message for v in result.violations] == [
        "Unused class 'Keys' declared at line 1 - no references found in project"]


@pytest.mark.parametrize('refs', [[], 'declaration', RuntimeError('lookup failed')])
def test_used_constants_class_survives_bad_lookup(tmp_path, monkeypatch, capsys, refs):
    _project(tmp_path, {'lib/keys.dart': 'class Keys {\n  Keys._();\n  static const a = 1;\n}\n',
                        'lib/app.dart': 'final value = Keys.a;\n'})
    result = _check(tmp_path, monkeypatch, 'Keys',
                    [_declaration(tmp_path)] if refs == 'declaration' else refs)
    assert result.status == RuleStatus.OK
    assert result.violations == []
    assert 'not reported, name is used in project source: Keys' in capsys.readouterr().out


def test_reference_only_in_tests_survives_empty_lookup(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Keys { static const a = 1; }\n',
                        'test/keys_test.dart': 'final value = Keys.a;\n'})
    assert _check(tmp_path, monkeypatch, 'Keys', []).violations == []


def test_sibling_declaration_reference_survives_empty_lookup(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Foo { FooState createState() => FooState(); }\n'
                                     'class FooState {}\n'})
    result = _check(tmp_path, monkeypatch, 'FooState', [], source='lib/keys.dart')
    assert all('FooState' not in v.message for v in result.violations)


@pytest.mark.parametrize('refs', [[], 'declaration', RuntimeError('lookup failed')])
def test_unused_class_with_constructor_and_doc_is_reported(tmp_path, monkeypatch, refs):
    _project(tmp_path, {'lib/keys.dart': '/// Keys is unused.\nclass Keys {\n  Keys();\n}\n'})
    result = _check(tmp_path, monkeypatch, 'Keys',
                    [_declaration(tmp_path, 2)] if refs == 'declaration' else refs)
    assert [v.message for v in result.violations] == [
        "Unused class 'Keys' declared at line 2 - no references found in project"]


def test_other_identifier_does_not_keep_unused_class_alive(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Keys {}\n',
                        'lib/app.dart': 'final KeysOther = 1;\n'})
    result = _check(tmp_path, monkeypatch, 'Keys', [])
    assert len(result.violations) == 1


def test_bad_lookups_have_stable_violations(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Keys {}\n'})
    results = [_check(tmp_path, monkeypatch, 'Keys', refs).violations
               for refs in ([], [_declaration(tmp_path)], RuntimeError('lookup failed'))]
    assert results[0] == results[1] == results[2]


def test_collect_project_dart_files_skips_generated_directories(tmp_path):
    from rules.dart_utils import collect_project_dart_files

    _project(tmp_path, {'lib/a.dart': '', 'test/a.dart': '', '.dart_tool/a.dart': '',
                        'build/a.dart': '', 'windows/flutter/ephemeral/a.dart': ''})
    assert [p.relative_to(tmp_path).as_posix() for p in collect_project_dart_files(tmp_path)] == [
        'lib/a.dart', 'test/a.dart']


def test_unreadable_source_fails_rule(tmp_path, monkeypatch):
    _project(tmp_path, {'lib/keys.dart': 'class Keys {}\n', 'lib/broken.dart': 'final x = 1;\n'})
    original = Path.read_text

    def read_text(path, *args, **kwargs):
        if path.name == 'broken.dart':
            raise OSError('access denied')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read_text)
    result = _check(tmp_path, monkeypatch, 'Keys', [])
    assert result.status == RuleStatus.FAILED
    assert 'broken.dart' in result.message
    assert result.violations == []
