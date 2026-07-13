#!/usr/bin/env python3
"""
brain_audit.py -- compiled-brain quality gate for kernl.

Usage:
    python brain_audit.py <path-to-brain.json>

Reads a compiled brain JSON (the shape saved as
backend/tests/last_compiled_brain.json: {skills, graph_json, metadata_json,
meta}) and prints the quality signals that predict eval behaviour BEFORE you
spend GPU time on an eval run:

  - skill count + per-skill condition count, conditions_confidence,
    which skills lose their conditions at retrieval time (confidence gate)
  - per-skill metadata_confidence fields below the trust threshold
  - specificity_level distribution (a single level = specificity bonus is a no-op)
  - graph stats: entities / edges / policies / authority rules,
    effect distribution, policies that are effect=approve with NO conditions
  - authority naming inconsistencies between graph authority_rules and
    metadata authority_levels (incl. role_-prefixed duplicates)

Stdlib only. No network, no LLM, no DB. Exit code 0 always (report tool).
"""

import argparse
import json
import sys
from collections import Counter

# Mirrors DEFAULT thresholds in backend/runtime/brain_agent.py (_MD) --
# only used when metadata_json.thresholds is absent from the brain file.
FALLBACK_METADATA_CONF = 0.60
FALLBACK_CONDITIONS_CONF = 0.60

TRUSTED_META_FIELDS = (
    "department",
    "severity",
    "action_type",
    "workflow_type",
    "customer_tier",
)


