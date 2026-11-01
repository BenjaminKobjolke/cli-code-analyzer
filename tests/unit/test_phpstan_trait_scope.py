import json
from pathlib import Path
from types import SimpleNamespace

from logger import Logger
from models import RuleStatus
from rules.context import RuleContext
from rules.phpstan_analyze import PHPStanAnalyzeRule


def _rule(tmp_path: Path, config: dict, filter_files=None) -> PHPStanAnalyzeRule:
    return PHPStanAnalyzeRule(RuleContext(
        config=config,
        base_path=tmp_path,
        filter_files=filter_files,
        logger=Logger(quiet=True),
    ))


def _write_trait_scope_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    changed = tmp_path / 'src/ContentDispatcher.php'
    content_trait = tmp_path / 'src/Traits/ContentCreationTrait.php'
    status_trait = tmp_path / 'src/Traits/StatusUpdaterTrait.php'
    for path in (changed, content_trait, status_trait):
        path.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text(
        '<?php\nnamespace App;\nuse App\\Traits\\ContentCreationTrait;\n'
        'class ContentDispatcher { use ContentCreationTrait; }',
        encoding='utf-8',
    )
    content_trait.write_text(
        '<?php\nnamespace App\\Traits;\ntrait ContentCreationTrait { use StatusUpdaterTrait; }',
        encoding='utf-8',
    )
    status_trait.write_text(
        '<?php\nnamespace App\\Traits;\ntrait StatusUpdaterTrait {}',
        encoding='utf-8',
    )
    return changed, content_trait, status_trait


def _phpstan_documents(paths: list[Path]) -> str:
    return json.dumps({
        'files': {
            str(path): {'messages': [{'message': 'property.onlyWritten', 'line': 12}]}
            for path in paths
        },
        'errors': [],
    })


def test_scoped_phpstan_includes_transitive_traits_and_filters_unchanged_findings(tmp_path: Path):
    changed, content_trait, status_trait = _write_trait_scope_fixture(tmp_path)
    rule = _rule(tmp_path, {}, filter_files={'src/ContentDispatcher.php'})
    rule.output_folder = tmp_path / 'reports'
    rule.output_folder.mkdir()
    seen = {}

    def fake_run(cmd, *_args, **_kwargs):
        seen['cmd'] = cmd
        return SimpleNamespace(
            returncode=0,
            stdout=_phpstan_documents([changed, content_trait, status_trait]),
            stderr='',
        )

    rule._run_subprocess = fake_run

    result = rule._run_phpstan_check('phpstan')

    assert result.status == RuleStatus.OK
    assert len(result.violations) == 1
    assert result.violations[0].file_path.replace('\\', '/') == 'src/ContentDispatcher.php'
    assert all(str(path) in seen['cmd'] for path in (changed, content_trait, status_trait))
    csv_report = (rule.output_folder / 'phpstan_analyze.csv').read_text(encoding='utf-8')
    assert 'ContentDispatcher.php' in csv_report
    assert 'ContentCreationTrait.php' not in csv_report
    assert 'StatusUpdaterTrait.php' not in csv_report


def test_scoped_phpstan_keeps_findings_for_changed_trait_files(tmp_path: Path):
    changed, content_trait, status_trait = _write_trait_scope_fixture(tmp_path)
    rule = _rule(tmp_path, {}, filter_files={'src/ContentDispatcher.php', 'src/Traits/ContentCreationTrait.php'})
    rule._run_subprocess = lambda *_args, **_kwargs: SimpleNamespace(
        returncode=0,
        stdout=_phpstan_documents([changed, content_trait, status_trait]),
        stderr='',
    )

    result = rule._run_phpstan_check('phpstan')

    assert result.status == RuleStatus.OK
    assert {violation.file_path.replace('\\', '/') for violation in result.violations} == {
        'src/ContentDispatcher.php',
        'src/Traits/ContentCreationTrait.php',
    }


def test_scoped_phpstan_does_not_add_excluded_traits(tmp_path: Path):
    changed, content_trait, _status_trait = _write_trait_scope_fixture(tmp_path)
    excluded_trait = tmp_path / 'src/vendor/ExcludedTrait.php'
    excluded_trait.parent.mkdir(parents=True)
    excluded_trait.write_text(
        '<?php\nnamespace App\\Traits;\ntrait ExcludedTrait {}', encoding='utf-8')
    changed.write_text(
        '<?php\nnamespace App;\nclass ContentDispatcher { use App\\Traits\\ExcludedTrait; }',
        encoding='utf-8',
    )
    rule = _rule(tmp_path, {'exclude_patterns': ['src/vendor/**']}, filter_files={'src/ContentDispatcher.php'})
    seen = {}

    def fake_run(cmd, *_args, **_kwargs):
        seen['cmd'] = cmd
        return SimpleNamespace(returncode=0, stdout=_phpstan_documents([changed]), stderr='')

    rule._run_subprocess = fake_run

    result = rule._run_phpstan_check('phpstan')

    assert result.status == RuleStatus.OK
    assert str(changed) in seen['cmd']
    assert str(excluded_trait) not in seen['cmd']
    assert str(content_trait) not in seen['cmd']


def test_full_project_phpstan_does_not_add_trait_paths(tmp_path: Path):
    changed, content_trait, status_trait = _write_trait_scope_fixture(tmp_path)
    rule = _rule(tmp_path, {'analyze_path': 'src'})
    seen = {}

    def fake_run(cmd, *_args, **_kwargs):
        seen['cmd'] = cmd
        return SimpleNamespace(returncode=0, stdout='{"files":[],"errors":[]}', stderr='')

    rule._run_subprocess = fake_run

    result = rule._run_phpstan_check('phpstan')

    assert result.status == RuleStatus.OK
    assert str(tmp_path / 'src') in seen['cmd']
    assert str(changed) not in seen['cmd']
    assert str(content_trait) not in seen['cmd']
    assert str(status_trait) not in seen['cmd']

