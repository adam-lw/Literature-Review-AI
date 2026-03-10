import asyncio
from papery.core.utils import get_project_root, deep_merge, load_dict
from papery.pipeline.utils import parse_pipeline_args
from papery.core.db import load_table, get_inspector, execute_query, save_table
from papery.core.api.semantic_scholar import collect_specter_embeddings
from datetime import datetime
from typing import Literal, Any

from loguru import logger


pipelines: Literal["specter", "generic"]


def specter_embeddings_pipeline(config: dict[str, Any], artifact_path: str):
    papers_df = load_table(config.get("papers_table"))  # type: ignore
    ids = papers_df["paperId"].tolist()

    table_save_path = config.get("table_save_path")

    if not table_save_path:
        raise ValueError("Table save path not set.")

    inspector = get_inspector()
    if inspector.has_table(
        table_save_path.split(".")[1], table_save_path.split(".")[0]
    ):
        if config.get("overwrite_table", False):
            logger.warning(f"Deleting {table_save_path}")
            execute_query(f"DROP TABLE {table_save_path};")
        else:
            raise ValueError(f"Table {table_save_path} already exists.")

    execute_query(
        f"CREATE TABLE IF NOT EXISTS {table_save_path} "
        f'("paperId" TEXT PRIMARY KEY, {config["embedding"]} VECTOR({config["embedding_ndim"]}));'
    )

    async def stream_embeddings():
        async for resp in collect_specter_embeddings(ids, config["embedding"]):
            # Process and save response
            print(resp)
            print(resp.dtypes)
            save_table(
                resp,
                table_save_path,
                if_exists="append",
                embedding_cols=[config["embedding"]],
            )
            logger.info("Saved data!")

    asyncio.run(stream_embeddings())


if __name__ == "__main__":
    DEFAULT_CONFIG = get_project_root() / "config/pipelines/generate_embeddings.yaml"

    args = parse_pipeline_args()

    if args.config:
        config = load_dict(args.config)
    else:
        config = load_dict(DEFAULT_CONFIG)

    if args.overrides:
        for override_path in args.override:
            override_config = load_dict(override_path)
            config = deep_merge(config, override_config)

    artifact_path = str(
        get_project_root()
        / "artifacts"
        / f"dataset_pipeline_{datetime.now().strftime('%d%m%Y_%H%M%S')}"
    )

    pipeline = config.get("pipeline", "specter")
    if pipeline == "specter":
        specter_embeddings_pipeline(config=config, artifact_path=artifact_path)
    else:
        raise ValueError(f"Unknown pipeline: {pipeline}")