def load_brain(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        sys.exit("ERROR: expected a JSON object at top level")
    # Tolerate a bare skills list or partial shapes.
    if "skills" not in data and isinstance(data.get("results"), list):
        sys.exit("ERROR: this looks like an eval results file, not a brain. "
                 "Use eval_failures.py / trace_summary.py for eval artifacts.")
    return data


def audit(path):
    brain = load_brain(path)
    skills = brain.get("skills") or []
    graph = brain.get("graph_json") or {}
    md = brain.get("metadata_json") or {}
    meta = brain.get("meta") or {}
    th = md.get("thresholds") or {}
    meta_conf_th = th.get("metadata_confidence", FALLBACK_METADATA_CONF)
    cond_conf_th = th.get("conditions_confidence", FALLBACK_CONDITIONS_CONF)

    warns = []

    print("=" * 72)
    print("  BRAIN AUDIT: %s" % path)
    if meta:
        print("  company=%s  compiled_at=%s  duration_ms=%s"
              % (meta.get("company_id"), meta.get("compiled_at"),
                 meta.get("duration_ms")))
    print("=" * 72)

    # -- Skills ----------------------------------------------------------
    print("\nSKILLS: %d total" % len(skills))
    print("  thresholds: metadata_confidence>=%.2f  conditions_confidence>=%.2f"
          % (meta_conf_th, cond_conf_th))
    print("  %-36s %5s %8s %6s  %s"
          % ("id", "conds", "cond_cf", "conf", "flags"))
    dropped_conditions = 0
    for s in skills:
        sid = s.get("id", "?")
        conds = s.get("conditions") or []
        cc = s.get("conditions_confidence", 0.5)
        conf = s.get("confidence", "?")
        flags = []
        if cc < cond_conf_th:
            flags.append("conditions DROPPED at retrieval (cond_cf<%.2f)"
                         % cond_conf_th)
            if conds:
                dropped_conditions += 1
        mc = s.get("metadata_confidence") or {}
        low_meta = [f for f in TRUSTED_META_FIELDS
                    if mc.get(f, 0.5) < meta_conf_th]
        if low_meta:
            flags.append("untrusted metadata: %s" % ",".join(low_meta))
        print("  %-36s %5d %8s %6s  %s"
              % (sid, len(conds), cc, conf, "; ".join(flags)))
    no_cond = sum(1 for s in skills if not (s.get("conditions") or []))
    if no_cond:
        warns.append("%d/%d skills have ZERO typed conditions -- condition_score "
                     "can never fire for them" % (no_cond, len(skills)))
    if dropped_conditions:
        warns.append("%d skills HAVE conditions but conditions_confidence < %.2f "
                     "-- retrieval silently ignores them" %
                     (dropped_conditions, cond_conf_th))

    # -- Specificity -----------------------------------------------------
    spec = Counter((s.get("operational") or {}).get("specificity_level")
                   for s in skills)
    print("\nSPECIFICITY DISTRIBUTION: %s" % dict(sorted(
        spec.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    if len(spec) == 1:
        warns.append("all skills share ONE specificity_level -- the specificity "
                     "bonus and 'Specificity level N preferred' trace text are "
                     "meaningless discriminators")

    # -- Graph -----------------------------------------------------------
    entities = graph.get("entities") or {}
    edges = graph.get("edges") or []
    policies = graph.get("policies") or {}
    if isinstance(policies, dict):
        policy_list = list(policies.values())
    else:
        policy_list = list(policies)
    auth_rules = graph.get("authority_rules") or {}
    stats = graph.get("stats") or {}
    print("\nGRAPH: %d entities, %d edges, %d policies, %d authority rules"
          % (len(entities), len(edges), len(policy_list), len(auth_rules)))
    if stats:
        print("  compiler stats: %s" % stats)
    effects = Counter(p.get("effect") for p in policy_list)
    print("  effect distribution: %s" % dict(effects))
    approve_no_cond = sum(1 for p in policy_list
                          if p.get("effect") == "approve"
                          and not (p.get("conditions") or []))
    print("  policies with effect=approve AND empty conditions: %d/%d"
          % (approve_no_cond, len(policy_list)))
    if policy_list and approve_no_cond == len(policy_list):
        warns.append("EVERY graph policy is effect=approve with no conditions -- "
                     "the graph path can only ever answer 'approve' and never "
                     "condition-filters anything")
    elif policy_list and approve_no_cond > len(policy_list) // 2:
        warns.append("%d/%d graph policies are effect=approve with no conditions"
                     % (approve_no_cond, len(policy_list)))
    has_policy_edges = sum(1 for e in edges
                           if e.get("relation_type") == "has_policy")
    if len(policy_list) and has_policy_edges < len(policy_list):
        warns.append("only %d has_policy edges for %d policies -- unreachable "
                     "policies can never be retrieved via the graph"
                     % (has_policy_edges, len(policy_list)))

    # -- Authority naming consistency ------------------------------------
    auth_levels = md.get("authority_levels") or {}
    print("\nAUTHORITY NAMING:")
    print("  graph authority_rules roles : %s" % sorted(auth_rules.keys()))
    print("  metadata authority_levels   : %s" % sorted(auth_levels.keys()))
    missing = sorted(r for r in auth_rules if r not in auth_levels)
    if missing:
        warns.append("authority_rules roles missing from metadata "
                     "authority_levels: %s (they fall back to default level 1)"
                     % missing)
    prefixed_dupes = sorted(
        k for k in auth_levels
        if k.startswith("role_") and k[len("role_"):] in auth_levels)
    if prefixed_dupes:
        warns.append("authority_levels mixes naming schemes -- role_-prefixed "
                     "duplicates: %s" % prefixed_dupes)
    orphan_prefixed = sorted(
        k for k in auth_levels
        if k.startswith("role_") and k[len("role_"):] not in auth_levels)
    if orphan_prefixed:
        print("  note: role_-prefixed names with no unprefixed twin: %s"
              % orphan_prefixed)

    # -- Verdict ---------------------------------------------------------
    print("\n" + "-" * 72)
    if warns:
        print("WARNINGS (%d):" % len(warns))
        for w in warns:
            print("  [WARN] %s" % w)
    else:
        print("No warnings. Brain looks structurally healthy.")
    print("-" * 72)


def main():
    ap = argparse.ArgumentParser(description="kernl compiled-brain quality gate")
    ap.add_argument("brain_json", help="path to compiled brain JSON "
                    "(e.g. backend/tests/last_compiled_brain.json)")
    args = ap.parse_args()
    audit(args.brain_json)


if __name__ == "__main__":
    main()
