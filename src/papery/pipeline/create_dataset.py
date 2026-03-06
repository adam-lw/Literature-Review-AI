from pathlib import Path
from typing import Any
from papery.core.api.semantic_scholar import bulk_collect_papers
from papery.pipeline.utils import parse_pipeline_args
from papery.core.utils import save_dict, load_dict, get_project_root, deep_merge
from papery.core.db import load_table, save_table
from datetime import datetime
import os
import asyncio
from papery.core.db import get_inspector
import uuid

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

    coroutines = [
        bulk_collect_papers(
            query=query,
            table_save_path=config.get("table_save_path", "public.papers_dataset"),
            research_fields=config.get("research_fields", []),
            return_fields=config.get("return_fields", []),
            sort_by=config.get("sort_by", None),
            ascending=config.get("ascending", False),
            publication_types=config.get("publication_types", []),
            years=config.get("years", None),
            n_results=config.get("results_per_query", 1000),
            open_access_only=config.get("open_access_only", True),
            min_citation_count=config.get("min_citation_count", 3),
        )
        for query in query_list
    ]

    # Run all queries and save to specified table path
    results = await asyncio.gather(
        *coroutines, return_exceptions=config.get("agent_mode", False)
    )

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
    results_path = f"{artifact_path}/dataset_pipeline_log.txt"
    with open(results_path, "w") as f:
        for result in results:
            f.write(f"{result}\n")

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
