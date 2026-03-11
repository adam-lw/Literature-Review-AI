from pathlib import Path
from typing import Any
from papery.core.api.semantic_scholar import bulk_collect_papers
from papery.pipeline.utils import parse_pipeline_args
from papery.core.utils import save_dict, load_dict, get_project_root, deep_merge
from papery.core.db import load_table, save_table, ENGINE as db_engine
from datetime import datetime
import os
import asyncio
from papery.core.db import get_inspector
import uuid
import math

from loguru import logger


async def dataset_pipeline(config: dict[str, Any], artifact_path: Path) -> None:
    """
    Pipeline for creating or extending a dataset of papers given a list of queries.
    """
    logger.info("Running dataset_pipeline...")

    metadata = {
        "uuid": uuid.uuid4(),
        "pipeline": "dataset_pipeline",
        "start_time": datetime.now().isoformat(),
    }

    query_list = config["query_list"]

    table_save_path = config.get("table_save_path", None)
    if not table_save_path:
        raise ValueError("table_save_path must be specified in the config.")

    inspector = get_inspector()

    if not inspector.has_schema(str(table_save_path).split(".")[0]):
        raise ValueError(
            f"Schema {table_save_path.split('.')[0]} does not exist. Please create the schema before running the pipeline."
        )

    if not inspector.has_table(
        table_save_path.split(".")[-1], schema=table_save_path.split(".")[0]
    ) and not config.get("overwrite_table", False):
        raise ValueError(
            f"Table {table_save_path} already exists. Set `overwrite_table` to True in the config to overwrite it."
        )

    async def gather_query_results(
        query: str, n_papers: int, collection_config: dict[str, Any]
    ):
        n_collections = math.ceil(n_papers / 1000)
        counter = 0
        async for resp in bulk_collect_papers(query=query, **collection_config):
            resp.to_sql(
                table_save_path,
                db_engine,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=10_000,
            )
            counter += 1
            if counter >= n_collections:
                break

    # Set collection config
    collection_config = {
        k: v
        for k, v in config.items()
        if k in [
            "research_fields",
            "return_fields",
            "sort_by",
            "ascending",
            "publication_types",
            "years",
            "open_access_only",
            "min_citation_count",
        ]
    }

    query_coroutines = [
        gather_query_results(
            query, config.get("results_per_query", 10000), collection_config
        )
        for query in query_list
    ]

    await asyncio.gather(*query_coroutines)

    # Deduplicate data
    df = load_table(config.get("table_save_path", "public.papers_dataset"))

    logger.info(f"Len before deduplication: {len(df)}")
    df = df.drop_duplicates(subset=["paperId"])
    logger.info(f"Len after deduplication: {len(df)}")
    save_table(
        df, config.get("table_save_path", "public.papers_dataset"), if_exists="replace"
    )

    # Save results
    os.makedirs(artifact_path, exist_ok=True)

    # Save pipeline config
    config_path = f"{artifact_path}/config.yaml"
    save_dict(config, config_path)

    logger.info(f"Saved pipeline config to {config_path}")

    # Save metadata
    metadata_path = f"{artifact_path}/metadata.yaml"
    save_dict(metadata, metadata_path)


if __name__ == "__main__":
    DEFAULT_CONFIG = get_project_root() / "config/pipelines/create_dataset.yaml"

    args = parse_pipeline_args()

    if args.config:
        config = load_dict(args.config)
    else:
        config = load_dict(DEFAULT_CONFIG)

    if args.overrides:
        for override_path in args.override:
            override_config = load_dict(override_path)
            config = deep_merge(config, override_config)

    artifact_path = (
        get_project_root()
        / "artifacts"
        / f"dataset_pipeline_{datetime.now().strftime('%d%m%Y_%H%M%S')}"
    )

    asyncio.run(dataset_pipeline(config, artifact_path))
