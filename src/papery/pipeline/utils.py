import argparse


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
