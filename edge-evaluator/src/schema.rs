//! Bundle schema — the Rust mirror of backend/bundle/schema.py, deserialized
//! from the exact JSON that `Bundle.model_dump(mode="json")` produces on the
//! Python side. Field names and shapes must match byte-for-byte so the two
//! evaluators read identical inputs.

use serde::Deserialize;

/// A scalar value in a fact or a condition. JSON gives us exactly these forms.
/// We keep numbers as f64 (Python coerces to float for numeric comparison) and
/// preserve bool separately from number (Python is strict: a bool is never a
/// number, and vice-versa).
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum Scalar {
    // Order matters for untagged deserialization: Bool before Int/Float, since
    // serde_json would otherwise accept `true` as... it wouldn't, but being
    // explicit guards intent. String last.
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(String),
}

impl Scalar {
    /// Numeric value as f64 (matches Python's `float(actual)`), or None if not
    /// numeric. A bool is NOT numeric (Python's strictness).
    pub fn as_number(&self) -> Option<f64> {
        match self {
            Scalar::Int(i) => Some(*i as f64),
            Scalar::Float(f) => Some(*f),
            _ => None,
        }
    }

    pub fn as_bool(&self) -> Option<bool> {
        match self {
            Scalar::Bool(b) => Some(*b),
            _ => None,
        }
    }

    /// Python's `_norm_str`: str(v).strip().lower(). We only ever norm strings
    /// (string-typed conditions), so this is defined for the string case; for
    /// robustness we render other scalars the way Python's str() would for the
    /// shapes that actually occur, but string conditions only compare strings.
    pub fn norm_str(&self) -> String {
        match self {
            Scalar::Str(s) => s.trim().to_lowercase(),
            Scalar::Bool(b) => if *b { "true".into() } else { "false".into() },
            Scalar::Int(i) => i.to_string(),
            Scalar::Float(f) => f.to_string(),
        }
    }
}

/// A condition's declared value: a scalar, OR a list of scalars for in/not_in.
#[derive(Debug, Clone, Deserialize)]
#[serde(untagged)]
pub enum CondValue {
    List(Vec<Scalar>),
    One(Scalar),
}

#[derive(Debug, Clone, Deserialize)]
pub struct Condition {
    pub field: String,
    pub operator: String,
    pub value: CondValue,
    pub value_type: String, // "number" | "string" | "boolean"
}

#[derive(Debug, Clone, Deserialize)]
pub struct Effect {
    pub kind: String, // "approve" | "deny" | "route" | "escalate"
    pub action: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Authority {
    #[serde(default)]
    pub approval_required: bool,
    #[serde(default)]
    pub approver_role: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Policy {
    pub id: String,
    pub workflow: String,
    pub effect: Effect,
    pub priority: i64,
    #[serde(default)]
    pub conditions: Vec<Condition>,
    #[serde(default)]
    pub authority: Authority,
    #[serde(default)]
    pub overrides: Vec<String>,
}

impl Policy {
    /// Python `Policy.specificity` == number of conditions.
    pub fn specificity(&self) -> usize {
        self.conditions.len()
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct FactSpec {
    pub name: String,
    pub value_type: String,
    #[serde(default)]
    pub default: Option<Scalar>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WorkflowSpec {
    pub name: String,
    #[serde(default)]
    pub facts: Vec<FactSpec>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Bundle {
    #[serde(default)]
    pub workflows: Vec<WorkflowSpec>,
    #[serde(default)]
    pub policies: Vec<Policy>,
}

impl Bundle {
    pub fn workflow(&self, name: &str) -> Option<&WorkflowSpec> {
        self.workflows.iter().find(|w| w.name == name)
    }

    pub fn policies_for(&self, workflow: &str) -> Vec<&Policy> {
        // Same order Python yields: source order, filtered by workflow.
        self.policies.iter().filter(|p| p.workflow == workflow).collect()
    }
}
