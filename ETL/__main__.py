"""Inspect the official Parquet dataset from the command line."""

import argparse
import json
import sys
from pathlib import Path

import pyarrow as pa

from ETL.parquet import inspect_dataset


def main() -> int:
    """Print row counts as JSON; return 1 if a file cannot be inspected."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect",))
    parser.add_argument("--data-dir", type=Path, default=Path("phase1_official_dataset"))
    args = parser.parse_args()
    try:
        counts = inspect_dataset(args.data_dir)
    except (OSError, ValueError, pa.ArrowInvalid, pa.ArrowNotImplementedError) as exc:
        print(f"Inspection failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
