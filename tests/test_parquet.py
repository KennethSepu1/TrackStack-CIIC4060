"""Tests for Parquet reading and the inspect command."""

import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ETL.parquet import inspect_dataset, read_batches

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase1_official_dataset"
COUNTS = {
    "fuel_type": 2, "vehicle_kind": 5, "vehicle_status": 2, "driver": 12,
    "vehicle_type": 8, "vehicle": 30, "parking_area": 224, "road_segment": 4086,
    "vehicle_assignment": 42, "location_ping": 28041, "trip": 300,
}


def test_official_row_counts():
    assert inspect_dataset(DATA) == COUNTS


def test_read_all_official_files_in_batches():
    for table, expected in COUNTS.items():
        path = DATA / f"{table}.parquet"
        batches = list(read_batches(path, batch_size=257))
        assert all(0 < batch.num_rows <= 257 for batch in batches)
        assert sum(batch.num_rows for batch in batches) == expected
        assert pa.Table.from_batches(batches).equals(pq.read_table(path))


def test_preserve_nulls_geometry_text_and_timestamp_precision(tmp_path):
    source = pa.table({
        "geom": ["0101000020E610000026C396C313CA50C0967BDC12143C3240", None],
        "ts": pa.array([1, None], type=pa.timestamp("ns")),
        "speed_kph": pa.array([0.25, None], type=pa.float64()),
    })
    path = tmp_path / "sample.parquet"
    pq.write_table(source, path)
    actual = pa.Table.from_batches(list(read_batches(path, batch_size=1)))
    assert actual.equals(source)


@pytest.mark.parametrize("batch_size", [0, -1])
def test_reject_invalid_batch_size(batch_size):
    with pytest.raises(ValueError, match="batch_size must be positive"):
        list(read_batches(DATA / "driver.parquet", batch_size))


@pytest.mark.parametrize("change", ["missing", "extra", "repeated"])
def test_reject_incorrect_columns(tmp_path, change):
    # fuel_type is the first file inspected; later files are not needed here.
    source = pq.read_table(DATA / "fuel_type.parquet")
    if change == "missing":
        source = source.drop(["name"])
    elif change == "extra":
        source = source.append_column("extra", pa.array([1, 2]))
    else:
        source = source.rename_columns(["name", "name"])
    pq.write_table(source, tmp_path / "fuel_type.parquet")
    with pytest.raises(ValueError, match="fuel_type: columns"):
        inspect_dataset(tmp_path)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_dataset(tmp_path)


def test_inspect_command():
    result = subprocess.run(
        [sys.executable, "-m", "ETL", "inspect"], cwd=ROOT,
        text=True, capture_output=True, check=True,
    )
    assert json.loads(result.stdout) == COUNTS
    assert result.stderr == ""


def test_inspect_command_reports_file_error(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "ETL", "inspect", "--data-dir", str(tmp_path)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "Inspection failed:" in result.stderr
    assert "fuel_type.parquet" in result.stderr
