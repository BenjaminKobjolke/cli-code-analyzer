"""
SQLite-based violation cache for fast --file queries.

The cache stores analyzer results so that subsequent --file queries
can filter from cached data instead of re-running all analyzers.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from logger import Logger
from models import Severity, Violation


class ViolationCache:
    """Read/write violation cache backed by SQLite."""

    def __init__(self, db_path: Path, logger: Logger | None = None):
        self.db_path = db_path
        self.logger = logger or Logger()

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

    def is_valid(self, max_age_minutes: int, rules_hash: str) -> bool:
        """Check whether the cache exists, is fresh, and matches the rules hash."""
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
            con.close()
            if not row or row[0] != rules_hash:
                self.logger.info("Cache rules hash mismatch, will run full analysis")
                return False
            return True
        except Exception:
            self.logger.info("Cache read error, will run full analysis")
            return False

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
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)", ("languages", ",".join(languages)))
        cur.execute("INSERT INTO cache_meta VALUES (?, ?)", ("base_path", base_path))

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

    def load_for_file(self, file_path: str) -> list[Violation]:
        """Load violations matching a specific file path from the cache."""
        if not self.db_path.exists():
            return []
        try:
            con = self._connect()
            cur = con.cursor()

            # Normalise to forward slashes for comparison
            norm = file_path.replace("\\", "/")
            cur.execute(
                "SELECT file_path, rule_name, severity, message, line, column_num, line_count "
                "FROM violations WHERE REPLACE(file_path, '\\', '/') = ? "
                "   OR REPLACE(file_path, '\\', '/') LIKE ?",
                (norm, f"%/{norm}"),
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
