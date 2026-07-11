import argparse
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from literature_ai.core.data_collect.get_ss_embeddings import collect_embeddings
from literature_ai.core.data_collect.get_ss_papers import collect_papers
from literature_ai.db import check_connection, apply_schema
from literature_ai.core.agent.logging.langfuse import lf_logger
from literature_ai.core.processing.clean_paper import clean_paper
from literature_ai.core.processing.create_index import create_hnsw_index
from literature_ai.core.processing.generate_paper_embeddings import generate_paper_embeddings
from literature_ai.core.utils import deep_merge, get_project_root, load_dict, save_dict, PaperProcessingMetrics


def parse_pipeline_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=False, help="Path to base config file")
    parser.add_argument(
        "--overrides",
        nargs="*",
        default=[],
        help="Paths to override config files, seperated by spaces",
    )
    args = parser.parse_args()
    return args


def run_pipeline(config: dict[str, Any], artifact_path: Path) -> None:
    """
    Pipeline for creating or extending a dataset of papers given a list of queries.
    """
    logger.info("Running run_pipeline...")

    metadata = {
        "uuid": str(uuid.uuid4()),
        "pipeline": "run_pipeline",
        "start_time": datetime.now().isoformat(),
    }

    if not check_connection():
        raise ValueError("Failed to connect to Postgres database. Ensure you have initialised its docker container with `docker compose up -d`")

    apply_schema(Path(__file__).parents[1] / "core" / "service_schema.sql")

    stages = config.get("stages", {})

    if stages.get("collect_papers", True):
        cp_cfg = config.get("collect_papers", {})

        try:
            metrics = collect_papers(
                **cp_cfg,
            )
        except Exception as e:
            metrics = PaperProcessingMetrics()
            logger.exception(f"collect_papers stage failed: {e}")
        # lf_logger.log_api_call(
        #     api_id="run_pipeline",
        #     endpoint="collect_papers",
        #     params=cp_cfg,
        #     response=vars(metrics),
        #     duration_s=time.time() - t0,
        #     error=error,
        # )
        logger.info(f"collect_papers complete: {metrics}")

    if stages.get("clean_paper", False):
        try:
            metrics = clean_paper()
        except Exception as e:
            logger.exception(f"clean_paper stage failed: {e}")
        else:
            logger.info(f"clean_paper complete: {metrics}")

    if stages.get("embeddings", False):
        emb_cfg = config.get("embeddings", {})
        collect_models: list[str] = emb_cfg.get("collect", [])
        generate_models: list[str] = emb_cfg.get("generate", [])
        idx_cfg = emb_cfg.get("index", {})
        auto_index = emb_cfg.get("create_index", False)

        for model in collect_models:
            try:
                run_id = collect_embeddings(embedding=model)
            except Exception as e:
                logger.exception(f"embeddings collect stage failed for model '{model}': {e}")
                continue
            logger.info(f"collect_embeddings complete for '{model}' (run_id={run_id})")
            if run_id is not None and auto_index:
                create_hnsw_index(
                    run_id=run_id,
                    m=idx_cfg.get("m", 16),
                    ef_construction=idx_cfg.get("ef_construction", 64),
                    distance=idx_cfg.get("distance", "cosine"),
                )

        for model in generate_models:
            try:
                run_id = generate_paper_embeddings(embedding_model=model)
            except Exception as e:
                logger.exception(f"embeddings generate stage failed for model '{model}': {e}")
                continue
            logger.info(f"generate_paper_embeddings complete for '{model}' (run_id={run_id})")
            if run_id is not None and auto_index:
                create_hnsw_index(
                    run_id=run_id,
                    m=idx_cfg.get("m", 16),
                    ef_construction=idx_cfg.get("ef_construction", 64),
                    distance=idx_cfg.get("distance", "cosine"),
                )

    # Save results
    os.makedirs(artifact_path, exist_ok=True)

    config_path = f"{artifact_path}/config.yaml"
    save_dict(config, config_path)
    logger.info(f"Saved pipeline config to {config_path}")

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
        for override_path in args.overrides:
            override_config = load_dict(override_path)
            config = deep_merge(config, override_config)

    artifact_path = (
        get_project_root()
        / "artifacts"
        / f"run_pipeline_{datetime.now().strftime('%d%m%Y_%H%M%S')}"
    )

    run_pipeline(config, artifact_path)
