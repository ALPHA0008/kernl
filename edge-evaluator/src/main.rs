//! CLI: read one `{facts, bundle, workflow}` JSON object from stdin, print the
//! decision as JSON to stdout. Errors (unknown workflow / invalid facts) print
//! a JSON `{"error": {...}}` to stdout and exit non-zero, mirroring how the
//! Python side distinguishes request errors from decisions.
//!
//! This binary is what the differential-test harness drives, and the shape the
//! edge sidecar would expose.

use std::io::Read;

use kernl_edge_evaluator::{run, EvalError, EvalRequest};

fn main() {
    let mut input = String::new();
    if std::io::stdin().read_to_string(&mut input).is_err() {
        eprintln!("failed to read stdin");
        std::process::exit(2);
    }
    let req: EvalRequest = match serde_json::from_str(&input) {
        Ok(r) => r,
        Err(e) => {
            println!("{}", serde_json::json!({"error": {"kind": "bad_request", "detail": e.to_string()}}));
            std::process::exit(2);
        }
    };
    match run(&req) {
        Ok(decision) => {
            println!("{}", serde_json::to_string(&decision).unwrap());
        }
        Err(EvalError::UnknownWorkflow(w)) => {
            println!("{}", serde_json::json!({"error": {"kind": "unknown_workflow", "detail": w}}));
            std::process::exit(1);
        }
        Err(EvalError::InvalidFacts(d)) => {
            println!("{}", serde_json::json!({"error": {"kind": "invalid_facts", "detail": d}}));
            std::process::exit(1);
        }
    }
}
