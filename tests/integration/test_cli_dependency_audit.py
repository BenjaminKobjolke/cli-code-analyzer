"""CLI-level dependency audit tests with isolated fake package tools."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PIP_AUDIT = json.dumps({"dependencies": [{"name": "jinja2", "version": "3.1.3", "vulns": [{
    "id": "GHSA-python", "fix_versions": ["3.1.4"], "description": "python issue"
}]}]})
PUB = json.dumps({"packages": [
    {"package": "dart_pkg", "kind": "direct", "current": {"version": "1.0"},
     "latest": {"version": "2.0"}, "isCurrentAffectedByAdvisory": False}
]})
COMPOSER_AUDIT = json.dumps({"advisories": {}})
COMPOSER_OUTDATED = json.dumps({"locked": [{
    "name": "vendor/pkg", "version": "1.0", "latest": "2.0", "latest-status": "update-possible"
}]})


def _write_fake_tools(
    bin_dir: Path, *, broken_composer: bool = False, empty_composer: bool = False,
    fvm_pinned: bool = False,
) -> None:
    if os.name == "nt":
        scripts = {
            "uv.bat": '@echo off\nif "%1"=="export" (echo requirements>%8 & exit /b 0)\necho root v1.0\necho └── python_pkg v1.0 (latest: v2.0)\n',
            "uvx.bat": f'@echo off\necho {PIP_AUDIT}\n',
            "composer.bat": (
                '@echo off\nif "%1"=="audit" (\n'
                + ('echo invalid json\nexit /b 1\n' if broken_composer else
                   'exit /b 0\n' if empty_composer else f'echo {COMPOSER_AUDIT}\nexit /b 0\n')
                + (')\necho []\n' if empty_composer else f')\necho {COMPOSER_OUTDATED}\n')
            ),
        }
        if fvm_pinned:
            scripts["fvm.bat"] = f'@echo off\necho {PUB}\n'
        else:
            scripts["dart.bat"] = f'@echo off\necho {PUB}\n'
        for name, body in scripts.items():
            (bin_dir / name).write_text(body, encoding="utf-8")
        return
    scripts = {
        "uv": "#!/bin/sh\nif [ \"$1\" = export ]; then echo requirements > \"$8\"; exit 0; fi\nprintf '%s\\n' 'root v1.0' '└── python_pkg v1.0 (latest: v2.0)'\n",
        "uvx": f"#!/bin/sh\nprintf '%s\\n' '{PIP_AUDIT}'\n",
        "composer": (
            "#!/bin/sh\nif [ \"$1\" = audit ]; then\n"
            + ("echo 'invalid json'; exit 1\n" if broken_composer else
               "exit 0\n" if empty_composer else f"printf '%s\\n' '{COMPOSER_AUDIT}'; exit 0\n")
            + ("fi\nprintf '%s\\n' '[]'\n" if empty_composer else
               f"fi\nprintf '%s\\n' '{COMPOSER_OUTDATED}'\n")
        ),
    }
    if fvm_pinned:
        scripts["fvm"] = f"#!/bin/sh\nprintf '%s\\n' '{PUB}'\n"
    else:
        scripts["dart"] = f"#!/bin/sh\nprintf '%s\\n' '{PUB}'\n"
    for name, body in scripts.items():
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)


def _checkout(
    tmp_path: Path, *, broken_composer: bool = False, empty_composer: bool = False,
    fvm_pinned: bool = False,
) -> tuple[Path, dict[str, int]]:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (checkout / "composer.lock").write_text(json.dumps({"packages": [], "packages-dev": []}), encoding="utf-8")
    pubspec = "name: sample\ndependencies:\n  flutter:\n    sdk: flutter\n" if fvm_pinned else "name: sample\n"
    (checkout / "pubspec.yaml").write_text(pubspec, encoding="utf-8")
    (checkout / "pubspec.lock").write_text("packages: {}\n", encoding="utf-8")
    if fvm_pinned:
        (checkout / ".fvmrc").write_text('{"flutter": "3.24.0"}', encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_tools(
        bin_dir, broken_composer=broken_composer, empty_composer=empty_composer,
        fvm_pinned=fvm_pinned,
    )
    return checkout, {str(file): file.stat().st_mtime_ns for file in checkout.iterdir()}


def _run_audit(checkout: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--audit-dependencies", "--path", str(checkout)],
        capture_output=True, text=True, timeout=180, check=False, env=env,
    )


@pytest.mark.parametrize("broken_composer", [False, True])
def test_cli_audits_stacks_emits_json_and_leaves_checkout_unchanged(tmp_path, broken_composer):
    checkout, before = _checkout(tmp_path, broken_composer=broken_composer)
    result = _run_audit(checkout, tmp_path / "bin")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert any(item["ecosystem"] == "python" for item in data["advisories"] + data["outdated"]), data
    assert "vendor/pkg" in {item["package"] for item in data["outdated"]}
    assert "dart_pkg" in {item["package"] for item in data["outdated"]}
    if broken_composer:
        assert any(item["ecosystem"] == "php" for item in data["errors"])
    assert "python issue" not in result.stderr
    assert {str(file): file.stat().st_mtime_ns for file in checkout.iterdir()} == before


def test_cli_accepts_composer_with_no_packages(tmp_path):
    checkout, _before = _checkout(tmp_path, empty_composer=True)
    result = _run_audit(checkout, tmp_path / "bin")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert not any(item["ecosystem"] == "php" for item in data["errors"])
    assert not any(item["ecosystem"] == "php" for item in data["advisories"])
    assert not any(item["ecosystem"] == "php" for item in data["outdated"])


def test_cli_uses_fvm_for_pinned_flutter_checkout_and_leaves_checkout_unchanged(tmp_path):
    checkout, before = _checkout(tmp_path, fvm_pinned=True)
    result = _run_audit(checkout, tmp_path / "bin")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert any(item["package"] == "dart_pkg" for item in data["outdated"])
    assert not any(item["ecosystem"] == "dart" for item in data["errors"])
    assert {str(file): file.stat().st_mtime_ns for file in checkout.iterdir()} == before
