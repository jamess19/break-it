"""python -m eval [--model NAME|all] [--case ID]

Seed task giả vào DB (TEST_POSTGRES_DSN, default = POSTGRES_DSN), cho agent xếp
lịch, chấm bằng eval/scorers.py. Xuất bảng + eval/results/<timestamp>.json.

CẢNH BÁO: dùng chung DB `ops_agent` → eval TRUNCATE tasks/plans/facts.
"""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path

import yaml

from eval.loader import load_cases
from eval.report import print_comparison, print_model_table, write_json
from eval.runner import run_suite

_DIR = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m eval")
    ap.add_argument("--model", default="all", help="tên model trong models.yaml, hoặc 'all'")
    ap.add_argument("--case", help="chỉ chạy 1 case theo id")
    ap.add_argument("--gap", type=float, default=3.0, help="giây nghỉ giữa các case (né rate-limit)")
    args = ap.parse_args()

    models = yaml.safe_load((_DIR / "models.yaml").read_text())
    if args.model != "all":
        models = [m for m in models if m["name"] == args.model]
        if not models:
            raise SystemExit(f"không thấy model '{args.model}' trong eval/models.yaml")

    cases = load_cases(_DIR / "cases" / "planning.yaml")
    if args.case:
        cases = [c for c in cases if c.id == args.case]
        if not cases:
            raise SystemExit(f"không thấy case '{args.case}'")

    by_model: dict = {}
    for i, m in enumerate(models):
        if i:
            time.sleep(args.gap * 2)  # nghỉ dài hơn giữa các model
        print(f"\n▶ chạy {len(cases)} case với {m['name']} ({m['model']})…")
        by_model[m["name"]] = asyncio.run(run_suite(cases, m, gap_seconds=args.gap))
        print_model_table(m["name"], by_model[m["name"]])

    comparison = print_comparison(by_model) if len(by_model) > 1 else []
    path = write_json(by_model, comparison)
    print(f"\n→ {path.relative_to(Path.cwd())}")


main()
