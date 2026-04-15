"""PulseCommerce command-line interface.

Commands:
  pulsecommerce generate            # synthesize raw dataset
  pulsecommerce warehouse           # build DuckDB warehouse
  pulsecommerce pipeline            # run all 5 analytical layers
  pulsecommerce all                 # generate + warehouse + pipeline
  pulsecommerce version
"""

from __future__ import annotations

import argparse
import sys

from pulsecommerce._version import __version__
from pulsecommerce.config import DATA_GEN, SmallDataGenConfig
from pulsecommerce.data.generator import generate_and_write
from pulsecommerce.logging_utils import get_logger
from pulsecommerce.pipeline import run_pipeline
from pulsecommerce.warehouse import Warehouse

logger = get_logger("pulsecommerce.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pulsecommerce", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate synthetic dataset")
    g.add_argument("--seed", type=int, default=42)
    g.add_argument("--small", action="store_true", help="use a small CI-friendly dataset")

    sub.add_parser("warehouse", help="build DuckDB warehouse from raw parquet")
    sub.add_parser("pipeline", help="run all 5 analytical layers")

    a = sub.add_parser("all", help="generate + warehouse + pipeline")
    a.add_argument("--seed", type=int, default=42)
    a.add_argument("--small", action="store_true")

    sub.add_parser("version", help="print version")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"pulsecommerce {__version__}")
        return 0

    if args.command in ("generate", "all"):
        cfg = SmallDataGenConfig() if args.small else DATA_GEN
        generate_and_write(cfg=cfg, seed=args.seed)

    if args.command in ("warehouse", "all"):
        with Warehouse() as wh:
            wh.build()

    if args.command in ("pipeline", "all"):
        run_pipeline()

    logger.info("done")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
