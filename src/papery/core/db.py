import os
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv
import pandas as pd
import asyncio
from typing import Literal

if_exists_options = Literal["fail", "replace", "append", "delete_rows"]

load_dotenv()

ENGINE = create_engine(
    f"postgresql+psycopg2://"
    f"{os.getenv('PGUSER')}:"
    f"{os.getenv('PGPASSWORD')}@"
    f"{os.getenv('PGHOST')}:"
    f"{os.getenv('PGPORT')}/"
    f"{os.getenv('PGDATABASE')}",
    pool_size=10,
    max_overflow=20,
)


def execute_query(query: str):
    with ENGINE.begin() as conn:
        return conn.execute(text(query))


# Ensure pgvector is installed at import time
execute_query("CREATE EXTENSION IF NOT EXISTS vector;")


def save_table(
    df: pd.DataFrame,
    table_path: str,
    if_exists: if_exists_options = "fail",
    embedding_cols: list[str] = [],
):
    """Saves a Pandas DataFrame to PostgresSQL based on .env settings."""

    parts = table_path.split(".")
    if len(parts) == 1:
        schema = "public"
        table_name = parts[0]
    elif len(parts) == 2:
        schema, table_name = parts
    else:
        raise ValueError(
            f"Unexpected table_path format {table_path}. Hint: provide path in format `schema.table`"
        )

    if embedding_cols:
        for embedding in embedding_cols:
            # Ensure the vector is a list of floats (not numpy array or object)
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


def load_table(table_path: str) -> pd.DataFrame:
    """Loads a table from PostgreSQL into a Pandas DataFrame based on .env settings."""
    query = f"SELECT * FROM {table_path}"
    return pd.read_sql(query, ENGINE)


def get_inspector():
    return inspect(ENGINE)
