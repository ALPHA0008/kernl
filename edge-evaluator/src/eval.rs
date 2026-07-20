//! The pure decision function — an outcome-exact port of
//! backend/runtime/evaluator.py's `evaluate`. "Outcome-exact" means: for the
//! same (facts, bundle, workflow), this produces the same OUTCOME as Python
//! (kind, action, policy_id, escalation_reason, sorted missing_facts, sorted
//! conflict_between) plus the enforce-critical precedence facts (winner,
//! applied_rules, dominance blockers). The differential test harness
//! (tests/conformance) proves this parity against the live Python evaluator.
//!
//! Determinism and strictness are preserved verbatim:
//!   * a condition on an absent fact is "missing", never a silent pass/fail;
//!   * winner selection is overrides -> specificity -> priority, ties escalate;
//!   * an undeterminable policy with strictly higher priority than the winner
//!     blocks the decision (the dominance rule).

use std::collections::{BTreeSet, HashMap, HashSet};

use crate::schema::{Bundle, CondValue, Condition, Policy, Scalar};

#[derive(Debug, PartialEq, Eq)]
pub enum PolicyStatus {
    Matched,
    Failed,
    Undeterminable,
}

pub struct PolicyEval<'a> {
    pub policy: &'a Policy,
    pub status: PolicyStatus,
    pub missing_fields: Vec<String>, // sorted-unique, mirrors Python
}

/// The outcome — the enforce-critical result. Mirrors backend Outcome's
/// decision-relevant fields (the full trace's per-condition detail is a
/// reporting concern, not needed at the enforce edge).
#[derive(Debug, Clone, serde::Serialize, PartialEq)]
pub struct Outcome {
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub action: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub policy_id: Option<String>,
    #[serde(default)]
    pub approval_required: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub approver_role: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub escalation_reason: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub missing_facts: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub conflict_between: Vec<String>,
}

#[derive(Debug, Clone, serde::Serialize, PartialEq)]
pub struct Precedence {
    pub applied_rules: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub winner: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub tie_between: Vec<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub dominance_blocked_by: Vec<String>,
}

#[derive(Debug, Clone, serde::Serialize, PartialEq)]
pub struct Decision {
    pub outcome: Outcome,
    pub precedence: Precedence,
}

#[derive(Debug)]
pub enum EvalError {
    UnknownWorkflow(String),
    InvalidFacts(String),
}

/// Python's `_compare`. `actual` is guaranteed present (missing handled upstream).
fn compare(cond: &Condition, actual: &Scalar) -> bool {
    match cond.value_type.as_str() {
        "number" => {
            let a = actual.as_number().expect("number-typed fact must be numeric");
            let e = match &cond.value {
                CondValue::One(s) => s.as_number().expect("number condition value"),
                CondValue::List(_) => unreachable!("number ops are never list ops"),
            };
            match cond.operator.as_str() {
                "gt" => a > e,
                "gte" => a >= e,
                "lt" => a < e,
                "lte" => a <= e,
                "eq" => a == e,
                "neq" => a != e,
                _ => unreachable!("bad number operator {}", cond.operator),
            }
        }
        "string" => {
            let a = actual.norm_str();
            match cond.operator.as_str() {
                "eq" => match &cond.value {
                    CondValue::One(s) => a == s.norm_str(),
                    _ => unreachable!(),
                },
                "neq" => match &cond.value {
                    CondValue::One(s) => a != s.norm_str(),
                    _ => unreachable!(),
                },
                "in" => match &cond.value {
                    CondValue::List(vs) => vs.iter().any(|v| v.norm_str() == a),
                    _ => unreachable!(),
                },
                "not_in" => match &cond.value {
                    CondValue::List(vs) => !vs.iter().any(|v| v.norm_str() == a),
                    _ => unreachable!(),
                },
                _ => unreachable!("bad string operator {}", cond.operator),
            }
        }
        "boolean" => {
            // Python: bool(actual) is bool(cond.value), only "eq".
            let a = actual.as_bool().expect("boolean-typed fact must be bool");
            let e = match &cond.value {
                CondValue::One(s) => s.as_bool().expect("boolean condition value"),
                _ => unreachable!(),
            };
            a == e
        }
        other => unreachable!("unknown value_type {}", other),
    }
}

