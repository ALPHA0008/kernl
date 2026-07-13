import json, re, math, numpy as np
from backend.core.db.supabase import get_client
from backend.core.llm import llm_call, get_embedding
from backend.runtime.graph_retriever import retrieve_from_graph
from backend.runtime.constraint_resolver import resolve as constraint_resolve
from backend.runtime.guardrails import guardrail_check

_MD = {
    "action_types": {
        "values": ["approve", "deny", "escalate", "monitor"],
        "ontology": {},
    },
    "valid_sets": {
        "departments": ["general"],
        "severities": ["general", "P0", "P1", "P2", "policy", "sla"],
        "workflow_types": ["general"],
        "customer_tiers": ["all"],
        "condition_fields": [],
    },
    "heuristic_patterns": {},
    "authority_levels": {"default": 1},
    "retrieval_weights": {
        "semantic": 0.45,
        "metadata": 0.20,
        "keyword": 0.15,
        "severity": 0.10,
        "condition": 0.10,
    },
    "thresholds": {
        "metadata_confidence": 0.60,
        "conditions_confidence": 0.60,
        "ambiguity_entropy": 0.75,
        "min_confidence_for_auto_action": 0.40,
        "graph_fallback_threshold": 0.5,
        "score_differential_threshold": 0.10,
        "specificity_bonus_scale": 0.02,
    },
}


def _load_metadata(brain):
    m = brain.get("metadata_json")
    if m and isinstance(m, dict):
        out = {}
        for k in _MD:
            v = m.get(k)
            out[k] = v if v is not None else _MD[k]
        return out
    return dict(_MD)


def _t(meta, k, d=0.0):
    return meta.get("thresholds", {}).get(k, d)


def _ats(meta):
    return meta.get("action_types", {}).get("values", [])


def _onto(meta):
    return meta.get("action_types", {}).get("ontology", {})


def _hpats(meta):
    return meta.get("heuristic_patterns", {})


def _wts(meta):
    return meta.get("retrieval_weights", {})


_DEPT_KEYWORDS = {
    "engineering": [
        "engineer",
        "bug",
        "outage",
        "deploy",
        "incident",
        "runbook",
        "on-call",
        "p0",
        "p1",
        "technical",
        "infra",
        "server",
        "database",
        "ci",
        "cd",
        "pipeline",
    ],
    "customer_support": [
        "refund",
        "charge",
        "invoice",
        "billing",
        "payment",
        "subscription",
        "price",
        "pricing",
        "ticket",
        "support",
    ],
    "finance": [
        "vendor",
        "invoice",
        "procurement",
        "supplier",
        "purchase order",
        "billing",
        "payment",
        "expense",
        "budget",
    ],
    "customer_success": [
        "churn",
        "onboard",
        "account manager",
        "enterprise customer",
        "customer success",
        "qbr",
        "health score",
        "adoption",
        "nps",
    ],
    "revenue": [
        "discount",
        "pricing",
        "plan",
        "startup",
        "promotion",
        "deal",
        "contract",
        "renewal",
        "upsell",
    ],
    "hr": [
        "hiring",
        "recruiter",
        "kpi",
        "pip",
        "performance",
        "interview",
        "offer letter",
        "onboarding",
        "termination",
        "review",
    ],
    "operations": [
        "ops lead",
        "procurement",
        "supplier",
        "logistics",
        "vendor",
        "inventory",
        "fulfillment",
    ],
    "legal": [
        "legal",
        "compliance",
        "regulatory",
        "policy",
        "terms",
        "privacy",
        "gdpr",
        "sla",
        "audit",
    ],
    "product": [
        "feature",
        "roadmap",
        "sprint",
        "backlog",
        "release",
        "product",
        "spec",
    ],
    "marketing": ["campaign", "lead", "content", "social", "brand", "seo", "ad"],
}


def _build_dept_hints(meta):
    valid_depts = set((meta or _MD).get("valid_sets", {}).get("departments", []))
    hints = []
    for dept in valid_depts:
        kw = _DEPT_KEYWORDS.get(dept, [dept.replace("_", " ")])
        hints.append((kw, dept))
    if not hints:
        for dept, kw in _DEPT_KEYWORDS.items():
            hints.append((kw, dept))
    return hints


