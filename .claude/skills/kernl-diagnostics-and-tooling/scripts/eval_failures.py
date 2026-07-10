#!/usr/bin/env python3
"""
eval_failures.py -- triage eval-harness failures by CLASS, not by vibes.

Usage:
    python eval_failures.py <path-to-eval-results.json>

Accepts either committed artifact shape:
  - backend/tests/eval_results_baseline.json  ({...summary..., "results": [...]})
  - backend/tests/eval_results_partial.json   ({"completed", "total", "results": [...]})
  - or a bare JSON list of scenario records.

Failure taxonomy (strict_pass=False records only):
  label-collapse : relaxed_pass=True  -- the right decision was reachable
                   (raw text / candidate set contained it) but the canonical
                   action_type label was wrong. Fixing labels, not knowledge.
  over-ambiguity : relaxed_pass=False AND actual_action_type == "ambiguous"
                   while a definite action was expected -- the resolver
                   declared a tie instead of deciding.
  wrong-decision : a definite action came out, and it was the wrong one.
  error          : actual_action_type == "error" (exception during the run).

Entropy note: committed eval records do NOT carry the resolver entropy
(the harness saves a flattened trace). This script prints entropy when a
record has it (constraint_result.entropy or a top-level entropy key) and
"n/a" otherwise. Stdlib only; no network.
"""

import argparse
import json
import sys
from collections import Counter, OrderedDict


def load_results(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        summary = {k: v for k, v in data.items() if k != "results"}
        return data["results"], summary
    sys.exit("ERROR: unrecognized eval results shape (no 'results' list)")


def family(scenario_id):
    """REF-01 -> REF, ENG-ADV-01 -> ENG-ADV, DET-03 -> DET."""
    parts = str(scenario_id).rsplit("-", 1)
    return parts[0] if len(parts) == 2 else str(scenario_id)


def get_entropy(rec):
    cr = rec.get("constraint_result") or {}
    for candidate in (cr.get("entropy"), rec.get("entropy")):
        if isinstance(candidate, (int, float)):
            return "%.3f" % candidate
    return "n/a"


def classify(rec):
    if rec.get("actual_action_type") == "error":
        return "error"
    if rec.get("relaxed_pass"):
        return "label-collapse"
    if (rec.get("actual_action_type") == "ambiguous"
            and rec.get("expected_action") != "ambiguous"):
        return "over-ambiguity"
    return "wrong-decision"


def main():
    ap = argparse.ArgumentParser(description="kernl eval failure triage")
    ap.add_argument("results_json", help="path to eval results JSON")
    args = ap.parse_args()

    results, summary = load_results(args.results_json)
    total = len(results)
    strict = sum(1 for r in results if r.get("strict_pass"))
    relaxed = sum(1 for r in results if r.get("relaxed_pass"))

    print("=" * 72)
    print("  EVAL FAILURE TRIAGE: %s" % args.results_json)
    if summary.get("run_timestamp"):
        print("  run_timestamp=%s  company=%s"
              % (summary.get("run_timestamp"), summary.get("company_id")))
    print("  scenarios=%d  strict_pass=%d (%.1f%%)  relaxed_pass=%d (%.1f%%)"
          % (total, strict, 100.0 * strict / max(total, 1),
             relaxed, 100.0 * relaxed / max(total, 1)))
    print("=" * 72)

    failures = [r for r in results if not r.get("strict_pass")]
    classes = OrderedDict(
        (name, [r for r in failures if classify(r) == name])
        for name in ("label-collapse", "over-ambiguity", "wrong-decision",
                     "error"))

    print("\nSTRICT FAILURES: %d" % len(failures))
    for name, recs in classes.items():
        print("  %-15s: %d" % (name, len(recs)))

    fam_counts = Counter(family(r.get("id")) for r in failures)
    fam_totals = Counter(family(r.get("id")) for r in results)
    print("\nFAILURES BY FAMILY:")
    print("  %-12s %10s %8s" % ("family", "failed", "of"))
    for fam, n in fam_counts.most_common():
        print("  %-12s %10d %8d" % (fam, n, fam_totals[fam]))

    for name, recs in classes.items():
        if not recs:
            continue
        print("\n%s (%d):" % (name.upper(), len(recs)))
        for r in recs:
            trace = r.get("retrieval_trace") or {}
            print("  [%s] expected=%-12s got_type=%-12s final_score=%s "
                  "entropy=%s"
                  % (r.get("id"), r.get("expected_action"),
                     r.get("actual_action_type"),
                     trace.get("final_score", r.get("top_retrieval_score")),
                     get_entropy(r)))
            got = (r.get("actual_action") or "").replace("\n", " ")
            print("        got: %s" % got[:110])

    print("\nHint: label-collapse -> normalization/alias problem "
          "(see eval harness check_action_* fns), over-ambiguity -> resolver "
          "tie-breaking (entropy/score_diff thresholds), wrong-decision -> "
          "retrieval or brain content. Deep-dive one ID with trace_summary.py.")


if __name__ == "__main__":
    main()
