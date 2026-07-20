//! Kernl edge evaluator — the reflexive decision function as a stateless Rust
//! library + binary (arc Part 11: "the reflexive evaluator ships as a stateless
//! sidecar/binary that runs inside the customer's infrastructure").
//!
//! This is an OUTCOME-EXACT port of backend/runtime/evaluator.py. It is NOT the
//! authority on its own: the Python evaluator remains the reference for V1, and
//! the differential-test harness proves this crate agrees with it. The endgame
//! (arc V6) is a verified reference evaluator with continuous differential
//! testing against this production Rust evaluator; this crate is that
//! evaluator's first, test-anchored incarnation.

pub mod eval;
pub mod schema;

pub use eval::{evaluate, Decision, EvalError, Outcome, Precedence};
pub use schema::{Bundle, Scalar};

use serde::Deserialize;
use std::collections::HashMap;

/// The stdin request shape the CLI and harness use: the same three inputs the
/// Python `evaluate(facts, bundle, workflow)` takes.
#[derive(Debug, Deserialize)]
pub struct EvalRequest {
    pub facts: HashMap<String, Scalar>,
    pub bundle: Bundle,
    pub workflow: String,
}

/// Evaluate a parsed request, returning either the decision or a structured
/// error (matching Python's error semantics: unknown workflow / invalid facts).
pub fn run(req: &EvalRequest) -> Result<Decision, EvalError> {
    evaluate(&req.facts, &req.bundle, &req.workflow)
}
