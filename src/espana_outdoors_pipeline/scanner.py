from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable

SUPPORTED_EXTENSIONS = {
    ".gpx": "gpx",
    ".kml": "kml",
    ".kmz": "kmz",
    ".geojson": "geojson",
    ".geojsonl": "geojsonl",
    ".osm": "osm",
    ".osm.pbf": "osm.pbf",
    ".pbf": "pbf",
    ".pmtiles": "pmtiles",
    ".mbtiles": "mbtiles",
}

CHUNK_SIZE = 4 * 1024 * 1024
SCHEMA_VERSION = 1


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    relative_path TEXT NOT NULL,
    name TEXT NOT NULL,
    extension TEXT NOT NULL,
    format TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    ctime_ns INTEGER NOT NULL,
    sha256 TEXT,
    hash_status TEXT NOT NULL,
    scan_status TEXT NOT NULL,
    error TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_files_format ON files(format);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_files_size ON files(size_bytes);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(scan_status);
"""


def detect_format(path: Path) -> tuple[str, str] | None:
    """Return (extension, logical format) for a supported file."""
    name = path.name.lower()
    if name.endswith(".osm.pbf"):
        return ".osm.pbf", "osm.pbf"
    ext = path.suffix.lower()
    fmt = SUPPORTED_EXTENSIONS.get(ext)
    return (ext, fmt) if fmt else None


def iter_supported_files(root: Path) -> Iterable[Path]:
    """Yield supported files without following directory symlinks."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Do not descend into symlinked directories.
        dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.is_symlink() or not path.is_file():
                continue
            if detect_format(path):
                yield path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def connect_catalog(catalog: Path) -> sqlite3.Connection:
    catalog.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(catalog)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    connection.commit()
    return connection


def get_cached_hash(
    connection: sqlite3.Connection,
    path: str,
    size_bytes: int,
    mtime_ns: int,
) -> str | None:
    row = connection.execute(
        "SELECT sha256 FROM files WHERE path = ? AND size_bytes = ? AND mtime_ns = ? AND hash_status = 'ok'",
        (path, size_bytes, mtime_ns),
    ).fetchone()
    return row[0] if row else None


def upsert_file(
    connection: sqlite3.Connection,
    *,
    root: Path,
    path: Path,
    sha256: str | None,
    hash_status: str,
    scan_status: str,
    error: str | None = None,
) -> None:
    stat = path.stat()
    ext, fmt = detect_format(path) or (path.suffix.lower(), "unknown")
    absolute = str(path.resolve())
    relative = str(path.resolve().relative_to(root.resolve()))
    connection.execute(
        """
        INSERT INTO files(
            path, relative_path, name, extension, format, size_bytes,
            mtime_ns, ctime_ns, sha256, hash_status, scan_status, error,
            last_scanned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(path) DO UPDATE SET
            relative_path=excluded.relative_path,
            name=excluded.name,
            extension=excluded.extension,
            format=excluded.format,
            size_bytes=excluded.size_bytes,
            mtime_ns=excluded.mtime_ns,
            ctime_ns=excluded.ctime_ns,
            sha256=excluded.sha256,
            hash_status=excluded.hash_status,
            scan_status=excluded.scan_status,
            error=excluded.error,
            last_scanned_at=CURRENT_TIMESTAMP
        """,
        (
            absolute,
            relative,
            path.name,
            ext,
            fmt,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
            sha256,
            hash_status,
            scan_status,
            error,
        ),
    )


def scan(root: Path, catalog: Path, *, hash_mode: str = "auto", progress_every: int = 100) -> dict[str, int | float]:
    """Scan supported files below root into a SQLite catalog.

    hash_mode:
      - auto: reuse a hash when path, size and mtime are unchanged.
      - always: recompute SHA-256 for every file.
      - never: collect metadata only.
    """
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Root is not a directory: {root}")

    connection = connect_catalog(catalog)
    started = time.monotonic()
    counts = {"files": 0, "hashed": 0, "reused": 0, "errors": 0, "bytes": 0}

    try:
        for path in iter_supported_files(root):
            counts["files"] += 1
            try:
                stat = path.stat()
                counts["bytes"] += stat.st_size
                absolute = str(path.resolve())
                cached = None if hash_mode == "always" else get_cached_hash(
                    connection, absolute, stat.st_size, stat.st_mtime_ns
                )

                if hash_mode == "never":
                    digest = None
                    hash_status = "skipped"
                elif cached:
                    digest = cached
                    hash_status = "ok"
                    counts["reused"] += 1
                else:
                    digest = sha256_file(path)
                    hash_status = "ok"
                    counts["hashed"] += 1

                upsert_file(
                    connection,
                    root=root,
                    path=path,
                    sha256=digest,
                    hash_status=hash_status,
                    scan_status="ok",
                )
            except (OSError, ValueError) as exc:
                counts["errors"] += 1
                try:
                    upsert_file(
                        connection,
                        root=root,
                        path=path,
                        sha256=None,
                        hash_status="error",
                        scan_status="error",
                        error=str(exc),
                    )
                except OSError:
                    pass

            if counts["files"] % progress_every == 0:
                connection.commit()
                elapsed = max(time.monotonic() - started, 0.001)
                rate = counts["files"] / elapsed
                print(
                    f"[scan] files={counts['files']:,} "
                    f"hashed={counts['hashed']:,} reused={counts['reused']:,} "
                    f"errors={counts['errors']:,} rate={rate:,.1f}/s",
                    flush=True,
                )

        connection.commit()
    finally:
        connection.close()

    counts["seconds"] = round(time.monotonic() - started, 2)
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventory geographic files into a local SQLite catalog without modifying source files."
    )
    parser.add_argument("--root", required=True, type=Path, help="Root directory containing the source corpus")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("data/catalog.sqlite"),
        help="SQLite catalog path (default: data/catalog.sqlite)",
    )
    parser.add_argument(
        "--hash-mode",
        choices=("auto", "always", "never"),
        default="auto",
        help="Hash policy: auto reuses unchanged hashes; always recomputes; never skips hashing",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        metavar="N",
        help="Print progress every N files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.progress_every < 1:
        parser.error("--progress-every must be >= 1")

    try:
        result = scan(
            args.root,
            args.catalog,
            hash_mode=args.hash_mode,
            progress_every=args.progress_every,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("\nScan complete")
    print(f"  files:   {result['files']:,}")
    print(f"  bytes:   {result['bytes']:,}")
    print(f"  hashed:  {result['hashed']:,}")
    print(f"  reused:  {result['reused']:,}")
    print(f"  errors:  {result['errors']:,}")
    print(f"  seconds: {result['seconds']}")
    print(f"  catalog: {args.catalog.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
