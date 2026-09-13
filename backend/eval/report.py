"""In bảng terminal + xuất JSON. Không phụ thuộc lib ngoài."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from eval.runner import CaseResult

_RESULTS = Path(__file__).parent / "results"


def _cost(c: float | None) -> str:
    return f"${c:.5f}" if c is not None else "—"


def _tok(u) -> str:
    return str(u.total_tokens) if u else "—"


def print_model_table(name: str, results: list[CaseResult]) -> None:
    print(f"\n━━ {name} ━━")
    print(f"{'case':<20} {'kết quả':<7} {'step':>4} {'tool':>4} {'tok':>7} {'$':>9} {'ms':>6}")
    for r in results:
        verdict = "PASS" if r.passed else ("ERROR" if r.error else "FAIL")
        print(
            f"{r.case_id:<20} {verdict:<7} {r.steps:>4} {r.tool_calls:>4} "
            f"{_tok(r.usage):>7} {_cost(r.cost_usd):>9} {r.latency_ms:>6.0f}"
        )
        if r.error:
            print(f"    ! {r.error}")
        for c in r.checks:
            if not c.ok:
                mark = "~ (soft)" if c.soft else "✗"
                print(f"    {mark} {c.type}: {c.detail}")
    n = len(results)
    npass = sum(1 for r in results if r.passed)
    nsoft = sum(1 for r in results if r.passed and r.soft_fails)
    tail = f" ({nsoft} có soft-fail)" if nsoft else ""
    print(f"{'─' * 58}\n   {npass}/{n} pass{tail}")


def print_comparison(by_model: dict[str, list[CaseResult]]) -> list[dict]:
    print("\n━━ SO SÁNH MODEL ━━")
    print(f"{'model':<16} {'pass':>8} {'avg $':>10} {'p95 ms':>8} {'avg tok':>9}")
    rows: list[dict] = []
    for name, results in by_model.items():
        n = len(results)
        npass = sum(1 for r in results if r.passed)
        costs = [r.cost_usd for r in results if r.cost_usd is not None]
        toks = [r.usage.total_tokens for r in results if r.usage]
        lat = sorted(r.latency_ms for r in results)
        p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else 0.0
        avg_cost = sum(costs) / len(costs) if costs else None
        avg_tok = round(sum(toks) / len(toks)) if toks else 0
        rows.append(
            {"model": name, "pass_rate": round(npass / n, 3), "passed": npass, "total": n,
             "avg_cost_usd": avg_cost, "p95_latency_ms": round(p95), "avg_tokens": avg_tok}
        )
        print(f"{name:<16} {f'{npass}/{n}':>8} {_cost(avg_cost):>10} {p95:>8.0f} {avg_tok:>9}")
    return rows


def _result_dict(r: CaseResult) -> dict:
    return {
        "case": r.case_id,
        "pass": r.passed,
        "error": r.error,
        "steps": r.steps,
        "tool_calls": r.tool_calls,
        "tokens": r.usage.total_tokens if r.usage else None,
        "cost_usd": r.cost_usd,
        "latency_ms": round(r.latency_ms),
        "soft_fails": [c.type for c in r.soft_fails],
        "checks": [
            {"type": c.type, "ok": c.ok, "soft": c.soft, "detail": c.detail} for c in r.checks
        ],
    }


def write_json(by_model: dict[str, list[CaseResult]], comparison: list[dict]) -> Path:
    _RESULTS.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
    data = {
        "run_at": stamp,
        "comparison": comparison,
        "results": {name: [_result_dict(r) for r in rs] for name, rs in by_model.items()},
    }
    path = _RESULTS / f"{stamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return path
