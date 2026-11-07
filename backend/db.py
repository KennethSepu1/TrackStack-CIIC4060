import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a database connection for one transaction."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")

    with psycopg.connect(database_url, connect_timeout=5) as connection:
        yield connection