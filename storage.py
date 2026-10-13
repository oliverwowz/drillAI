"""DrillAI Data Storage.

SQLite-based persistent storage for analysis results and history.
Uses parameterized queries and automatic schema management.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("drillai.storage")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    screenshot_hash TEXT,
    question_text TEXT,
    question_type TEXT,
    options_json TEXT,
    proposed_answer TEXT,
    answer_text TEXT,
    explanation TEXT,
    confidence REAL,
    needs_review INTEGER DEFAULT 1,
    warnings_json TEXT,
    model TEXT,
    processing_time REAL,
    validation_status TEXT DEFAULT 'unverified',
    error_info TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON analysis_results(timestamp);
CREATE INDEX IF NOT EXISTS idx_screenshot_hash ON analysis_results(screenshot_hash);
"""


class StorageError(Exception):
    """Storage operation error."""
    pass


class AnalysisStorage:
    """SQLite storage for DrillAI analysis results.
    
    Provides CRUD operations with automatic schema management.
    Uses parameterized queries to prevent SQL injection.
    Never stores API keys or full screenshots by default.
    """
    
    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.cwd() / "results" / "drillai.db"
        
        self.db_path = Path(db_path)
        self._ensure_directory()
        self._init_db()
    
    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Cannot create database directory: {e}") from e
    
    def _init_db(self) -> None:
        """Initialize the database and create tables."""
        try:
            with self._connect() as conn:
                conn.executescript(CREATE_TABLE_SQL)
                logger.debug(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            raise StorageError(f"Database initialization failed: {e}") from e
    
    def _connect(self) -> sqlite3.Connection:
        """Create a database connection."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except sqlite3.Error as e:
            raise StorageError(f"Database connection failed: {e}") from e
    
    def save_result(
        self,
        result: Dict[str, Any],
        screenshot_hash: Optional[str] = None,
    ) -> int:
        """Save an analysis result to the database.
        
        Args:
            result: Analysis result dict from SolverResult.to_dict().
            screenshot_hash: Optional hash for duplicate detection.
            
        Returns:
            Row ID of the inserted record.
            
        Raises:
            StorageError: If save fails.
        """
        # Check for duplicates based on screenshot hash
        if screenshot_hash:
            existing = self.find_by_hash(screenshot_hash)
            if existing:
                logger.debug(f"Duplicate result for hash {screenshot_hash[:8]}, skipping")
                return existing[0]["id"]
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO analysis_results (
                        timestamp, screenshot_hash, question_text, question_type,
                        options_json, proposed_answer, answer_text, explanation,
                        confidence, needs_review, warnings_json, model,
                        processing_time, validation_status, error_info, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp,
                        screenshot_hash or "",
                        result.get("question_text", ""),
                        result.get("question_type", "unknown"),
                        json.dumps(result.get("options", {}), ensure_ascii=False),
                        result.get("proposed_answer", ""),
                        result.get("answer_text", ""),
                        result.get("explanation", ""),
                        float(result.get("confidence", 0.0) or 0.0),
                        1 if result.get("needs_review", True) else 0,
                        json.dumps(result.get("warnings", []), ensure_ascii=False),
                        result.get("model", ""),
                        float(result.get("processing_time", 0.0) or 0.0),
                        result.get("validation_status", "unverified"),
                        result.get("error_info", ""),
                        time.time(),
                    ),
                )
                conn.commit()
                row_id = cursor.lastrowid
                logger.info(f"Result saved (id={row_id})")
                return row_id or 0
                
        except sqlite3.Error as e:
            raise StorageError(f"Failed to save result: {e}") from e
    
    def find_by_hash(self, screenshot_hash: str) -> List[Dict[str, Any]]:
        """Find results by screenshot hash.
        
        Args:
            screenshot_hash: Hash to search for.
            
        Returns:
            List of matching result dicts.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM analysis_results WHERE screenshot_hash = ? ORDER BY created_at DESC",
                    (screenshot_hash,),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Hash lookup failed: {e}")
            return []
    
    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get the most recent analysis results.
        
        Args:
            limit: Maximum number of results to return.
            
        Returns:
            List of result dicts, newest first.
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM analysis_results ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to get recent results: {e}")
            return []
    
    def get_count(self) -> int:
        """Get total number of stored results."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM analysis_results"
                ).fetchone()
                return row["count"] if row else 0
        except sqlite3.Error as e:
            logger.error(f"Failed to get count: {e}")
            return 0
    
    def format_results(self, results: List[Dict[str, Any]]) -> str:
        """Format results for terminal display."""
        if not results:
            return "No results found."
        
        lines = [f"Found {len(results)} result(s):"]
        lines.append("-" * 60)
        
        for r in results:
            lines.append(f"ID: {r.get('id', '?')} | {r.get('timestamp', '?')}")
            lines.append(f"  Q: {str(r.get('question_text', 'N/A'))[:80]}")
            lines.append(f"  A: {r.get('proposed_answer', 'N/A')} ({float(r.get('confidence', 0) or 0):.0%})")
            lines.append(f"  Model: {r.get('model', 'N/A')}")
            lines.append("-" * 60)
        
        return "\n".join(lines)
    
    def close(self) -> None:
        """Close storage resources."""
        logger.debug("Storage closed")
