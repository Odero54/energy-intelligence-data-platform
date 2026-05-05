"""CLI runner for data ingestion pipelines.

Usage:
    uv run python scripts/run_ingestion.py world-bank
    uv run python scripts/run_ingestion.py power-plants
    uv run python scripts/run_ingestion.py admin-boundaries
    uv run python scripts/run_ingestion.py all
    uv run python scripts/run_ingestion.py all --dry-run
"""

import argparse
import importlib

from dotenv import load_dotenv

load_dotenv()

PIPELINES: dict[str, str] = {
    "world-bank": "ingestion.world_bank.pipeline",
    "power-plants": "ingestion.power_plants.pipeline",
    "admin-boundaries": "ingestion.admin_boundaries.pipeline",
}


def run_pipeline(name: str, dry_run: bool) -> None:
    print(f"\n{'=' * 60}")
    print(f"  Pipeline: {name}")
    print("=" * 60)
    mod = importlib.import_module(PIPELINES[name])
    mod.run(dry_run=dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run data ingestion pipelines")
    parser.add_argument("pipeline", choices=[*PIPELINES, "all"])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and transform only — skip Snowflake load",
    )
    args = parser.parse_args()

    targets = list(PIPELINES) if args.pipeline == "all" else [args.pipeline]
    for name in targets:
        run_pipeline(name, dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
