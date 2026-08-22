"""
SQLite-based violation cache for fast --file queries.

The cache stores analyzer results so that subsequent --file queries
can filter from cached data instead of re-running all analyzers.
"""

import hashlib
import sqlite3
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from analyzer_fingerprint import compute_analyzer_hash
from logger import Logger
from models import Severity, Violation


class ViolationCache:
    """Read/write violation cache backed by SQLite."""

    def __init__(self, db_path: Path, logger: Logger | None = None):
        self.db_path = db_path
        self.logger = logger or Logger()
        self.analyzer_hash = compute_analyzer_hash()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with WAL mode and busy timeout."""
        con = sqlite3.connect(str(self.db_path), timeout=10)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_valid(self, max_age_minutes: int, rules_hash: str,
                 current_files: list[Path] | None = None,
                 base_path: str | None = None) -> bool:
        """Check whether the cache is fresh and matches rules and analyzer code.

        When `current_files` (the currently discovered source files) is given,
        the cache is additionally invalid if the analyzed file set changed
        (files added/removed vs the cached `file_paths`) or if any current file
        was modified after the cache was written (mtime newer than the stored
        `newest_mtime`). `base_path` relativizes `current_files` the same way
        the analyzer stored them.
        """
        if not self.db_path.exists():
            self.logger.info("Cache not found, will run full analysis")
            return False
        try:
            con = self._connect()
            cur = con.cursor()
            cur.execute("SELECT value FROM cache_meta WHERE key = 'created_at'")
            row = cur.fetchone()
            if not row:
                con.close()
                self.logger.info("Cache not found, will run full analysis")
                return False
            created_at = datetime.fromisoformat(row[0])
            age_minutes = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
            if age_minutes > max_age_minutes:
                con.close()
                self.logger.info(f"Cache is {age_minutes:.0f} min old (max: {max_age_minutes}), will run full analysis")
                return False
            cur.execute("SELECT value FROM cache_meta WHERE key = 'rules_hash'")
            row = cur.fetchone()
            if not row or row[0] != rules_hash:
                con.close()
                self.logger.info("Cache rules hash mismatch, will run full analysis")
                return False
            cur.execute("SELECT value FROM cache_meta WHERE key = 'analyzer_hash'")
            row = cur.fetchone()
            if not row or row[0] != self.analyzer_hash:
                con.close()
                self.logger.info("Cache analyzer hash mismatch, will run full analysis")
                return False
            if current_files is not None and not self._sources_unchanged(cur, current_files, base_path):
                con.close()
                return False
            con.close()
            return True
        except Exception:
            self.logger.info("Cache read error, will run full analysis")
            return False

    def _sources_unchanged(self, cur: sqlite3.Cursor,
                           current_files: list[Path],
                           base_path: str | None) -> bool:
        """True if the discovered file set and mtimes still match the cache."""
        cur.execute("SELECT file_path FROM file_paths")
        cached_set = {r[0].replace("\\", "/") for r in cur.fetchall()}

        base = Path(base_path).resolve() if base_path else None
        current_set = set()
        newest_mtime = 0.0
        for p in current_files:
            resolved = p.resolve()
            rel = resolved.relative_to(base) if base and resolved.is_relative_to(base) else resolved
            current_set.add(str(rel).replace("\\", "/"))
            newest_mtime = max(newest_mtime, resolved.stat().st_mtime)

        if current_set != cached_set:
            self.logger.info("Cache file set changed (files added/removed), will run full analysis")
            return False

        cur.execute("SELECT value FROM cache_meta WHERE key = 'newest_mtime'")
        row = cur.fetchone()
        if not row or newest_mtime > float(row[0]):
            self.logger.info("Source files modified since cache, will run full analysis")
            return False
        return True

    def save(self, violations: list[Violation], rules_hash: str,
             languages: list[str], base_path: str,
             file_paths: list[str] | None = None) -> None:
        """Persist violations to the SQLite cache, replacing any previous data."""
        con = self._connect()
        cur = con.cursor()

        cur.execute("DROP TABLE IF EXISTS violations")
        cur.execute("DROP TABLE IF EXISTS file_paths")
        cur.execute("DROP TABLE IF EXISTS cache_meta")

        cur.execute("""
            CREATE TABLE cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                line INTEGER,
                column_num INTEGER,
                line_count INTEGER
            )
        """)
        cur.execute("CREATE INDEX idx_violations_file_path ON violations(file_path)")
        cur.execute("""
            CREATE TABLE file_paths (
                file_path TEXT NOT NULL
            )
        """)

        # Write metadata
        now_utc = datetime.now(timezone.utc).isoformat()
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)", ("created_at", now_utc))
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)", ("rules_hash", rules_hash))
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)",
                    ("analyzer_hash", self.analyzer_hash))
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)", ("languages", ",".join(languages)))
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)", ("base_path", base_path))
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)",
                    ("newest_mtime", repr(self._newest_mtime(base_path, file_paths))))

        # Bulk-insert violations
        rows = [
            (v.file_path, v.rule_name, v.severity.value, v.message,
             v.line, v.column, v.line_count)
            for v in violations
        ]
        cur.executemany(
            "INSERT INTO violations (file_path, rule_name, severity, message, line, column_num, line_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

        # Bulk-insert analyzed file paths
        if file_paths:
            cur.executemany(
                "INSERT INTO file_paths (file_path) VALUES (?)",
                [(fp,) for fp in file_paths],
            )

        con.commit()
        con.close()
        self.logger.info(f"Cache saved to: {self.db_path} ({len(violations)} violation(s))")

    def load_for_files(self, file_paths: Iterable[str]) -> list[Violation]:
        """Load violations whose file_path matches any of `file_paths`.

        Matching is forward-slash-normalized and accepts either exact equality
        or suffix match (handles absolute-vs-relative path differences).
        """
        normalized = [p.replace("\\", "/") for p in file_paths]
        if not normalized:
            return []
        if not self.db_path.exists():
            return []
        try:
            con = self._connect()
            cur = con.cursor()

            clauses = []
            params: list[str] = []
            for norm in normalized:
                clauses.append("REPLACE(file_path, '\\', '/') = ?")
                params.append(norm)
                clauses.append("REPLACE(file_path, '\\', '/') LIKE ?")
                params.append(f"%/{norm}")
            where = " OR ".join(clauses)
            cur.execute(
                "SELECT file_path, rule_name, severity, message, line, column_num, line_count "
                f"FROM violations WHERE {where}",
                params,
            )
            rows = cur.fetchall()
            con.close()
            return [self._row_to_violation(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def load_all_with_paths(self) -> tuple[list[Violation], list[str]]:
        """Load all violations and analyzed file paths from the cache."""
        if not self.db_path.exists():
            return ([], [])
        try:
            con = self._connect()
            cur = con.cursor()
            cur.execute(
                "SELECT file_path, rule_name, severity, message, line, column_num, line_count "
                "FROM violations"
            )
            violations = [self._row_to_violation(r) for r in cur.fetchall()]
            cur.execute("SELECT file_path FROM file_paths")
            file_paths = [r[0] for r in cur.fetchall()]
            con.close()
            return (violations, file_paths)
        except sqlite3.OperationalError:
            return ([], [])

    def load_all(self) -> list[Violation]:
        """Load every violation from the cache."""
        if not self.db_path.exists():
            return []
        try:
            con = self._connect()
            cur = con.cursor()
            cur.execute(
                "SELECT file_path, rule_name, severity, message, line, column_num, line_count "
                "FROM violations"
            )
            rows = cur.fetchall()
            con.close()
            return [self._row_to_violation(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _newest_mtime(base_path: str, file_paths: list[str] | None) -> float:
        """Max st_mtime over `file_paths` (relative to `base_path`); 0.0 if none."""
        newest = 0.0
        for fp in file_paths or []:
            p = Path(fp)
            if not p.is_absolute():
                p = Path(base_path) / p
            with suppress(OSError):
                newest = max(newest, p.stat().st_mtime)
        return newest

    @staticmethod
    def compute_rules_hash(rules_file: str) -> str:
        """Compute SHA-256 hash of a rules file."""
        with open(rules_file, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    @staticmethod
    def _row_to_violation(row: tuple) -> Violation:
        severity_map = {"ERROR": Severity.ERROR, "WARNING": Severity.WARNING, "INFO": Severity.INFO}
        return Violation(
            file_path=row[0],
            rule_name=row[1],
            severity=severity_map.get(row[2], Severity.WARNING),
            message=row[3],
            line=row[4],
            column=row[5],
            line_count=row[6],
        )
