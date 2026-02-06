#!/usr/bin/env python3
"""
Merge multiple SQLite databases into one.

Used by CI to combine databases from parallel jobs.
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def merge_databases(output_path: Path, input_paths: list[Path]) -> None:
    """Merge multiple databases into one."""
    # Filter to existing files
    existing_inputs = [p for p in input_paths if p.exists()]

    if not existing_inputs:
        logger.error("No input databases found")
        sys.exit(1)

    logger.info(f"Merging {len(existing_inputs)} databases into {output_path}")

    # Initialize output database with schema from first input
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists():
        output_path.unlink()

    # Copy first database as base
    first_db = existing_inputs[0]
    logger.info(f"Using {first_db} as base")

    import shutil

    shutil.copy(first_db, output_path)

    # Merge remaining databases
    conn = sqlite3.connect(output_path)
    conn.execute("PRAGMA foreign_keys = OFF")  # Disable for merge

    for db_path in existing_inputs[1:]:
        logger.info(f"Merging {db_path}")
        conn.execute(f"ATTACH DATABASE '{db_path}' AS source")

        # Get list of tables
        cursor = conn.execute(
            "SELECT name FROM source.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            # Get column names
            cursor = conn.execute(f"PRAGMA source.table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            if not columns:
                continue

            cols_str = ", ".join(columns)

            # Use INSERT OR REPLACE to handle duplicates
            try:
                conn.execute(f"""
                    INSERT OR REPLACE INTO main.{table} ({cols_str})
                    SELECT {cols_str} FROM source.{table}
                """)
                logger.info(f"  Merged table: {table}")
            except sqlite3.Error as e:
                logger.warning(f"  Failed to merge table {table}: {e}")

        conn.execute("DETACH DATABASE source")
        conn.commit()

    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

    logger.info(f"Merge complete: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Merge SQLite databases")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output database path")
    parser.add_argument("inputs", type=Path, nargs="+", help="Input database paths")

    args = parser.parse_args()
    merge_databases(args.output, args.inputs)


if __name__ == "__main__":
    main()
