"""Summarize the agent-loop audit trail (output/audit_trail.json).

    .venv/bin/python audit_report.py            # summary of every logged chat message
    .venv/bin/python audit_report.py --last 3   # also print the last 3 messages step by step
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict

from audit import AUDIT_PATH


def main(last: int) -> None:
    if not AUDIT_PATH.exists():
        print(f"No audit trail yet at {AUDIT_PATH}")
        return
    entries = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    turns: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        turns[e["turn_id"]].append(e)
    ends = [steps[-1] for steps in turns.values()]

    print(f"{len(entries)} agent-loop steps across {len(turns)} chat messages  ({AUDIT_PATH})")
    print("How runs ended: " + ", ".join(
        f"{reason} {n}" for reason, n in Counter(
            "answered" if e["ended_run"] and not (e["stop_reason"] or "").startswith(("error", "content_filter"))
            else (e["stop_reason"] or "?").split(":")[0]
            for e in ends
        ).most_common()))
    print("Steps per message: " + ", ".join(f"{k} steps: {v}" for k, v in sorted(Counter(len(s) for s in turns.values()).items())))
    latencies = sorted(e["turn_latency_ms"] / 1000 for e in ends if e.get("turn_latency_ms") is not None)
    if latencies:
        print(f"Time per message: median {statistics.median(latencies):.1f}s, max {latencies[-1]:.1f}s")
    tools = Counter(c["tool_name"] for e in entries for c in e["tool_calls"] if c["tool_name"] != "final_result")
    print("Tool calls: " + (", ".join(f"{t} {n}" for t, n in tools.most_common()) or "none"))
    retries = sum(1 for e in entries for c in e["tool_calls"] if (c.get("result") or "").startswith("retry:"))
    print(f"Retries (fact-check or bad tool arguments): {retries}")
    print(f"Tokens: {sum(e['input_tokens'] for e in entries)} in, {sum(e['output_tokens'] for e in entries)} out")

    for turn_id in list(turns)[-last:] if last else []:
        steps = turns[turn_id]
        first = steps[0]
        print(f"\n[{first['timestamp']}] {turn_id} {first['endpoint']} user={first['user_id']} page={first['page_path']}")
        print(f"  shopper: {first['message']}")
        for e in steps:
            end = " (ended run)" if e["ended_run"] else ""
            print(f"  step {e['step']}: stop_reason={e['stop_reason']}{end}")
            for c in e["tool_calls"]:
                print(f"    {c['tool_name']}({c['args'] if c['tool_name'] != 'final_result' else '…'}) -> {c['result']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--last", type=int, default=0, help="also print the last N chat messages step by step")
    main(parser.parse_args().last)