/// Python's `_check_type` — validates a supplied fact against its declared
/// type, returning the normalized Scalar or an InvalidFacts error. Integral
/// floats normalize to ints (matches Python), which is irrelevant to numeric
/// comparison but kept for fidelity.
fn check_type(name: &str, value: &Scalar, value_type: &str) -> Result<Scalar, EvalError> {
    match value_type {
        "number" => match value {
            Scalar::Bool(_) => Err(EvalError::InvalidFacts(format!(
                "fact {name:?} must be a number, got a boolean"
            ))),
            Scalar::Int(i) => Ok(Scalar::Int(*i)),
            Scalar::Float(f) => {
                if f.fract() == 0.0 {
                    Ok(Scalar::Int(*f as i64))
                } else {
                    Ok(Scalar::Float(*f))
                }
            }
            _ => Err(EvalError::InvalidFacts(format!(
                "fact {name:?} must be a number"
            ))),
        },
        "string" => match value {
            Scalar::Str(s) => Ok(Scalar::Str(s.clone())),
            _ => Err(EvalError::InvalidFacts(format!(
                "fact {name:?} must be a string"
            ))),
        },
        "boolean" => match value {
            Scalar::Bool(b) => Ok(Scalar::Bool(*b)),
            _ => Err(EvalError::InvalidFacts(format!(
                "fact {name:?} must be a boolean"
            ))),
        },
        other => Err(EvalError::InvalidFacts(format!(
            "fact {name:?}: unknown declared type {other:?}"
        ))),
    }
}

fn evaluate_policy<'a>(policy: &'a Policy, facts: &HashMap<String, Scalar>) -> PolicyEval<'a> {
    let mut missing: Vec<String> = Vec::new();
    let mut any_fail = false;
    for cond in &policy.conditions {
        match facts.get(&cond.field) {
            None => missing.push(cond.field.clone()),
            Some(actual) => {
                if !compare(cond, actual) {
                    any_fail = true;
                }
            }
        }
    }
    let status = if any_fail {
        PolicyStatus::Failed
    } else if !missing.is_empty() {
        PolicyStatus::Undeterminable
    } else {
        PolicyStatus::Matched
    };
    // sorted-unique, like Python's tuple(sorted(set(missing)))
    let uniq: BTreeSet<String> = missing.into_iter().collect();
    PolicyEval {
        policy,
        status,
        missing_fields: uniq.into_iter().collect(),
    }
}

/// Winner selection: overrides -> specificity -> priority. Returns
/// (winner, applied_rules, tie_between). Mirrors `_select_winner`.
fn select_winner<'a>(
    matched: &[&'a Policy],
) -> (Option<&'a Policy>, Vec<String>, Vec<String>) {
    if matched.is_empty() {
        return (None, vec![], vec![]);
    }
    let mut rules: Vec<String> = Vec::new();
    let mut survivors: Vec<&Policy> = matched.to_vec();

    // overrides
    let matched_ids: HashSet<&str> = survivors.iter().map(|p| p.id.as_str()).collect();
    let mut overridden: HashSet<String> = HashSet::new();
    for p in &survivors {
        for target in &p.overrides {
            if matched_ids.contains(target.as_str()) {
                overridden.insert(target.clone());
            }
        }
    }
    if !overridden.is_empty() {
        rules.push("overrides".into());
        survivors.retain(|p| !overridden.contains(&p.id));
    }

    // specificity
    if survivors.len() > 1 {
        let top = survivors.iter().map(|p| p.specificity()).max().unwrap();
        if survivors.iter().any(|p| p.specificity() < top) {
            rules.push("specificity".into());
            survivors.retain(|p| p.specificity() == top);
        }
    }

    // priority
    if survivors.len() > 1 {
        let top = survivors.iter().map(|p| p.priority).max().unwrap();
        if survivors.iter().any(|p| p.priority < top) {
            rules.push("priority".into());
            survivors.retain(|p| p.priority == top);
        }
    }

    if survivors.len() > 1 {
        let mut tie: Vec<String> = survivors.iter().map(|p| p.id.clone()).collect();
        tie.sort();
        return (None, rules, tie);
    }
    if survivors.len() == 1 && rules.is_empty() {
        rules.push("single_match".into());
    }
    (survivors.into_iter().next(), rules, vec![])
}

