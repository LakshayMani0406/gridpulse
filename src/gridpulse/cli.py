"""gridpulse command-line interface."""
from __future__ import annotations

import argparse
import json
import sys

from .config import WAREHOUSE_BACKEND, load_config, setup_logging
from .storage import Warehouse


def _print_result(res) -> None:
    print(f"\nBackend: {WAREHOUSE_BACKEND} | synthetic: {res.synthetic}")
    if res.n_rows:
        print("warehouse rows:", json.dumps(res.n_rows))
    print("\nSiting ranking (lowest marginal carbon first):")
    cols = ["ba", "mef_kg_per_mwh", "aef_kg_per_mwh", "rank_shift"]
    print(res.siting[cols].head(12).to_string(index=False))
    if not res.inversions.empty:
        print(f"\nRank inversions (avg-based analysis gets these wrong): "
              f"{', '.join(res.inversions['ba'])}")
    print(f"\nReport: {res.report_path}")
    print("Figures:", ", ".join(res.figures) if res.figures else "(matplotlib not installed)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gridpulse", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run-offline", help="run on the synthetic fixture (no key needed)")

    rn = sub.add_parser("run-now", help="live run if EIA_API_KEY present, else offline")
    rn.add_argument("--months", type=int, default=None)
    rn.add_argument("--load-mw", type=float, default=100.0)

    bf = sub.add_parser("backfill", help="incremental live backfill into the warehouse")
    bf.add_argument("--months", type=int, default=None)
    bf.add_argument("--bas", nargs="*", default=None)

    sub.add_parser("status", help="show warehouse manifest / watermarks")

    va = sub.add_parser("validate", help="cross-check computed AEF vs EIA published CO2")
    va.add_argument("--bas", nargs="*", default=None)
    va.add_argument("--months", type=int, default=6)

    pb = sub.add_parser("phaseb", help="consumption-based re-ranking + actual-vs-optimal siting gap")
    pb.add_argument("--new-mw", type=float, default=10000.0)

    fc = sub.add_parser("forecast", help="demand backtest, with vs without weather features")
    fc.add_argument("--ba", default="ERCO")
    fc.add_argument("--folds", type=int, default=12)

    args = p.parse_args(argv)
    cfg = load_config()
    setup_logging(cfg.log_level)

    if args.cmd == "run-offline":
        from .pipeline import run_offline
        _print_result(run_offline(cfg))
    elif args.cmd == "run-now":
        from .pipeline import run_now
        _print_result(run_now(cfg, months=args.months, load_mw=args.load_mw))
    elif args.cmd == "backfill":
        from .pipeline import incremental_pull
        wh = Warehouse(cfg)
        counts = incremental_pull(cfg, wh, months=args.months, bas=args.bas)
        print("upserted:", json.dumps(counts, indent=2))
    elif args.cmd == "status":
        wh = Warehouse(cfg)
        man = wh.load_manifest()
        print(f"backend: {wh.backend}")
        print(json.dumps(man, indent=2) if man else "(empty warehouse)")
    elif args.cmd == "validate":
        from .validate import run_validation
        agree = run_validation(cfg, bas=args.bas, months=args.months)
        if not agree.empty:
            print(agree.to_string(index=False))
    elif args.cmd == "phaseb":
        from .phaseb import run_phaseb
        out = run_phaseb(cfg, total_new_mw=args.new_mw)
        print("\nConsumption-based ranking (lowest first):")
        cols = ["ba", "aef", "prod_mef", "cons_mef", "rank_aef", "rank_cons_mef", "rerank_aef_to_cons"]
        print(out["ranking"][cols].to_string(index=False))
        if out["gap"]:
            print("\nActual vs optimal siting gap:", json.dumps(out["gap"], indent=2, default=str))
    elif args.cmd == "forecast":
        from .forecasting import run_forecast_comparison
        run_forecast_comparison(cfg, ba=args.ba, n_folds=args.folds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
