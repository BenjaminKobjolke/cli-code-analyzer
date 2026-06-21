"""AutoHotkey syntax/load validation via the real AHK interpreter.

Instead of regex heuristics, this rule runs the actual AutoHotkey interpreter in
load-but-don't-execute mode and parses the load errors it reports. Empirically
verified on v1.1.37 and v2.0.10 (see docs/analyzers/autohotkey_analyze.md):

  v2:  AutoHotkey64.exe  /ErrorStdOut=UTF-8 /validate "<root>.ahk"
  v1:  AutoHotkeyU64.exe /iLib "<discard>"  /ErrorStdOut    "<root>.ahk"

Both load + syntax-check WITHOUT executing the script (no GUI / app launch),
write errors to stderr as `<file> (<line>) : ==> <message>` (+ an optional
indented continuation line), and exit 2 on error / 0 when clean. AHK projects
are #Include-based, so only entry-point ("root") scripts are validated; an
included sub-file is checked through its root, and errors map to the correct
sub-file. v1 resolves relative #Include against the working directory, so the
interpreter must run with cwd = the root's directory.
"""

import re
import tempfile
from pathlib import Path

from file_discovery import FileDiscovery
from models import RuleResult, Severity, Violation
from path_utils import to_relative_posix
from rules.base import ProjectWideRule

AHK_EXTENSIONS = ('.ahk', '.ah2', '.ahk2')

_V2_EXE = 'AutoHotkey64.exe'
_V1_EXE = 'AutoHotkeyU64.exe'

# `#Include [*flags] FileOrDir` / `#IncludeAgain ...`; capture the target.
_INCLUDE_RE = re.compile(r'^\s*#Include(?:Again)?\s+(.+?)\s*$', re.IGNORECASE | re.MULTILINE)
# A script is v2 if it requires AutoHotkey v2 (v2 scripts conventionally declare
# this; legacy v1 scripts usually don't), otherwise it is treated as v1.
_REQUIRES_V2_RE = re.compile(r'#Requires\s+AutoHotkey\s+v?2', re.IGNORECASE)
# Load-error line emitted to stderr by both v1 and v2.
_ERROR_LINE_RE = re.compile(r'^(?P<file>.+?) \((?P<line>\d+)\) : ==> (?P<msg>.*)$')