def _extract_query_signals(text, ctx, meta=None):
    text_l = text.lower()
    ctx_l = {str(k).lower(): str(v).lower() for k, v in (ctx or {}).items()}
    vs = set((meta or _MD).get("valid_sets", {}).get("severities", ["general"]))
    sev = None
    sp = ctx_l.get("priority", "").upper()
    for s in sorted(vs, reverse=True):
        if s.startswith("P") and (s in text.upper() or sp == s):
            sev = s
            break
    if sev is None:
        pm = {
            "P0": [
                "completely down",
                "production down",
                "services down",
                "p0",
                "critical",
                "emergency",
            ],
            "P1": ["p1", "broken", "feature broken", "major", "severe"],
            "P2": ["p2", "minor", "degraded"],
        }
        for s, pts in pm.items():
            if s in vs and any(t in text_l for t in pts):
                sev = s
                break
    hints = _build_dept_hints(meta)
    dept_h = set()
    for kw, d in hints:
        if any(t in text_l for t in kw):
            dept_h.add(d)
    esc = any(
        t in text_l
        for t in [
            "escalat",
            "founder",
            "account executive",
            "ae ",
            "lead",
            "approval",
            "manager",
        ]
    )
    toks = set(re.sub(r"[^a-z0-9\- ]", "", text_l).split())
    cv = {}
    for k, v in (ctx or {}).items():
        kl = str(k).lower().strip()
        try:
            cv[kl] = float(v)
        except:
            if isinstance(v, str):
                vl = v.lower().strip()
                cv[kl] = (
                    True
                    if vl in ("true", "yes")
                    else (False if vl in ("false", "no") else vl)
                )
            else:
                cv[kl] = v
    return {
        "severity": sev,
        "department_hints": dept_h,
        "escalation_signal": esc,
        "query_tokens": toks,
        "context_values": cv,
        "raw_text": text,
    }


def _get_trusted_op(skill, meta=None):
    meta = meta or _MD
    mt = _t(meta, "metadata_confidence", 0.60)
    ct = _t(meta, "conditions_confidence", 0.60)
    op = skill.get("operational") or {}
    cf = skill.get("metadata_confidence") or {}
    t = {}
    for f in (
        "department",
        "severity",
        "action_type",
        "workflow_type",
        "customer_tier",
    ):
        fc = cf.get(f, 0.5)
        t[f] = op.get(f) if fc >= mt else None
    t["escalation_required"] = op.get("escalation_required", False)
    t["specificity_level"] = op.get("specificity_level", 2)
    cc = skill.get("conditions_confidence", 0.5)
    t["conditions"] = skill.get("conditions", []) if cc >= ct else []
    return t


def _score_meta(td, qs):
    s = 0.0
    r = {}
    dh = qs["department_hints"]
    sd = td.get("department")
    if sd and dh:
        if sd in dh:
            s += 0.50
            r["department"] = f"matched ({sd})"
        else:
            r["department"] = f"mismatch (skill={sd}, hints={dh})"
    else:
        r["department"] = "no signal"
    if td.get("action_type"):
        s += 0.20
        r["action_type_present"] = td["action_type"]
    return min(s, 1.0), r


def _score_kw(skill, qs):
    sk = set(k.lower() for k in (skill.get("keywords") or []))
    if not sk:
        return 0.0, {"overlap": "no keywords in skill"}
    qt = qs["query_tokens"]
    ov = sk & qt
    return min(len(ov) / (len(sk) + 1), 1.0), {
        "matched_keywords": list(ov)[:5],
        "skill_keywords": list(sk)[:5],
        "overlap_count": len(ov),
    }


def _score_sev(td, qs):
    qs_ = qs["severity"]
    ss = td.get("severity")
    er = td.get("escalation_required", False)
    es = qs["escalation_signal"]
    if qs_ and ss and qs_ == ss:
        return 1.0, {"reason": f"severity exact match ({qs_})"}
    if es and er:
        return 0.5, {"reason": "escalation signal aligned"}
    if qs_ and ss and qs_ != ss:
        return 0.0, {"reason": f"severity mismatch (query={qs_}, skill={ss})"}
    return 0.0, {"reason": "no severity signal"}


