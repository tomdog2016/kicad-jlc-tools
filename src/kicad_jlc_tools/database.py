"""FTS5 SQLite database for JLC/LCSC component search and download."""

from __future__ import annotations

import os
import re
import sqlite3
import urllib.request
from pathlib import Path
from zipfile import ZipFile

from .exceptions import DatabaseDownloadError, DatabaseNotFoundError
from .models import MatchResult

_DB_URL_BASE = "https://bouni.github.io/kicad-jlcpcb-tools/"
_CHUNK_COUNT_URL = _DB_URL_BASE + "chunk_num_fts5.txt"
_CHUNK_STUB = "parts-fts5.db.zip."
_DB_FILENAME = "parts-fts5.db"


def _default_db_dir() -> Path:
    """Return the default directory for the database."""
    p = Path.home() / ".kicad-jlc-tools"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default_db_path() -> Path:
    return _default_db_dir() / _DB_FILENAME


def _build_match(query_str: str) -> str:
    keywords = [f'"{w}"' for w in query_str.split() if w.strip()]
    return " AND ".join(keywords)


class JLCDatabase:
    """Manages the JLC/LCSC FTS5 SQLite database for component search."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize with an explicit path or auto-discover.

        Search order:
          1. Explicit db_path
          2. CWD / parts-fts5.db
          3. ~/.kicad-jlc-tools/parts-fts5.db
        """
        if db_path is not None:
            self._path = Path(db_path)
        elif Path(_DB_FILENAME).exists():
            self._path = Path(_DB_FILENAME).resolve()
        else:
            self._path = _default_db_path()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def is_available(self) -> bool:
        return self._path.exists() and self._path.stat().st_size > 0

    @property
    def db_size_mb(self) -> float:
        if not self.is_available:
            return 0.0
        return self._path.stat().st_size / (1024 * 1024)

    def search(
        self, value: str, footprint: str, limit: int = 1
    ) -> list[MatchResult]:
        """Multi-pass FTS5 search: value+footprint -> value -> value tokens.

        Returns a list of MatchResult (up to *limit*).
        """
        if not self.is_available:
            return []

        fp = footprint.split(":")[-1].replace("_", " ").strip()
        queries: list[str] = []

        # Pass 1: Value + first segment of footprint
        fp_first = re.split(r"[-_\s]", fp)[0] if fp else ""
        if fp_first:
            queries.append(f"{value} {fp_first}")

        # Pass 2: Value as-is
        queries.append(value)

        # Pass 3: Value tokens (only if multi-word)
        if " " in value.strip():
            queries.append(value)

        sql = (
            'SELECT "LCSC Part", "Stock", "MFR.Part", "Manufacturer", "Description", "Package" '
            'FROM parts WHERE parts MATCH ? '
            'ORDER BY CAST("Stock" AS INTEGER) DESC LIMIT ?'
        )

        results: list[MatchResult] = []
        try:
            with sqlite3.connect(self._path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                for pass_num, q in enumerate(queries, 1):
                    q = q.strip()
                    if not q:
                        continue
                    match_str = _build_match(q)
                    try:
                        cur.execute(sql, (match_str, limit))
                        rows = cur.fetchall()
                        for row in rows:
                            if row["LCSC Part"] and row["LCSC Part"].startswith("C"):
                                results.append(
                                    MatchResult(
                                        lcsc=row["LCSC Part"],
                                        stock=row["Stock"] or "",
                                        manufacturer=row["Manufacturer"] or "",
                                        part_number=row["MFR.Part"] or "",
                                        description=row["Description"] or "",
                                        package=row["Package"] or "",
                                        match_pass=pass_num,
                                    )
                                )
                        if results:
                            return results[:limit]
                    except sqlite3.OperationalError:
                        continue
        except Exception:
            pass
        return results

    def fetch_details(self, lcsc_code: str) -> MatchResult | None:
        """Fetch full details for a known LCSC part number."""
        if not self.is_available or not lcsc_code:
            return None

        sql = (
            'SELECT "LCSC Part", "Stock", "MFR.Part", "Manufacturer", '
            '"Description", "Package", "First Category", "Second Category" '
            'FROM parts WHERE "LCSC Part" = ? LIMIT 1'
        )
        try:
            with sqlite3.connect(self._path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(sql, (lcsc_code.strip(),))
                row = cur.fetchone()
                if row:
                    return MatchResult(
                        lcsc=row["LCSC Part"],
                        stock=row["Stock"] or "",
                        manufacturer=row["Manufacturer"] or "",
                        part_number=row["MFR.Part"] or "",
                        description=row["Description"] or "",
                        package=row["Package"] or "",
                    )
        except Exception:
            pass
        return None

    @staticmethod
    def download(
        target: Path | str | None = None,
        progress_callback=None,
    ) -> Path:
        """Download the FTS5 database from bouni.github.io/kicad-jlcpcb-tools/.

        Args:
            target: Directory to store the database. Defaults to ~/.kicad-jlc-tools/.
            progress_callback: Called as progress_callback(chunk, total) for each chunk.

        Returns:
            Path to the extracted database file.

        Raises:
            DatabaseDownloadError: On download or extraction failure.
        """
        target_dir = Path(target) if target else _default_db_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        # Get chunk count
        try:
            req = urllib.request.Request(
                _CHUNK_COUNT_URL, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                total_chunks = int(resp.read().decode().strip())
        except Exception as e:
            raise DatabaseDownloadError(f"Failed to get chunk count: {e}") from e

        # Download chunks
        for i in range(1, total_chunks + 1):
            chunk_name = f"{_CHUNK_STUB}{i:03d}"
            chunk_url = _DB_URL_BASE + chunk_name
            chunk_path = target_dir / chunk_name

            if not chunk_path.exists():
                try:
                    req = urllib.request.Request(
                        chunk_url, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp, \
                         open(chunk_path, "wb") as out:
                        out.write(resp.read())
                except Exception as e:
                    raise DatabaseDownloadError(
                        f"Failed to download {chunk_name}: {e}"
                    ) from e

            if progress_callback:
                progress_callback(i, total_chunks)

        # Merge chunks
        merged_zip = target_dir / "parts-fts5.db.zip"
        with open(merged_zip, "wb") as db:
            for i in range(1, total_chunks + 1):
                chunk_path = target_dir / f"{_CHUNK_STUB}{i:03d}"
                with open(chunk_path, "rb") as f:
                    while data := f.read(1024 * 1024):
                        db.write(data)

        # Extract
        db_path = target_dir / _DB_FILENAME
        try:
            with ZipFile(merged_zip, "r") as zf:
                info = zf.infolist()[0]
                with zf.open(info) as src, open(db_path, "wb") as dst:
                    while chunk := src.read(1024 * 1024):
                        dst.write(chunk)
        except Exception as e:
            raise DatabaseDownloadError(f"Failed to extract database: {e}") from e

        # Cleanup
        for i in range(1, total_chunks + 1):
            p = target_dir / f"{_CHUNK_STUB}{i:03d}"
            if p.exists():
                p.unlink()
        if merged_zip.exists():
            merged_zip.unlink()

        return db_path
