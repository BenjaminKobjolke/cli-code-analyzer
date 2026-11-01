from pathlib import Path

from rules.php_trait_scope import build_trait_index, resolve_used_trait_files


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_resolves_traits_transitively_without_closure_uses(tmp_path: Path):
    changed = _write(
        tmp_path / "src/ContentDispatcher.php",
        """<?php
namespace App;
use App\\Traits\\ContentCreationTrait;
class ContentDispatcher {
    use ContentCreationTrait;
    function () use ($x) {}
}
""",
    )
    content = _write(
        tmp_path / "src/Traits/ContentCreationTrait.php",
        """<?php
namespace App\\Traits;
trait ContentCreationTrait { use StatusUpdaterTrait; }
""",
    )
    status = _write(
        tmp_path / "src/Traits/StatusUpdaterTrait.php",
        "<?php\nnamespace App\\Traits;\ntrait StatusUpdaterTrait {}",
    )
    _write(
        tmp_path / "src/Traits/UnusedTrait.php",
        "<?php\nnamespace App\\Traits;\ntrait UnusedTrait {}",
    )

    index = build_trait_index(list((tmp_path / "src").rglob("*.php")))

    assert resolve_used_trait_files([changed], index) == [content, status]


def test_resolves_alias_and_fully_qualified_trait_names(tmp_path: Path):
    aliased = _write(
        tmp_path / "src/Aliased.php",
        """<?php
namespace App;
use App\\Traits\\ContentCreationTrait as Creation;
class Aliased { use Creation; }
""",
    )
    qualified = _write(
        tmp_path / "src/Qualified.php",
        "<?php\nnamespace App;\nclass Qualified { use \\App\\Traits\\StatusUpdaterTrait; }",
    )
    content = _write(
        tmp_path / "src/Traits/ContentCreationTrait.php",
        "<?php\nnamespace App\\Traits;\ntrait ContentCreationTrait {}",
    )
    status = _write(
        tmp_path / "src/Traits/StatusUpdaterTrait.php",
        "<?php\nnamespace App\\Traits;\ntrait StatusUpdaterTrait {}",
    )
    index = build_trait_index([content, status, aliased, qualified])

    assert resolve_used_trait_files([aliased, qualified], index) == [content, status]


def test_trait_resolution_is_case_insensitive_and_skips_changed_trait(tmp_path: Path):
    changed_trait = _write(
        tmp_path / "src/Traits/SharedTrait.php",
        "<?php\nnamespace App\\Traits;\ntrait SharedTrait {}",
    )
    user = _write(
        tmp_path / "src/User.php",
        "<?php\nnamespace App;\nclass User { use \\app\\traits\\sharedtrait; }",
    )
    index = build_trait_index([changed_trait, user])

    assert resolve_used_trait_files([changed_trait], index) == []
    assert resolve_used_trait_files([user], index) == [changed_trait]


def test_trait_cycles_terminate(tmp_path: Path):
    changed = _write(
        tmp_path / "src/Changed.php",
        "<?php\nnamespace App;\nclass Changed { use FirstTrait; }",
    )
    first = _write(
        tmp_path / "src/FirstTrait.php",
        "<?php\nnamespace App;\ntrait FirstTrait { use SecondTrait; }",
    )
    second = _write(
        tmp_path / "src/SecondTrait.php",
        "<?php\nnamespace App;\ntrait SecondTrait { use FirstTrait; }",
    )
    index = build_trait_index([changed, first, second])

    assert resolve_used_trait_files([changed], index) == [first, second]