pub fn evaluate(
    facts: &HashMap<String, Scalar>,
    bundle: &Bundle,
    workflow: &str,
) -> Result<Decision, EvalError> {
    let wf = bundle
        .workflow(workflow)
        .ok_or_else(|| EvalError::UnknownWorkflow(workflow.to_string()))?;

    // fact validation -> effective facts (after defaults). Mirrors _validate_facts.
    let fact_map: HashMap<&str, &crate::schema::FactSpec> =
        wf.facts.iter().map(|f| (f.name.as_str(), f)).collect();
    let mut effective: HashMap<String, Scalar> = HashMap::new();
    for (name, value) in facts {
        if let Some(spec) = fact_map.get(name.as_str()) {
            let checked = check_type(name, value, &spec.value_type)?;
            effective.insert(name.clone(), checked);
        }
        // unknown fields are ignored (not an error), like Python
    }
    for f in &wf.facts {
        if !effective.contains_key(&f.name) {
            if let Some(def) = &f.default {
                effective.insert(f.name.clone(), def.clone());
            }
        }
    }

    let policies = bundle.policies_for(workflow);
    let evals: Vec<PolicyEval> = policies.iter().map(|p| evaluate_policy(p, &effective)).collect();

    let matched: Vec<&Policy> = evals
        .iter()
        .filter(|e| e.status == PolicyStatus::Matched)
        .map(|e| e.policy)
        .collect();
    let undeterminable: Vec<&PolicyEval> = evals
        .iter()
        .filter(|e| e.status == PolicyStatus::Undeterminable)
        .collect();

    let (winner, rules, tie) = select_winner(&matched);

    // tie -> conflict escalation
    if !tie.is_empty() {
        return Ok(Decision {
            outcome: Outcome {
                kind: "escalate".into(),
                action: None,
                policy_id: None,
                approval_required: false,
                approver_role: None,
                escalation_reason: Some("conflict".into()),
                missing_facts: vec![],
                conflict_between: tie.clone(),
            },
            precedence: Precedence {
                applied_rules: rules,
                winner: None,
                tie_between: tie,
                dominance_blocked_by: vec![],
            },
        });
    }

    // no winner -> missing_facts (if any undeterminable) else no_matching_policy
    if winner.is_none() {
        let (reason, fields): (&str, Vec<String>) = if !undeterminable.is_empty() {
            let mut set: BTreeSet<String> = BTreeSet::new();
            for e in &undeterminable {
                for f in &e.missing_fields {
                    set.insert(f.clone());
                }
            }
            ("missing_facts", set.into_iter().collect())
        } else {
            ("no_matching_policy", vec![])
        };
        return Ok(Decision {
            outcome: Outcome {
                kind: "escalate".into(),
                action: None,
                policy_id: None,
                approval_required: false,
                approver_role: None,
                escalation_reason: Some(reason.into()),
                missing_facts: fields,
                conflict_between: vec![],
            },
            precedence: Precedence {
                applied_rules: rules,
                winner: None,
                tie_between: vec![],
                dominance_blocked_by: vec![],
            },
        });
    }

    let winner = winner.unwrap();

    // dominance: an undeterminable policy with STRICTLY higher priority blocks.
    let blockers: Vec<&PolicyEval> = undeterminable
        .iter()
        .copied()
        .filter(|e| e.policy.priority > winner.priority)
        .collect();
    if !blockers.is_empty() {
        let mut fset: BTreeSet<String> = BTreeSet::new();
        let mut bset: BTreeSet<String> = BTreeSet::new();
        for e in &blockers {
            for f in &e.missing_fields {
                fset.insert(f.clone());
            }
            bset.insert(e.policy.id.clone());
        }
        let mut rules_d = rules.clone();
        rules_d.push("dominance".into());
        return Ok(Decision {
            outcome: Outcome {
                kind: "escalate".into(),
                action: None,
                policy_id: None,
                approval_required: false,
                approver_role: None,
                escalation_reason: Some("missing_facts".into()),
                missing_facts: fset.into_iter().collect(),
                conflict_between: vec![],
            },
            precedence: Precedence {
                applied_rules: rules_d,
                winner: None,
                tie_between: vec![],
                dominance_blocked_by: bset.into_iter().collect(),
            },
        });
    }

    // decisive ruling
    Ok(Decision {
        outcome: Outcome {
            kind: winner.effect.kind.clone(),
            action: Some(winner.effect.action.clone()),
            policy_id: Some(winner.id.clone()),
            approval_required: winner.authority.approval_required,
            approver_role: winner.authority.approver_role.clone(),
            escalation_reason: None,
            missing_facts: vec![],
            conflict_between: vec![],
        },
        precedence: Precedence {
            applied_rules: rules,
            winner: Some(winner.id.clone()),
            tie_between: vec![],
            dominance_blocked_by: vec![],
        },
    })
}