def _score_cond(td, qs):
    conds = td.get("conditions", [])
    if not conds:
        return 0.0, {"reason": "no conditions in skill"}
    cv = qs.get("context_values", {})
    if not cv:
        return 0.0, {"reason": "no context values provided in query"}
    mc = 0
    ec = 0
    reasons = []
    for c in conds:
        f = c.get("field")
        o = c.get("operator")
        v = c.get("value")
        if f not in cv:
            continue
        ctx = cv[f]
        ec += 1
        m = False
        try:
            if o == "==":
                m = ctx == v
            elif o == "!=":
                m = ctx != v
            elif o == ">":
                m = ctx > v
            elif o == ">=":
                m = ctx >= v
            elif o == "<":
                m = ctx < v
            elif o == "<=":
                m = ctx <= v
            elif o == "in" and isinstance(v, list):
                m = ctx in v
            elif o == "not_in" and isinstance(v, list):
                m = ctx not in v
        except:
            pass
        if m:
            mc += 1
            reasons.append(f"{f} {o} {v} (matched {ctx})")
        else:
            reasons.append(f"{f} {o} {v} (failed vs {ctx})")
    if ec == 0:
        return 0.0, {"reason": "no conditions matched available context keys"}
    return mc / ec, {"matched": mc, "evaluated": ec, "details": reasons}


def _hybrid(sem, skill, qs, wts=None, meta=None):
    meta = meta or _MD
    w = wts or _wts(meta)
    sbs = _t(meta, "specificity_bonus_scale", 0.02)
    td = _get_trusted_op(skill, meta)
    ms, mr = _score_meta(td, qs)
    ks, kr = _score_kw(skill, qs)
    ss, sr = _score_sev(td, qs)
    cs, cr = _score_cond(td, qs)
    op_s = (
        ms * w.get("metadata", 0.20)
        + ks * w.get("keyword", 0.15)
        + ss * w.get("severity", 0.10)
        + cs * w.get("condition", 0.10)
    )
    s_sem = sem * w.get("semantic", 0.45)
    sp = td.get("specificity_level", 2)
    sb = (sp / 5.0) * sbs
    f_s = s_sem + op_s + sb
    denom = max(
        w.get("metadata", 0.20)
        + w.get("keyword", 0.15)
        + w.get("severity", 0.10)
        + w.get("condition", 0.10),
        1e-10,
    )
    return f_s, {
        "semantic_confidence": round(sem, 4),
        "operational_confidence": round(op_s / denom, 4),
        "embedding_sim": round(sem, 4),
        "metadata_score": round(ms, 4),
        "keyword_score": round(ks, 4),
        "severity_score": round(ss, 4),
        "condition_score": round(cs, 4),
        "specificity_bonus": round(sb, 4),
        "final_score": round(f_s, 4),
        "meta_reasons": mr,
        "kw_reasons": kr,
        "sev_reasons": sr,
        "cond_reasons": cr,
    }