class AutoHotkeyAnalyzeRule(ProjectWideRule):
    """Validate AutoHotkey root scripts using the matching AHK interpreter."""

    rule_name = 'autohotkey_analyze'

    def _run(self, _file_path: Path) -> RuleResult:
        self.logger.info("\nRunning AutoHotkey validation...")

        files = self._discover_ahk_files()
        if not files:
            return self._ok([])

        adjacency, included = self._build_include_graph(files)
        roots = [f for f in files if f not in included] or list(files)
        roots = self._scope_roots(roots, adjacency)

        violations: list[Violation] = []
        ran = skipped_missing = 0
        for root in roots:
            result = self._validate_root(root)
            if result is None:
                skipped_missing += 1
                continue
            ran += 1
            violations.extend(result)

        if ran == 0 and skipped_missing:
            return self._skipped("AutoHotkey interpreter not configured")

        # Two roots may include the same broken sub-file; report each issue once.
        violations = self._dedupe(violations)
        violations = self._filter_violations_by_log_level(violations)
        if self.max_errors and len(violations) > self.max_errors:
            violations = violations[:self.max_errors]

        if violations:
            self.logger.info(f"AutoHotkey: {len(violations)} issue(s) found")
        else:
            self.logger.info("AutoHotkey: no issues found")

        if self.output_folder and violations:
            self._write_violations_csv(
                self.output_folder / 'autohotkey_analyze.csv',
                violations,
                ['file', 'line', 'severity', 'message'],
                lambda v: [v.file_path, v.line, v.severity.value, v.message],
            )

        return self._ok(violations)

    # ------------------------------------------------------------------ discovery

    def _discover_ahk_files(self) -> list[Path]:
        """All AutoHotkey files under base_path (resolved, for stable graph keys)."""
        discovery = FileDiscovery(['autohotkey'], str(self.base_path))
        return [f.resolve() for f in discovery.discover()]

    def _build_include_graph(self, files: list[Path]) -> tuple[dict[Path, list[Path]], set[Path]]:
        """Map each file to the discovered files it #Includes, and the included set.

        Includes are matched leniently by basename (handles `<Lib>`,
        `%A_ScriptDir%\\x.ahk`, and relative paths without a full path resolver).
        """
        by_name: dict[str, list[Path]] = {}
        for f in files:
            by_name.setdefault(f.name.lower(), []).append(f)

        adjacency: dict[Path, list[Path]] = {}
        included: set[Path] = set()
        for f in files:
            targets: list[Path] = []
            for raw in _INCLUDE_RE.findall(self._read(f)):
                for match in self._resolve_include(raw, by_name):
                    if match != f:
                        targets.append(match)
                        included.add(match)
            adjacency[f] = targets
        return adjacency, included

    def _resolve_include(self, raw: str, by_name: dict[str, list[Path]]) -> list[Path]:
        """Resolve a raw #Include target string to discovered file(s) by basename."""
        target = raw.strip().strip('"')
        # Drop a leading option flag like `*i ` / `*` used by #Include.
        if target.startswith('*'):
            parts = target.split(None, 1)
            target = parts[1] if len(parts) > 1 else ''
        target = target.strip().strip('<>').replace('\\', '/')
        if not target:
            return []
        name = target.rsplit('/', 1)[-1].lower()
        return by_name.get(name, [])

    def _scope_roots(self, roots: list[Path], adjacency: dict[Path, list[Path]]) -> list[Path]:
        """In --file/--only-changed mode keep only roots covering a filtered file."""
        if not self.filter_files:
            return roots
        scoped = []
        for root in roots:
            closure = self._closure(root, adjacency)
            if any(to_relative_posix(f, self.base_path) in self.filter_files for f in closure):
                scoped.append(root)
        return scoped

    def _closure(self, root: Path, adjacency: dict[Path, list[Path]]) -> set[Path]:
        """Root plus everything it transitively #Includes."""
        seen: set[Path] = set()
        stack = [root]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adjacency.get(cur, []))
        return seen

    # ------------------------------------------------------------------ validation

    def _validate_root(self, root: Path) -> list[Violation] | None:
        """Validate one root script. Returns violations, or None if no interpreter."""
        if self._is_v2(root):
            exe = self._get_tool_path(_V2_EXE, 'autohotkey_v2')
            if not exe:
                return None
            cmd = [exe, '/ErrorStdOut=UTF-8', '/validate', str(root)]
        else:
            exe = self._get_tool_path(_V1_EXE, 'autohotkey_v1')
            if not exe:
                return None
            discard = str(Path(tempfile.gettempdir()) / 'ahk_ilib_discard.txt')
            cmd = [exe, '/iLib', discard, '/ErrorStdOut', str(root)]

        result = self._run_subprocess(cmd, cwd=root.parent)
        return self._parse_stderr(result.stderr)

    def _is_v2(self, root: Path) -> bool:
        return bool(_REQUIRES_V2_RE.search(self._read(root)))

    def _parse_stderr(self, stderr: str) -> list[Violation]:
        """Parse AHK load-error stderr into ERROR violations."""
        violations: list[Violation] = []
        if not stderr:
            return violations

        lines = stderr.splitlines()
        i = 0
        while i < len(lines):
            m = _ERROR_LINE_RE.match(lines[i])
            if not m:
                i += 1
                continue
            msg = m.group('msg').strip()
            # Fold indented continuation lines (e.g. "     Specifically: ...").
            j = i + 1
            while j < len(lines) and lines[j][:1] in (' ', '\t') and lines[j].strip():
                msg += ' ' + lines[j].strip()
                j += 1
            violations.append(Violation(
                file_path=self._get_relative_path(Path(m.group('file').strip())),
                rule_name=self.rule_name,
                severity=Severity.ERROR,
                message=msg,
                line=int(m.group('line')),
            ))
            i = j
        return violations

    # ------------------------------------------------------------------ helpers

    def _read(self, path: Path) -> str:
        # utf-8-sig strips a leading BOM so `#Include` / `#Requires` on the first
        # line still match (BOM-prefixed .ahk files are common on Windows).
        try:
            return path.read_text(encoding='utf-8-sig', errors='replace')
        except Exception as e:
            self.logger.warning(f"Warning: could not read {path}: {e}")
            return ''

    def _dedupe(self, violations: list[Violation]) -> list[Violation]:
        seen: set[tuple[str, int | None, str]] = set()
        unique: list[Violation] = []
        for v in violations:
            key = (v.file_path, v.line, v.message)
            if key not in seen:
                seen.add(key)
                unique.append(v)
        return unique
