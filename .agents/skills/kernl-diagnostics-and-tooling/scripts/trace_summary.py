#!/usr/bin/env python3
"""
trace_summary.py -- pretty-print ONE eval scenario's full record for a deep dive.

Usage:
    python trace_summary.py <path-to-eval-results.json> <scenario-id>
    python trace_summary.py <path-to-eval-results.json> --list

Accepts both committed artifact shapes (baseline summary dict with "results",
partial {"completed","total","results"}) and a bare list of records. Prints
every field the record carries, including nested retrieval_trace (flat eval
shape OR the runtime shape with "components"/"matched_conditions") and, if
present, constraint_result with reasoning_steps / condition_trace /
precedence_trace. Stdlib only; no network.
"""

import argparse
import json
import sys


def load_results(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        return data["results"]
    sys.exit("ERROR: unrecognized eval results shape (no 'results' list)")


def pp(value, indent=0, key=None):
    pad = "  " * indent
    label = "%s%s" % (pad, key + ": " if key else "")
    if isinstance(value, dict):
        print("%s" % label.rstrip(": ") + ":" if key else pad.rstrip())
        for k, v in value.items():
            pp(v, indent + 1, k)
    elif isinstance(value, list):
        if not value:
            print("%s[]" % label)
        elif all(not isinstance(v, (dict, list)) for v in value):
            print("%s" % label.rstrip(": ") + ":")
            for v in value:
                print("%s  - %s" % (pad, v))
        else:
            print("%s" % label.rstrip(": ") + ":")
            for i, v in enumerate(value):
                pp(v, indent + 1, "[%d]" % i)
    else:
        print("%s%s" % (label, value))


def main():
    ap = argparse.ArgumentParser(description="kernl per-scenario trace viewer")
    ap.add_argument("results_json", help="path to eval results JSON")
    ap.add_argument("scenario_id", nargs="?",
                    help="scenario id, e.g. REF-01 (case-insensitive)")
    ap.add_argument("--list", action="store_true",
                    help="list all scenario ids with pass flags and exit")
    args = ap.parse_args()

    results = load_results(args.results_json)

    if args.list or not args.scenario_id:
        print("%-14s %-8s %-8s %-12s -> %s"
              % ("id", "strict", "relaxed", "got_type", "expected"))
        for r in results:
            print("%-14s %-8s %-8s %-12s -> %s"
                  % (r.get("id"), r.get("strict_pass"), r.get("relaxed_pass"),
                     r.get("actual_action_type"), r.get("expected_action")))
        return

    wanted = args.scenario_id.lower()
    rec = next((r for r in results
                if str(r.get("id", "")).lower() == wanted), None)
    if rec is None:
        sys.exit("ERROR: scenario id %r not found. Run with --list to see ids."
                 % args.scenario_id)

    print("=" * 72)
    print("  SCENARIO %s  (strict=%s, relaxed=%s, rule=%s)"
          % (rec.get("id"), rec.get("strict_pass"), rec.get("relaxed_pass"),
             rec.get("rule_pass")))
    print("=" * 72)

    # Scalars first, in a stable and readable order; then nested blocks.
    scalar_order = [
        "source", "scenario", "expected_action", "actual_action_type",
        "actual_action", "expected_rule_fragment", "actual_rule",
        "top_retrieval_score", "confidence", "skill_matched",
        "reasoning_snippet",
    ]
    for k in scalar_order:
        if k in rec:
            pp(rec[k], 0, k)
    printed = set(scalar_order) | {"id", "strict_pass", "relaxed_pass",
                                   "rule_pass"}
    for k, v in rec.items():
        if k in printed:
            continue
        print()
        pp(v, 0, k)


if __name__ == "__main__":
    main()