def _trace(top, runner_up=None):
    ts = top["skill"]
    tc = top["components"]
    wp = []
    mr = tc.get("meta_reasons", {})
    if "matched" in str(mr.get("department", "")):
        wp.append(f"Department={mr['department']}")
    if tc.get("kw_reasons", {}).get("matched_keywords"):
        wp.append(
            f"Keywords [{', '.join(tc['kw_reasons']['matched_keywords'][:3])}] overlapped"
        )
    if tc.get("sev_reasons", {}).get("reason", "").startswith("severity exact"):
        wp.append(tc["sev_reasons"]["reason"])
    if tc.get("specificity_bonus", 0) > 0:
        wp.append(
            f"Specificity level {(ts.get('operational') or {}).get('specificity_level', '?')} preferred"
        )
    if tc.get("cond_reasons", {}).get("matched", 0) > 0:
        wp.append(
            f"Matched {tc['cond_reasons']['matched']}/{tc['cond_reasons']['evaluated']} explicit conditions"
        )
    tr = {
        "top_skill": ts.get("id", "unknown"),
        "final_score": tc["final_score"],
        "components": {
            "semantic_confidence": tc["semantic_confidence"],
            "operational_confidence": tc["operational_confidence"],
            "embedding_sim": tc["embedding_sim"],
            "metadata_score": tc["metadata_score"],
            "keyword_score": tc["keyword_score"],
            "severity_score": tc["severity_score"],
            "condition_score": tc.get("condition_score", 0.0),
            "specificity_bonus": tc["specificity_bonus"],
        },
        "matched_conditions": tc.get("cond_reasons", {}).get("details", []),
        "why_matched": ". ".join(wp) if wp else "Highest semantic similarity",
    }
    if runner_up:
        rs = runner_up["skill"]
        rc = runner_up["components"]
        tr["runner_up"] = rs.get("id", "unknown")
        tr["why_runner_up_lost"] = {
            "semantic_gap": round(tc["embedding_sim"] - rc["embedding_sim"], 4),
            "final_score_gap": round(tc["final_score"] - rc["final_score"], 4),
            "missing_metadata_match": rc["metadata_score"] < 0.3,
            "severity_mismatch": rc["severity_score"] == 0.0
            and tc["severity_score"] > 0.0,
            "lower_specificity": (rs.get("operational") or {}).get(
                "specificity_level", 2
            )
            < (ts.get("operational") or {}).get("specificity_level", 2),
            "condition_gap": rc.get("condition_score", 0.0)
            < tc.get("condition_score", 0.0),
            "runner_up_scores": {
                "semantic_confidence": rc["semantic_confidence"],
                "operational_confidence": rc["operational_confidence"],
                "keyword_score": rc["keyword_score"],
                "condition_score": rc.get("condition_score", 0.0),
            },
        }
    return tr


def _heuristic_cands(qs, top_r, meta=None):
    meta = meta or _MD
    onto = _onto(meta)
    pats = _hpats(meta)
    cands = {}
    txt = " ".join(qs["query_tokens"]).lower()
    for r in top_r:
        txt += (
            " "
            + r["skill"].get("category", "").lower()
            + " "
            + r["skill"].get("rule", "").lower()
        )
    sev = qs.get("severity")
    ats_set = _ats(meta)
    if sev == "P0":
        a = "page_on_call" if "page_on_call" in ats_set else sev.lower()
        cands[a] = {
            "action": a,
            "retrieval_score": 0.5,
            "source_skill": "fallback",
            "action_confidence": 0.5,
            "specificity": onto.get(a, {}).get("specificity", 5),
            "category": onto.get(a, {}).get("category", "incident_response"),
            "fallback_used": True,
        }
    elif sev == "P1":
        a = (
            "resolve_within_4_hours"
            if "resolve_within_4_hours" in ats_set
            else sev.lower()
        )
        cands[a] = {
            "action": a,
            "retrieval_score": 0.4,
            "source_skill": "fallback",
            "action_confidence": 0.5,
            "specificity": onto.get(a, {}).get("specificity", 3),
            "category": onto.get(a, {}).get("category", "incident_response"),
            "fallback_used": True,
        }
    for p, a in pats.items():
        if p in txt and a not in cands:
            cands[a] = {
                "action": a,
                "retrieval_score": 0.4,
                "source_skill": "fallback",
                "action_confidence": 0.5,
                "specificity": onto.get(a, {}).get("specificity", 2),
                "category": onto.get(a, {}).get("category", "unknown"),
                "fallback_used": True,
            }
    return list(cands.values())


def _entropy(cands):
    if not cands:
        return 0.0
    ss = [c["retrieval_score"] for c in cands]
    t = sum(ss)
    if t <= 0:
        return 0.0
    ps = [s / t for s in ss]
    e = -sum(p * math.log(p, 2) for p in ps if p > 0)
    mx = math.log(len(ps), 2) if len(ps) > 1 else 1.0
    return e / mx if mx > 0 else 0.0


