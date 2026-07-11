from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text
import asyncio
from typing import Literal

if_exists_options = Literal["fail", "replace", "append", "delete_rows"]

# instance initialised in docker - run docker-compose.yml
PGUSER = "literature_ai"
PGPASSWORD = "literature_ai"
PGHOST = "localhost"
PGPORT = 5433
PGDATABASE = "literature_ai"

ENGINE = create_engine(
    f"postgresql+psycopg2://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}",
    pool_size=10,
    max_overflow=20,
)


def execute_query(query: str):
    with ENGINE.begin() as conn:
        return conn.execute(text(query))


def _parse_path(table_path: str) -> tuple[str, str]:
    parts = table_path.split(".")
    if len(parts) == 1:
        return "public", parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(
        f"Unexpected table_path format {table_path}. Expected `schema.table` or `table`."
    )


def save_table(
    df: pd.DataFrame,
    table_path: str,
    if_exists: if_exists_options = "fail",
    embedding_cols: list[str] = [],
):
    """Saves a Pandas DataFrame to PostgresSQL based on .env settings."""

    schema, table_name = _parse_path(table_path)

    if embedding_cols:
        for embedding in embedding_cols:
            df[embedding] = df[embedding].apply(
                lambda x: list(map(float, x)) if x is not None else None
            )

    df.to_sql(
        table_name,
        ENGINE,
        schema=schema,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=10_000,
    )


async def save_table_async(
    df: pd.DataFrame, table_path: str, if_exists: if_exists_options = "fail"
):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, save_table, df, table_path, if_exists)


def upsert_table(records: list[dict], table_path: str, conflict_cols: list[str], *, do_update: bool = True) -> int:
    """Upsert records into a PostgreSQL table.

    Requires a UNIQUE or PRIMARY KEY constraint on conflict_cols:
      ALTER TABLE <schema>.<table> ADD UNIQUE (<col>);

    Returns the number of rows actually inserted. When do_update=True all rows are
    considered inserted (conflicts are updated in-place). When do_update=False conflicts
    are skipped and only new rows count toward the return value.
    """
    if not records:
        return 0
    schema, table_name = _parse_path(table_path)
    cols = list(records[0].keys())
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    conflict_list = ", ".join(f'"{c}"' for c in conflict_cols)
    if do_update:
        update_cols = [c for c in cols if c not in conflict_cols]
        updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
        sql = text(
            f'INSERT INTO "{schema}"."{table_name}" ({col_list}) VALUES ({placeholders})'
            f" ON CONFLICT ({conflict_list}) DO UPDATE SET {updates}"
        )
    else:
        sql = text(
            f'INSERT INTO "{schema}"."{table_name}" ({col_list}) VALUES ({placeholders})'
            f" ON CONFLICT ({conflict_list}) DO NOTHING"
        )
    inserted = 0
    with ENGINE.begin() as conn:
        for i in range(0, len(records), 10_000):
            result = conn.execute(sql, records[i : i + 10_000])
            inserted += result.rowcount
    return inserted if not do_update else len(records)


async def upsert_table_async(
    records: list[dict], table_path: str, conflict_cols: list[str], *, do_update: bool = True
) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: upsert_table(records, table_path, conflict_cols, do_update=do_update)
    )


def load_table(table_path: str) -> pd.DataFrame:
    """Loads a table from PostgreSQL into a Pandas DataFrame based on .env settings."""
    query = f"SELECT * FROM {table_path}"
    return pd.read_sql(query, ENGINE)


def check_connection() -> bool:
    """Returns True if the database is reachable, False otherwise."""
    try:
        with ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def apply_schema(schema_path: Path) -> None:
    """Applies a SQL schema file to the database. Safe to run on an existing database (uses IF NOT EXISTS)."""
    sql = schema_path.read_text()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with ENGINE.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def get_inspector():
    return inspect(ENGINE)
