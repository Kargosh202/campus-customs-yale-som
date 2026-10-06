"""Measure reply speed and correctness at different reasoning efforts.

    .venv/bin/python benchmark.py                      # high, medium, low
    .venv/bin/python benchmark.py --efforts high medium

Runs each question below through run_chat() as a logged-out shopper (nothing is saved to the
database), checks the reply against facts from the database, and prints latency, tokens,
tool calls, and fact-check retries per effort. Results are also written to logs/benchmark-*.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from agent import run_chat
from models import AgentResult, ChatDeps, ViewedProduct
import db


def viewed(product_id: str) -> ViewedProduct:
    p = db.get_product(product_id)
    assert p, product_id
    return ViewedProduct(p.product_id, p.name, p.garment_type, p.colors, p.description)


@dataclass
class Case:
    question: str
    check: Callable[[AgentResult], bool]
    expect: str
    product_id: str | None = None


def has(*needles: str) -> Callable[[AgentResult], bool]:
    return lambda r: all(n.lower() in r.reply.lower() for n in needles)


CASES = [
    Case("what hoodies do you have?", has("27", "$45.00", "$88.00"), "27 hoodies, $45.00 to $88.00"),
    Case("is this in stock in large?", has("out of stock"), "L is out of stock", "yale-grandpa-hoodie"),
    Case("do you have this in pink?", has("navy", "white"), "no; navy and white", "baseball-left-chest-crewneck"),
    Case("how much is the Yale Mom Hoodie and how many are left in XXL?", has("$68.00", "2"), "$68.00, 2 left in XXL"),
    Case("what's the cheapest thing you sell?", has("$32.00"), "T-shirts at $32.00"),
    Case("anything with handsome dan on it?", lambda r: "bulldog" in r.reply.lower() and len(r.products) > 0, "bulldog items with cards"),
]


async def run_effort(effort: str) -> list[dict]:
    rows = []
    for case in CASES:
        deps = ChatDeps(viewed_product=viewed(case.product_id) if case.product_id else None,
                        page_path=f"/products/{case.product_id}" if case.product_id else "/")
        started = time.perf_counter()
        try:
            result = await run_chat(case.question, [], deps, reasoning_effort=effort)
            t = result.trace
            rows.append({
                "effort": effort, "question": case.question, "correct": case.check(result), "expect": case.expect,
                "seconds": round(time.perf_counter() - started, 1), "tool_calls": len(t.tool_calls),
                "model_requests": t.model_requests, "fact_check_retries": len(t.fact_check_retries),
                "input_tokens": t.input_tokens, "output_tokens": t.output_tokens, "reply": result.reply,
            })
        except Exception as exc:
            rows.append({"effort": effort, "question": case.question, "correct": False, "expect": case.expect,
                         "seconds": round(time.perf_counter() - started, 1), "error": f"{type(exc).__name__}: {exc}"[:200]})
        r = rows[-1]
        print(f"  [{effort:6}] {'PASS' if r['correct'] else 'FAIL'} {r['seconds']:5.1f}s  {case.question}")
    return rows


async def main(efforts: list[str]) -> None:
    all_rows = []
    for effort in efforts:
        print(f"\nReasoning effort: {effort}")
        all_rows += await run_effort(effort)

    print(f"\n{'effort':8} {'correct':>8} {'median s':>9} {'mean s':>7} {'max s':>6} {'out tok':>8} {'retries':>8}")
    for effort in efforts:
        rows = [r for r in all_rows if r["effort"] == effort]
        secs = [r["seconds"] for r in rows]
        out_tokens = [r.get("output_tokens", 0) for r in rows]
        print(f"{effort:8} {sum(r['correct'] for r in rows):>4}/{len(rows):<3} {statistics.median(secs):>9.1f} "
              f"{statistics.mean(secs):>7.1f} {max(secs):>6.1f} {statistics.mean(out_tokens):>8.0f} "
              f"{sum(r.get('fact_check_retries', 0) for r in rows):>8}")

    out = Path(__file__).resolve().parent / "logs" / f"benchmark-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(all_rows, indent=2))
    print(f"\nDetails: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--efforts", nargs="+", default=["high", "medium", "low"])
    asyncio.run(main(parser.parse_args().efforts))