def _admissible(top_r, qs, meta=None):
    meta = meta or _MD
    ats = set(_ats(meta))
    onto = _onto(meta)
    mt = _t(meta, "metadata_confidence", 0.60)
    cands = {}
    for rr in top_r:
        sk = rr["skill"]
        sc = rr["score"]
        op = sk.get("operational") or {}
        cf = sk.get("metadata_confidence") or {}
        a = op.get("action_type")
        if not a or a not in ats:
            continue
        ac = cf.get("action_type", 0.5)
        if ac < mt:
            continue
        td = _get_trusted_op(sk, meta)
        conds = td.get("conditions", [])
        if a not in cands or cands[a]["retrieval_score"] < sc:
            cands[a] = {
                "action": a,
                "retrieval_score": round(sc, 4),
                "source_skill": sk.get("id", "unknown"),
                "action_confidence": round(ac, 3),
                "specificity": onto.get(a, {}).get("specificity", 2),
                "category": onto.get(a, {}).get("category", "unknown"),
                "fallback_used": False,
                "conditions": conds,
            }
    ranked = sorted(
        cands.values(),
        key=lambda x: x["retrieval_score"] * x["action_confidence"],
        reverse=True,
    )[:4]
    if len(ranked) < 2:
        hc = _heuristic_cands(qs, top_r, meta)
        for h in hc:
            if h["action"] not in [c["action"] for c in ranked]:
                ranked.append(h)
        ranked = sorted(
            ranked,
            key=lambda x: x["retrieval_score"] * x.get("action_confidence", 0.5),
            reverse=True,
        )[:4]
    return ranked, _entropy(ranked)


def _load_db(cid):
    try:
        db = get_client()
        if not db:
            return None, "Database connection failed."
        r = (
            db.table("skills_files")
            .select("brain_json")
            .eq("company_id", cid)
            .order("compiled_at", desc=True)
            .limit(1)
            .execute()
        )
        if not r.data:
            return None, "No compiled brain found. Please compile first."
        return r.data[0]["brain_json"], None
    except Exception as e:
        return None, f"Database query failed: {e}"


