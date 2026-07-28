# WordPress Theme / Plugin Setup

This guide covers cli-code-analyzer for **WordPress block themes (FSE) and plugins**.
It is a specialization of [PHP.md](PHP.md) — read this instead of PHP.md when the
project is WordPress.

## When this applies (detection)

Treat a PHP project as WordPress when any of these markers are present:

- `style.css` with a `Theme Name:` header (theme), or a plugin header
  (`Plugin Name:`) in a top-level PHP file.
- `functions.php` at the theme root.
- `theme.json` (block theme / FSE).
- A `wp-content/` path segment.

WordPress themes frequently have **no `composer.json`**, so generic PHP detection
(`composer.json` / `*.php`) misses them — the markers above are what identify a
WordPress project.

## What is different from generic PHP

WordPress uses its **own coding standard (WPCS)**, which is **tab-indented** and has
its own escaping/sanitization/i18n rules. This conflicts with the generic PHP
defaults:

| Generic PHP default | WordPress reality | Action |
|---------------------|-------------------|--------|
| `php_cs_fixer` with `@PSR12` | PSR-12 uses **spaces**; WPCS uses **tabs** | **Disable** `php_cs_fixer`. Never run a PSR-12 fixer bat (`fix_php_issues.bat`) — it reformats WPCS tabs to spaces across `src/`, `inc/`, `functions.php`. Enforce style with **PHPCS against the `WordPress` standard** instead (`tools/phpcs.bat` / `tools/phpcbf.bat`), set up separately. |
| `phpstan_analyze` level 5 | Floods without WordPress stubs | **Disable** (or add WP stubs first). |
| `intelephense_analyze` | Noisy without WP symbols | **Disable** unless configured. |
| Excludes `vendor/`, `node_modules/` | Themes also ship a generated `build/` dir (compiled blocks) | Also exclude **`build/`** — otherwise every `src/<block>/render.php` reports a false duplicate against its compiled `build/<block>/render.php` copy. |

Net: for a WordPress theme, keep only **`max_lines_per_file`** and
**`pmd_duplicates`** enabled. WordPress correctness/style is covered by PHPCS
(`WordPress` standard), not by this analyzer's PSR-12/PHPStan rules.

## Exclude patterns (nested dependencies)

WordPress deps live **nested**, e.g. `wp-content/themes/<slug>/vendor/`,
`.../node_modules/`, `.../build/` — not at the repo root. Use the recursive
`**/dir/**` form so they match at any depth:

- Put excludes in **`max_lines_per_file.exclude_patterns`** — that rule's list is
  what drives file discovery for all per-file rules (see `analyzer.py`). Excludes on
  `pmd_duplicates` alone will not stop `max_lines` from scanning `vendor/`.
- Also list them in `pmd_duplicates.exclude_patterns`.

## Example Configuration

Create `code_analysis_rules.json` in the project root:

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500,
    "exclude_patterns": ["**/vendor/**", "**/node_modules/**", "**/build/**", "**/.git/**"]
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "exclude_patterns": {
      "php": ["**/vendor/**", "**/node_modules/**", "**/build/**", "**/.git/**"]
    }
  },
  "pmd_similar_code": { "enabled": false },
  "phpstan_analyze": { "enabled": false },
  "php_cs_fixer": { "enabled": false },
  "intelephense_analyze": { "enabled": false }
}
```

> `php_cs_fixer`, `phpstan_analyze`, and `intelephense_analyze` are disabled on
> purpose (see the table above). Re-enable them only if you have added WordPress
> stubs / a tab-aware ruleset and understand they will otherwise fight WPCS.

## WordPress style enforcement (separate from this analyzer)

Set up PHPCS with the WordPress standard as its own tooling in the project's
`tools/` folder:

- `tools/phpcs.bat` — report violations against the `WordPress` standard.
- `tools/phpcbf.bat` — auto-fix (tab-aware). Use this **instead of** any PSR-12
  fixer bat.

## Troubleshooting

- **Full run scans thousands of files / floods with `vendor/` violations** — your
  nested deps are not excluded. Ensure `max_lines_per_file.exclude_patterns` uses
  the `**/vendor/**` form (recursive, any depth).
- **Every `src/*/render.php` shows a duplicate** — you did not exclude `build/`. Add
  `**/build/**`.
- **Source files got reformatted tabs→spaces** — a PSR-12 fixer bat was run. Revert
  (`git checkout -- <theme>`), delete `.php-cs-fixer.cache`, and use `phpcbf.bat`.
