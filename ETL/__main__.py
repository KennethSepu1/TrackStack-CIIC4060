"""Inspect, load, or validate the official Car Tracking dataset."""

import argparse
import json
import os
import sys
from pathlib import Path

import pyarrow as pa
import psycopg

from ETL.database import load_data
from ETL.parquet import inspect_dataset


def main() -> int:
    """Print row counts as JSON; return 1 if the requested operation fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "load", "validate"))
    parser.add_argument("--data-dir", type=Path, default=Path("phase1_official_dataset"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--batch-size", type=int, default=10_000)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            counts = inspect_dataset(args.data_dir)
        else:
            url = os.environ.get("DATABASE_URL")
            if not url:
                raise ValueError("Set DATABASE_URL before loading or validating")
            with psycopg.connect(url, connect_timeout=15) as connection:
                counts = load_data(connection, args.data_dir, schema=args.schema,
                                   batch_size=args.batch_size, validate_only=args.command == "validate")
    except psycopg.Error as exc:
        # Connection errors can contain connection details; print only their type.
        print(f"Database operation failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    except (OSError, ValueError, pa.ArrowInvalid, pa.ArrowNotImplementedError) as exc:
        operation = {"inspect": "Inspection", "load": "Load", "validate": "Validation"}[args.command]
        print(f"{operation} failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
