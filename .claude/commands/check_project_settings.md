---
description: Check if a project's batch file setup is outdated and migrate to the config pattern

argument-hint: project path
---

The user's project path argument is: $ARGUMENTS

If $ARGUMENTS is empty or not provided, ask the user for the path to their project.

Check which type of project it is we support.
CSharp, Flutter, JavaScript/TypeScript, PHP or Python.
If you cant determine it ask the user for the type of project.

Then check the project's `tools/` folder for outdated batch file patterns. A project is outdated if ANY of these are true:
- `tools/analyze_code.bat` exists but does NOT contain `call "%~dp0analyze_code_config.bat"`
- `tools/analyze_code_config.example.bat` does not exist
- Old `tools/config.bat` exists (legacy naming)
- `.gitignore` does not contain `tools/analyze_code_config.bat`

If the project is already up-to-date (none of the above apply), tell the user and stop.

If the project is outdated, read the templates and apply the new config pattern:

1. Read @prompts/setup_files/analyze_code_config.example.bat — use this as the template for creating `tools/analyze_code_config.example.bat`, but set `LANGUAGE=` to the correct language for the project
2. Copy the example to `tools/analyze_code_config.bat` with the user's actual `CLI_ANALYZER_PATH` (check the old batch files to extract the existing path, or ask the user)
3. Read @prompts/setup_files/analyze_code.bat — use this to rewrite `tools/analyze_code.bat`
4. If `tools/fix_issues.bat` or any fixer batch file exists, read @prompts/setup_files/fix_issues.bat and rewrite it using the same config pattern
5. Delete old `tools/config.bat` if it exists
6. Add `tools/analyze_code_config.bat` to `.gitignore` if not already present

After migration, summarize what was changed.