async def handle_agent_query(cid, scenario, ctx=None, with_brain=True, rw=None):
    # Constitutional (CLAUDE.md rule 4): no fixture fallbacks. DB failure is an
    # explicit, visible error -- the runtime never silently substitutes a local
    # artifact. The with_brain=False baseline path (Brain-vs-Generic demo
    # theater) is retired and rejected.
    if not with_brain:
        return _err(
            "The with_brain=False baseline mode is retired (see CLAUDE.md: "
            "'never resurrect ... Brain-vs-Generic demo theater')."
        )
    bd, err = _load_db(cid)
    if err:
        return _err(f"unavailable: {err}")
    skills = bd.get("skills", [])
    if not skills:
        return _err("Brain is empty — no skills compiled.")
    meta = _load_metadata(bd)
    graph = bd.get("graph_json", {})
    gf = _t(meta, "graph_fallback_threshold", 0.5)
    gr = retrieve_from_graph(scenario, ctx or {}, graph)
    # W1 (constitutional): the operational graph is NOT decision authority --
    # compiled graph policies are unconditional approves. Graph retrieval stays
    # advisory (reasoning steps only); it never gates the decision path.
    # Re-enabling requires an evidence-citing decision record.
    gu = False
    _ = gf  # threshold retained for the advisory trace only
    grr = gr.get("reasoning_steps", [])
    qt = f"{scenario} {json.dumps(ctx or {})}"
    qe = get_embedding(qt)
    qs = _extract_query_signals(scenario, ctx, meta)
    w = rw or _wts(meta)
    cached = all("embedding_vector" in s for s in skills)
    if cached:
        se = np.array([s["embedding_vector"] for s in skills])
        qv = np.array(qe)
        norms = np.linalg.norm(se, axis=1) * np.linalg.norm(qv)
        norms[norms == 0] = 1e-10
        sem_scores = (np.dot(se, qv) / norms).tolist()
    else:
        sem_scores = []
        for sk in skills:
            st = " ".join(
                filter(
                    None,
                    [
                        sk.get("category", ""),
                        sk.get("rule", ""),
                        sk.get("rationale", ""),
                    ],
                )
            )
            se2 = get_embedding(st)
            sem_scores.append(
                float(
                    np.dot(qe, se2) / (np.linalg.norm(qe) * np.linalg.norm(se2) + 1e-10)
                )
            )
    scored = []
    for i, (sk, sem) in enumerate(zip(skills, sem_scores)):
        fs, comp = _hybrid(sem, sk, qs, w, meta)
        scored.append({"skill": sk, "score": fs, "components": comp, "index": i})
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_r = scored[:5]
    rt = _trace(top_r[0], runner_up=top_r[1] if len(top_r) > 1 else None)
    r_scores = [s["score"] for s in top_r]
    aa, ce = _admissible(top_r, qs, meta)
    cr = constraint_resolve(
        graph_result=gr,
        skill_admissible=aa,
        context=ctx or {},
        query_signals=qs,
        authority_rules=graph.get("authority_rules", {}),
        requester_role=(ctx or {}).get("requested_by"),
        metadata=meta,
    )
    gc = ""
    if gu:
        ents = graph.get("entities", {})
        pl = gr.get("policies", [])
        gc = "\n--- Graph-Derived Policy Context ---\n"
        if ents:
            gc += f"Matched entities: {list(ents.keys())}\n\n"
        for i, p in enumerate(pl):
            gc += f"Policy #{i + 1}: {p.get('rule_text', p.get('rule', ''))}\n  Category: {p.get('category', 'general')}\n  Effect: {p.get('effect', 'ambiguous')}\n  Confidence: {p.get('confidence', 0.5)}\n"
            if p.get("conditions"):
                gc += f"  Conditions: {json.dumps(p['conditions'])}\n"
        gc += f"\nGraph Resolution Steps:\n" + "".join(f"  - {s}\n" for s in grr)
        gc += f"\nGraph Confidence: {gr['graph_confidence']:.2f}\n"
    sc_ctx = ""
    for rk, s in enumerate(top_r):
        sk = s["skill"]
        c = s["components"]
        sc_ctx += f"\n--- Skill #{rk + 1} (hybrid_score: {s['score']:.4f}, semantic: {c['embedding_sim']:.3f}, operational: {c['operational_confidence']:.3f}) ---\nCategory: {sk.get('category', 'Unknown')}\nRule: {sk.get('rule', '')}\nRationale: {sk.get('rationale', '')}\n"
        ev = sk.get("evidence", [])
        if isinstance(ev, list):
            sc_ctx += f"Evidence: {json.dumps(ev[:3])}\n"
        sc_ctx += f"Compiled Confidence: {sk.get('confidence', 'unknown')}\n"
        op = sk.get("operational") or {}
        if op.get("action_type"):
            sc_ctx += f"Operational Action Type: {op['action_type']}\n"
        if op.get("severity"):
            sc_ctx += f"Severity: {op['severity']}\n"
    ts_c = top_r[0]["components"]["semantic_confidence"] if top_r else 0.0
    to_c = top_r[0]["components"]["operational_confidence"] if top_r else 0.0
    ca = cr.primary_action.action_type if cr.primary_action else "ambiguous"
    cs_ = cr.resolution_source
    ce_ = cr.entropy
    ca_ = cr.is_ambiguous
    cesc = cr.escalation_required
    crs = "\n".join(f"  - {s}" for s in cr.reasoning_steps[-5:])
    if ca_:
        als = "\n".join(
            f"  - {a.action_type} (conf={a.confidence:.2f}, source={a.source})"
            for a in cr.all_admissible_actions
        )
        cs_sum = f"AMBUGIOUS — No single action could be determined.\nEntropy: {ce_:.3f}\nAll admissible actions:\n{als}"
    else:
        cs_sum = f"Action: {ca}\nSource: {cs_}\nConfidence: {cr.primary_action.confidence:.3f}\nEscalation required: {cesc}\nEscalation target: {cr.escalation_target or 'none'}\nEvidence: {json.dumps(cr.primary_action.evidence[:3])}"
    rsn = (
        "These policies were resolved from the operational graph — they represent explicit company policies with typed conditions."
        if cs_ == "graph"
        else "These actions were resolved from skill-based retrieval — they represent learned patterns from company communications."
    )
    prompt = f"""You are a policy explainer. The constraint engine has already determined the correct action.
Your ONLY job is to explain it in natural language. Do NOT override the action.
CRITICAL LANGUAGE INTERPRETATION RULES (for explanation only):
- "No refunds after X days" means: refunds are allowed if the scenario is BEFORE X days.
- "Full refund within X days" means: refunds are allowed only if scenario is WITHIN X days.
- The constraint engine has already evaluated numeric thresholds; you just need to explain them.
CONSTRAINT ENGINE DECISION:
{cs_sum}
RESOLUTION TRACE:
{crs}
{rsn}
IMPORTANT RULES:
- Your action_type MUST match the constraint engine's action_type exactly.
- If the constraint engine says "ambiguous", output action_type="ambiguous" and explain why multiple options exist.
- If escalation is required, explain who needs to approve and why.
- Do NOT invent actions not in the constraint engine's admissible set.
Respond with ONLY this JSON:
{{"action_type":"{ca}","action_category":"category from ontology","requires_approval":{str(cesc).lower()},"recommended_action":"human-readable explanation","rule_applied":"the specific rule","evidence":["evidence items"],"skill_matched":"skill category","action_confidence":{{"retrieval_confidence":{ts_c:.3f},"operational_confidence":{to_c:.3f},"selection_confidence":{(cr.primary_action.confidence if cr.primary_action else 0.0):.3f}}},"decision_trace":{{"candidate_actions":["list"],"selected_action":"{ca}","selection_reason":"selected by constraint engine","rejected_actions":[],"candidate_entropy":{ce:.3f},"constraint_entropy":{ce_:.3f}}},"reasoning":"explain what the constraint engine decided"}}"""
    uc = f"--- Scenario ---\n{scenario}\n\n--- Additional Context ---\n{json.dumps(ctx or {})}\n\n--- Retrieved Skills (ranked by hybrid operational relevance) ---\n{sc_ctx}"
    try:
        rs = await llm_call(prompt, uc)
        result = _parse(rs)
    except:
        result = {
            "action_type": "",
            "recommended_action": "",
            "rule_applied": "",
            "evidence": [],
            "skill_matched": "none",
            "action_confidence": {
                "retrieval_confidence": ts_c,
                "operational_confidence": to_c,
                "selection_confidence": cr.primary_action.confidence
                if cr.primary_action
                else 0.0,
            },
            "retrieval_scores": r_scores,
            "reasoning": "LLM call failed; using constraint resolver decision.",
        }
    result = guardrail_check(result, cr)
    result["retrieval_scores"] = r_scores
    result["cached_embedding"] = cached
    result["retrieval_trace"] = rt
    result["action_type"] = _norm(result.get("action_type", ""), meta)
    result["graph_used"] = gu
    result["graph_reasoning"] = grr
    if gu:
        result["graph_policies"] = [
            {
                "rule": p.get("rule_text", p.get("rule", "")),
                "category": p.get("category", "general"),
                "effect": p.get("effect", ""),
                "confidence": p.get("confidence", 0.0),
            }
            for p in gr.get("policies", [])
        ]
    if "decision_trace" not in result:
        result["decision_trace"] = {"candidate_entropy": round(ce, 3)}
    else:
        result["decision_trace"]["candidate_entropy"] = round(ce, 3)
    result["constraint_result"] = cr.to_dict()
    return result


