"""Data-driven external tool registry.

Each tool's get/set/prompt behavior is the same shape; only the strings differ.
This module owns the table so `settings.py` stays focused on the configparser-
backed storage and dispatch.
"""
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from logger import Logger
from pmd_downloader import download_pmd


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    section: str
    key: str
    prompt_msg: str
    saved_label: str
    error_label: str
    install_msgs: tuple[str, ...] = ()
    skip_msg: str | None = None
    downloader: Callable[[Logger], Path | None] | None = None


def _pmd_downloader(logger: Logger) -> Path | None:
    logger.info("\nDownloading PMD...")
    return download_pmd(logger=logger)


TOOLS: list[ToolDescriptor] = [
    ToolDescriptor(
        name="pmd",
        section="pmd",
        key="pmd_path",
        prompt_msg="PMD path not configured. Enter path to pmd.bat (leave empty to download): ",
        saved_label="PMD",
        error_label="PMD",
        downloader=_pmd_downloader,
    ),
    ToolDescriptor(
        name="dart",
        section="dart",
        key="dart_path",
        install_msgs=(
            "\nDart executable not found in PATH.",
            "Please ensure Flutter/Dart SDK is installed.",
            "Download from: https://docs.flutter.dev/get-started/install",
        ),
        prompt_msg="\nEnter path to dart executable (or press Enter to skip): ",
        skip_msg="Skipping dart analyze rule. Install Dart SDK and configure later.",
        saved_label="Dart",
        error_label="Dart",
    ),
    ToolDescriptor(
        name="flutter",
        section="flutter",
        key="flutter_path",
        install_msgs=(
            "\nFlutter executable not found in PATH.",
            "Please ensure Flutter SDK is installed.",
            "Download from: https://docs.flutter.dev/get-started/install",
        ),
        prompt_msg="\nEnter path to flutter executable (or press Enter to skip): ",
        skip_msg="Skipping flutter analyze rule. Install Flutter SDK and configure later.",
        saved_label="Flutter",
        error_label="Flutter",
    ),
    ToolDescriptor(
        name="ruff",
        section="ruff",
        key="ruff_path",
        install_msgs=(
            "\nRuff executable not found in PATH.",
            "Ruff is a fast Python linter written in Rust.",
            "Install with: pip install ruff",
            "Or download from: https://docs.astral.sh/ruff/installation/",
        ),
        prompt_msg="\nEnter path to ruff executable (or press Enter to skip): ",
        skip_msg="Skipping ruff analyze rule. Install Ruff and configure later.",
        saved_label="Ruff",
        error_label="Ruff",
    ),
    ToolDescriptor(
        name="phpstan",
        section="phpstan",
        key="phpstan_path",
        install_msgs=(
            "\nPHPStan executable not found in PATH.",
            "Install with: composer require --dev phpstan/phpstan",
            "Or in the php/ subfolder: cd php && composer install",
        ),
        prompt_msg="\nEnter path to phpstan executable (or press Enter to skip): ",
        skip_msg="Skipping phpstan analyze rule. Install PHPStan and configure later.",
        saved_label="PHPStan",
        error_label="PHPStan",
    ),
    ToolDescriptor(
        name="php_cs_fixer",
        section="php_cs_fixer",
        key="php_cs_fixer_path",
        install_msgs=(
            "\nPHP-CS-Fixer executable not found in PATH.",
            "Install with: composer require --dev friendsofphp/php-cs-fixer",
            "Or in the php/ subfolder: cd php && composer install",
        ),
        prompt_msg="\nEnter path to php-cs-fixer executable (or press Enter to skip): ",
        skip_msg="Skipping php_cs_fixer rule. Install PHP-CS-Fixer and configure later.",
        saved_label="PHP-CS-Fixer",
        error_label="PHP-CS-Fixer",
    ),
    ToolDescriptor(
        name="dotnet",
        section="dotnet",
        key="dotnet_path",
        install_msgs=(
            "\ndotnet executable not found in PATH.",
            "Please ensure .NET SDK is installed.",
            "Download from: https://dotnet.microsoft.com/download",
        ),
        prompt_msg="\nEnter path to dotnet executable (or press Enter to skip): ",
        skip_msg="Skipping dotnet_analyze rule. Install .NET SDK and configure later.",
        saved_label="dotnet",
        error_label="dotnet",
    ),
    ToolDescriptor(
        name="eslint",
        section="eslint",
        key="eslint_path",
        install_msgs=(
            "\nESLint executable not found in PATH.",
            "ESLint is a JavaScript/TypeScript linter.",
            "Install with: npm install -g eslint",
            "Or locally: npm install --save-dev eslint",
        ),
        prompt_msg="\nEnter path to eslint executable (or press Enter to skip): ",
        skip_msg="Skipping eslint analyze rule. Install ESLint and configure later.",
        saved_label="ESLint",
        error_label="ESLint",
    ),
    ToolDescriptor(
        name="svelte_check",
        section="svelte_check",
        key="svelte_check_path",
        install_msgs=(
            "\nsvelte-check executable not found in PATH.",
            "svelte-check is a type checker for Svelte projects.",
            "Install with: npm install --save-dev svelte-check",
        ),
        prompt_msg="\nEnter path to svelte-check executable (or press Enter to skip): ",
        skip_msg="Skipping svelte_check rule. Install svelte-check and configure later.",
        saved_label="svelte-check",
        error_label="svelte-check",
    ),
    ToolDescriptor(
        name="tsc",
        section="tsc",
        key="tsc_path",
        install_msgs=(
            "\ntsc executable not found in PATH.",
            "TypeScript compiler is required for type checking.",
            "Install with: npm install --save-dev typescript",
            "Or globally: npm install -g typescript",
        ),
        prompt_msg="\nEnter path to tsc executable (or press Enter to skip): ",
        skip_msg="Skipping tsc_analyze rule. Install TypeScript and configure later.",
        saved_label="tsc",
        error_label="tsc",
    ),
    ToolDescriptor(
        name="pyscn",
        section="pyscn",
        key="pyscn_path",
        install_msgs=(
            "\npyscn executable not found in PATH.",
            "pyscn is a structural Python code analyzer (complexity, dead code, coupling).",
            "Install with: pipx install pyscn",
            "Or: uvx pyscn@latest analyze .",
            "Or: go install github.com/ludo-technologies/pyscn/cmd/pyscn@latest",
        ),
        prompt_msg="\nEnter path to pyscn executable (or press Enter to skip): ",
        skip_msg="Skipping pyscn_analyze rule. Install pyscn and configure later.",
        saved_label="pyscn",
        error_label="pyscn",
    ),
    ToolDescriptor(
        name="autohotkey_v2",
        section="autohotkey",
        key="autohotkey_v2_path",
        install_msgs=(
            "\nAutoHotkey v2 interpreter not found (needed for v2 scripts).",
            "Validation uses the /validate switch (v2 only).",
            "Download from: https://www.autohotkey.com/",
        ),
        prompt_msg="\nEnter path to AutoHotkey64.exe (v2) (or press Enter to skip): ",
        skip_msg="Skipping AutoHotkey v2 validation. Install AutoHotkey v2 and configure later.",
        saved_label="AutoHotkey v2",
        error_label="AutoHotkey v2",
    ),
    ToolDescriptor(
        name="autohotkey_v1",
        section="autohotkey",
        key="autohotkey_v1_path",
        install_msgs=(
            "\nAutoHotkey v1 interpreter not found (needed for v1 scripts).",
            "Validation uses the /iLib switch (v1).",
            "Download from: https://www.autohotkey.com/",
        ),
        prompt_msg="\nEnter path to AutoHotkeyU64.exe (v1) (or press Enter to skip): ",
        skip_msg="Skipping AutoHotkey v1 validation. Install AutoHotkey v1 and configure later.",
        saved_label="AutoHotkey v1",
        error_label="AutoHotkey v1",
    ),
    ToolDescriptor(
        name="dart_lsp_mcp",
        section="dart_lsp_mcp",
        key="dart_lsp_mcp_path",
        install_msgs=(
            "\ndart-lsp-mcp not found.",
            "Required for dart_unused_code and dart_missing_dispose analyzers.",
            "Install from: https://github.com/BenjaminKobjolke/dart-lsp-mcp",
        ),
        prompt_msg="\nEnter path to dart-lsp-mcp directory (or press Enter to skip): ",
        skip_msg="Skipping dart-lsp-mcp dependent analyzers.",
        saved_label="dart-lsp-mcp",
        error_label="dart-lsp-mcp",
    ),
]

TOOLS_BY_NAME: dict[str, ToolDescriptor] = {t.name: t for t in TOOLS}
