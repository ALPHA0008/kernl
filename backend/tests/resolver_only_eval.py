"""
resolver_only_eval.py
─────────────────────
Evaluates the constraint resolver against all 40 scenarios from eval_harness.py
WITHOUT calling the LLM. Tests only the retrieval + constraint resolution pipeline.

Usage: python -m backend.tests.resolver_only_eval
"""

import json
import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

from backend.tests.eval_harness import SCENARIOS
from backend.runtime.brain_agent import (
    _load_skills_from_file,
    _extract_query_signals,
    _compute_hybrid_score,
    _build_admissible_actions,
    RETRIEVAL_WEIGHTS,
)
from backend.core.llm import get_embedding
from backend.runtime.constraint_resolver import resolve as constraint_resolve


def _make_noop_graph_result() -> dict:
    return {
        "success": False,
        "graph_confidence": 0.0,
        "policies": [],
        "condition_results": [],
        "precedence_edges": [],
    }


def evaluate_scenario(scenario: dict) -> dict:
    brain_data, err = _load_skills_from_file()
    if err:
        return {"id": scenario["id"], "error": err}

    skills = brain_data.get("skills", [])
    if not skills:
        return {"id": scenario["id"], "error": "Brain is empty — no skills compiled."}

    graph = brain_data.get("graph_json", {})

    query_text = f"{scenario['scenario']} {json.dumps(scenario.get('context', {}))}"

    try:
        query_emb = get_embedding(query_text)
    except Exception as e:
        return {"id": scenario["id"], "error": f"Embedding failed: {e}"}

    query_signals = _extract_query_signals(
        scenario["scenario"], scenario.get("context")
    )
    w = RETRIEVAL_WEIGHTS

    cached = all("embedding_vector" in s for s in skills)
    if cached:
        skill_embs = np.array([s["embedding_vector"] for s in skills])
        query_vec = np.array(query_emb)
        norms = np.linalg.norm(skill_embs, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-10
        sem_scores = (np.dot(skill_embs, query_vec) / norms).tolist()
    else:
        sem_scores = []
        for skill in skills:
            skill_text = " ".join(
                filter(
                    None,
                    [
                        skill.get("category", ""),
                        skill.get("rule", ""),
                        skill.get("rationale", ""),
                    ],
                )
            )
            try:
                skill_emb = get_embedding(skill_text)
            except Exception:
                sem_scores.append(0.0)
                continue
            sem_scores.append(
                float(
                    np.dot(query_emb, skill_emb)
                    / (np.linalg.norm(query_emb) * np.linalg.norm(skill_emb) + 1e-10)
                )
            )

    scored = []
    for i, (skill, sem_sim) in enumerate(zip(skills, sem_scores)):
        final_score, components = _compute_hybrid_score(
            sem_sim, skill, query_signals, w
        )
        scored.append(
            {
                "skill": skill,
                "score": final_score,
                "components": components,
                "index": i,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:5]

    admissible_actions, candidate_entropy = _build_admissible_actions(
        top_results, query_signals
    )

    graph_result = _make_noop_graph_result()

    constraint_result = constraint_resolve(
        graph_result=graph_result,
        skill_admissible=admissible_actions,
        context=scenario.get("context", {}),
        query_signals=query_signals,
        authority_rules=graph.get("authority_rules", {}),
        requester_role=(scenario.get("context", {}) or {}).get("requested_by"),
    )

    return {
        "id": scenario["id"],
        "expected_action": scenario["expected_action"],
        "constraint_result": constraint_result,
        "all_candidates": admissible_actions,
        "candidate_entropy": candidate_entropy,
        "top_scores": [
            (s["skill"].get("id"), round(s["score"], 4)) for s in top_results
        ],
    }


def run():
    print("=" * 80)
    print("  CONSTRAINT RESOLVER EVAL (no LLM)")
    print(f"  Scenarios: {len(SCENARIOS)}")
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")
    print("=" * 80)

    results = []
    strict_passed = 0
    total = 0

    for i, s in enumerate(SCENARIOS):
        sid = s["id"]
        print(f"\n[{i + 1:02d}/{len(SCENARIOS)}] {sid}")

        result = evaluate_scenario(s)

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            results.append(result)
            continue

        total += 1
        cr = result["constraint_result"]
        primary = cr.primary_action
        is_ambiguous = cr.is_ambiguous
        actual_action = primary.action_type if primary else "ambiguous"

        expected = result["expected_action"]
        if expected == "ambiguous":
            strict_pass = is_ambiguous
        else:
            strict_pass = actual_action == expected

        if strict_pass:
            strict_passed += 1

        print(f"  Expected    : {expected}")
        print(
            f"  Actual      : {actual_action}{' (ambiguous)' if is_ambiguous else ''}"
        )
        print(f"  Pass        : {'YES' if strict_pass else 'NO'}")
        print(f"  Entropy     : {cr.entropy:.4f}")
        print(f"  Source      : {cr.resolution_source}")
        if not is_ambiguous and primary:
            print(f"  Confidence  : {primary.confidence:.4f}")
            print(f"  Escalation  : {cr.escalation_required} -> {cr.escalation_target}")
        print(f"  Candidates  :")
        for a in cr.all_admissible_actions:
            print(f"    - {a.action_type} (conf={a.confidence:.4f}, src={a.source})")
        if result.get("top_scores"):
            scores_str = ", ".join(
                f"{id_}={sc}" for id_, sc in result["top_scores"][:3]
            )
            print(f"  Top skills  : {scores_str}")

        results.append(
            {
                "id": sid,
                "expected_action": expected,
                "actual_action": actual_action,
                "is_ambiguous": is_ambiguous,
                "pass": strict_pass,
                "entropy": round(cr.entropy, 4),
                "resolution_source": cr.resolution_source,
                "primary_confidence": round(primary.confidence, 4) if primary else None,
                "all_admissible": [
                    {
                        "action": a.action_type,
                        "confidence": round(a.confidence, 4),
                        "source": a.source,
                    }
                    for a in cr.all_admissible_actions
                ],
            }
        )

    errors = len(SCENARIOS) - total
    accuracy = (strict_passed / total * 100) if total else 0

    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"  Total       : {total}")
    print(f"  Errors      : {errors}")
    print(f"  Strict Pass : {strict_passed}/{total} ({accuracy:.1f}%)")
    print("=" * 80)

    out_path = os.path.join(os.path.dirname(__file__), "resolver_eval_results.json")
    with open(out_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "total_scenarios": total,
                "strict_passed": strict_passed,
                "accuracy_pct": round(accuracy, 1),
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nResults saved -> {out_path}")


if __name__ == "__main__":
    run()
