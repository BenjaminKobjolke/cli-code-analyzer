# Exception growth tracking

Exception growth tracking warns when code that an exception or supported Ruff suppression keeps quiet grows beyond its previously accepted size. It is enabled by default and reports `WARNING` findings under the `exception_growth` rule.

## What is tracked

The analyzer records a value when a file exception raises a rule's threshold and the measured value has reached the rule's ordinary threshold. This covers supported threshold exceptions such as maximum file lines, Kotlin and PHP function metrics, PySCN complexity, CRAP score, Dart code-linter metrics, and Graphify fan-out. Dart inverse metrics, whose lower values are worse, are excluded.

For Python, Ruff-suppressed complexity is also tracked for `C901`, `PLR0911`, `PLR0912`, and `PLR0915`. The analyzer makes a second complexity-only Ruff pass with `--ignore-noqa` when tracking is enabled, then records findings whose function definition line has a matching `noqa` comment. This pass does not add ordinary Ruff findings to the report.

Whole-suppression exceptions such as PMD duplicate exceptions have no measured size and are not tracked. In-code suppressions from tools other than Ruff are not tracked. Ruff findings outside the four listed complexity codes are also outside this check.

## Baseline file

Each run uses the rules file beside the analyzed project. The baseline is written next to that rules file, with `.exception_baseline.json` replacing the rules file's `.json` suffix. For example, `code_analysis_rules.json` uses `code_analysis_rules.exception_baseline.json`.

The JSON file contains a version and sorted `entries`. Each entry identifies the rule, project-relative file, metric, optional function name, and accepted numeric value:

```json
{
  "version": 1,
  "entries": [
    {
      "file": "src/example.py",
      "function": "build_report",
      "metric": "C901",
      "rule": "ruff_analyze",
      "value": 12
    }
  ]
}
```

Commit the baseline with the project so all machines compare against the same accepted values. On the first analysis, the current values are recorded without a growth warning. When a value shrinks, the analyzer lowers the stored value. When it grows, the analyzer warns and leaves the stored value unchanged, so later runs continue to warn until the code shrinks or a person reviews and manually raises the value in the JSON file to accept the growth. New tracked exceptions are added automatically.

On a full, unfiltered analysis, entries no longer observed are pruned for rules that completed successfully. Filtered runs preserve unseen entries, as do failed or unrun rules. A corrupt or unsupported baseline is an error that names its path; the analyzer does not silently replace it.

## Runs and cache

An analysis that reads results from the violation cache does not inspect exception growth or update the baseline. Growth warnings found during an analysis run are included in that run's report and cached with its other violations. A later cache-only query can therefore show the cached warning, but it does not refresh the baseline.

## Opt out

Set the top-level `exception_growth` setting to `false` in the rules file to disable baseline loading, Ruff's extra suppression scan, growth warnings, and baseline writes:

```json
{
  "exception_growth": false
}
```