def _norm(raw, meta=None):
    if not raw:
        return ""
    meta = meta or _MD
    ats = _ats(meta)
    c = raw.lower().strip().replace(" ", "_").replace("-", "_")
    return c if c in ats or c == "ambiguous" else c


def _parse(raw):
    try:
        c = raw.strip()
        if c.startswith("```json"):
            c = c[7:]
        elif c.startswith("```"):
            c = c[3:]
        if c.endswith("```"):
            c = c[:-3]
        return json.loads(c.strip())
    except Exception as e:
        return {
            "action_type": "",
            "recommended_action": "Failed to parse LLM response",
            "rule_applied": "none",
            "evidence": [],
            "skill_matched": "none",
            "action_confidence": {
                "retrieval_confidence": 0.0,
                "operational_confidence": 0.0,
                "selection_confidence": 0.0,
            },
            "retrieval_scores": [],
            "reasoning": f"JSON parse error: {e}. Raw: {raw[:500]}",
        }


def _err(msg):
    return {
        "action_type": "",
        "recommended_action": msg,
        "rule_applied": "none",
        "evidence": [],
        "skill_matched": "none",
        "action_confidence": {
            "retrieval_confidence": 0.0,
            "operational_confidence": 0.0,
            "selection_confidence": 0.0,
        },
        "retrieval_scores": [],
        "reasoning": msg,
    }
