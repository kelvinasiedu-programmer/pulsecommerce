"""Bootstrap helper for zero-config deployments.

Used by:
  * Docker image build (as part of `RUN python -m pulsecommerce.cli all`)
  * Streamlit Cloud cold-start (via dashboard/Home.py)
  * Manual: `python scripts/bootstrap.py [--full]`

Default uses the small dataset for a ~30-second cold start; pass `--full`
for the production-scale dataset.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from pulsecommerce.cli import main  # noqa: E402


def bootstrap(full: bool = False, seed: int = 42) -> None:
    args = ["all", "--seed", str(seed)]
    if not full:
        args.append("--small")
    main(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="use the full 25k-user dataset")
    parser.add_argument("--seed", type=int, default=42)
    ns = parser.parse_args()
    bootstrap(full=ns.full, seed=ns.seed)
