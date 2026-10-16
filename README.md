# Car Tracking Phase I

Python ETL for CIIC 4060 / ICOM 5016. This first stage reads the 11 official Parquet files and checks their column names. Database loading will be added next.

## Setup

Use Python 3.11 or later. Run these commands from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

## Inspect the dataset

```sh
python -m ETL inspect
```

The command prints each table's row count as JSON. It reports an error if a required file is missing or its columns differ from the project diagram. To use another dataset directory:

```sh
python -m ETL inspect --data-dir /path/to/dataset
```

`ETL/parquet.py` also provides `read_batches()` for reading files in batches of up to 10,000 rows. It keeps the original values and Arrow types, including NULLs, timestamps, and EWKB geometry strings. This stage does not convert geometry or connect to a database.

## Tests

```sh
python -m pytest -q
```

The tests check the official row counts, batch reading, value preservation, column checks, and command-line errors. Test files are written only to temporary directories; the official dataset is not modified.
