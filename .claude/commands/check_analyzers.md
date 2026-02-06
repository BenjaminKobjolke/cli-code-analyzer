---
description: Check if a project has all available analyzers configured and suggest missing ones
---

Ask the user for:
1. The language/system of their project (Flutter, PHP, Python, CSharp, JavaScript)
2. The path to their example project

Then:
1. Read @analyzer_registry.py to see all available analyzers for that language
2. Look for the project's rules JSON file (check tools/code_analysis_rules.json and code_analysis_rules.json)
3. Compare which analyzers are enabled vs available
4. Read the documentation for each missing analyzer from @docs/analyzers/
5. Read the setup guide from @docs/setup/ for the language
6. Present a summary: which analyzers are active, which are missing, and for each missing one explain what it checks and recommend configuration
7. Offer to create a plan to add the missing analyzers to the project's configuration
