# C# Project Setup

This guide explains how to set up cli-code-analyzer for C# / .NET projects.

## Prerequisites

- Python 3.9+
- .NET SDK (any version: .NET Framework 4.x, .NET Core, .NET 5/6/7/8+)
- PMD (optional, for duplicate code detection)

## Quick Start

1. Ensure .NET SDK is installed and `dotnet` is in your PATH:
   ```bash
   dotnet --version
   ```

2. Run analysis:
   ```bash
   python main.py --language csharp --path /path/to/your/project
   ```

## Available Rules

| Rule | Description |
|------|-------------|
| `max_lines_per_file` | Checks file length against warning/error thresholds |
| `pmd_duplicates` | Detects duplicate code blocks (requires PMD) |
| `dotnet_analyze` | Static analysis using dotnet build with Roslyn analyzers |

## Example Configuration

Create a `code_analysis_rules.json` file in your project:

```json
{
  "log_level": "all",
  "max_lines_per_file": {
    "enabled": true,
    "warning": 300,
    "error": 500,
    "exclude_patterns": ["bin/**", "obj/**", ".vs/**", "packages/**"]
  },
  "pmd_duplicates": {
    "enabled": true,
    "minimum_tokens": 100,
    "exclude_patterns": {
      "cs": ["**/bin/**", "**/obj/**", "**/.vs/**", "**/packages/**"]
    }
  },
  "dotnet_analyze": {
    "enabled": true,
    "configuration": "Debug",
    "solution_path": "MySolution.sln",
    "ignore_codes": ["CS0168", "CS0219"],
    "exclude_patterns": ["bin/**", "obj/**", ".vs/**", "packages/**"]
  }
}
```

## Dotnet Analyze Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `configuration` | Build configuration (Debug/Release) | `Debug` |
| `solution_path` | Path to .sln file (relative to project) | Auto-detect |
| `project_path` | Path to .csproj file (if no solution) | Auto-detect |
| `ignore_codes` | List of warning codes to ignore | `[]` |
| `exclude_patterns` | Glob patterns to exclude from file discovery | `[]` |

### Common Warning Codes to Ignore

| Code | Description |
|------|-------------|
| `CS0168` | Variable declared but never used |
| `CS0219` | Variable assigned but never used |
| `CS0414` | Private field assigned but never used |
| `CS0649` | Field is never assigned |
| `CS1591` | Missing XML comment for publicly visible type |

## Roslyn Analyzers

The `dotnet build` command uses built-in Roslyn analyzers. You can add additional analyzers to your project:

### StyleCop.Analyzers
```bash
dotnet add package StyleCop.Analyzers
```

### Roslynator
```bash
dotnet add package Roslynator.Analyzers
```

### Microsoft.CodeAnalysis.NetAnalyzers
Included by default in .NET 5+ projects.

## Exclusion Patterns

Common patterns to exclude from analysis:

| Pattern | Purpose |
|---------|---------|
| `bin/**` | Build output directory |
| `obj/**` | Intermediate build files |
| `.vs/**` | Visual Studio settings |
| `packages/**` | NuGet packages (old format) |
| `node_modules/**` | npm dependencies (if applicable) |
| `.git/**` | Git repository data |
| `*.Designer.cs` | Auto-generated designer files |
| `*.g.cs` | Generated code files |

## Example Batch Files (Windows)

Create a `tools` subfolder in your project and place the batch files there.

> **Note:** Do not add `pause` at the end of batch files. These scripts are designed to be called by other tools and `pause` would block execution.

### Analyze Code

Create `tools/analyze_code.bat`:

```batch
@echo off
d:
cd "d:\path\to\cli-code-analyzer"

call venv\Scripts\python.exe main.py --language csharp --path "D:\path\to\your\project" --verbosity minimal --output "D:\path\to\your\project\code_analysis_results" --maxamountoferrors 50 --rules "D:\path\to\your\project\code_analysis_rules.json"

cd %~dp0..
```

### Quick Build Check

Create `tools/check_build.bat` for a quick build verification:

```batch
@echo off
cd %~dp0..
dotnet build --no-incremental -c Debug
```

## CLI Options

### Analyzer (main.py)

| Option | Description | Default |
|--------|-------------|---------|
| `--language` | Set to `csharp` | Required |
| `--path` | Path to project directory or file | Required |
| `--rules` | Path to rules JSON file | `rules.json` |
| `--verbosity` | Output level: `minimal`, `normal`, `verbose` | `normal` |
| `--output` | Folder for CSV/TXT reports | None (console) |
| `--loglevel` | Filter: `error`, `warning`, `all` | `all` |
| `--maxamountoferrors` | Limit violations in CSV | Unlimited |

## Troubleshooting

### dotnet not found

If you get a dotnet path error:
1. Ensure .NET SDK is installed: https://dotnet.microsoft.com/download
2. Verify `dotnet` is in your PATH: `dotnet --version`
3. Run the analyzer once - it will prompt to configure the dotnet path
4. Or manually edit `settings.ini` in the cli-code-analyzer directory

### Build fails with errors

The analyzer runs `dotnet build` which may fail if your project has compilation errors. Fix these first:
```bash
dotnet build
```

### PMD not found

If you get a PMD path error:
1. Run the analyzer once - it will prompt to download/configure PMD
2. Or manually edit `settings.ini` in the cli-code-analyzer directory

### Exclusions not working

- Ensure patterns use `/**` for recursive matching
- Use forward slashes `/` in patterns, even on Windows
- Check your bin/obj directories match the patterns

### Many warnings from generated code

Add generated file patterns to exclude_patterns, or ignore specific codes:
```json
{
  "dotnet_analyze": {
    "ignore_codes": ["CS1591"],
    "exclude_patterns": ["*.Designer.cs", "*.g.cs"]
  }
}
```

### Analysis is slow

- Use `configuration: "Release"` if Debug builds are slow
- Consider limiting analysis to specific projects via `project_path`

## Project Type Support

| Project Type | Support Level |
|--------------|---------------|
| .NET Framework 4.x | Full (requires MSBuild/VS) |
| .NET Core 2.x/3.x | Full |
| .NET 5/6/7/8+ | Full |
| WinForms | Full |
| WPF | Full |
| ASP.NET Core | Full |
| Console Apps | Full |
| Class Libraries | Full |
| Unity Projects | Partial (may need Unity-specific setup) |

## Integration with Visual Studio

The analyzer uses the same Roslyn analyzers as Visual Studio, so results should be consistent. For best results:
1. Enable "Treat warnings as errors" in project properties for stricter analysis
2. Add an `.editorconfig` file to configure analyzer rules
3. Consider adding analyzer packages like StyleCop or Roslynator to your project
