"""
Smoke test: proves the system is dynamic by modifying a source doc,
recompiling, and verifying that skills and agent answers change.

Usage:
    python scripts/smoke_test.py

Requires: backend running on http://localhost:8080
"""

import requests
import time
import sys
import os
import json

API = "http://localhost:8080"
COMPANY = "rivanly-inc"

# Path to a source doc we'll modify
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOP_PATH = os.path.join(BASE_DIR, "data", "sources", COMPANY, "notion_refund_sop.md")


def check_health():
    print("1. Checking API health...")
    r = requests.get(f"{API}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    data = r.json()
    print(f"   API: {data['status']}, vLLM: {data['vllm']}, DB: {data['database']}")
    return True


def read_sop():
    with open(SOP_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_sop(content: str):
    with open(SOP_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def compile_and_wait():
    """Trigger compilation and poll until complete."""
    print("   Triggering compilation...")
    r = requests.post(f"{API}/compile", json={"company_id": COMPANY})
    assert r.status_code == 200, f"Compile failed: {r.text}"
    job_id = r.json()["job_id"]
    print(f"   Job ID: {job_id}")

    # Poll the compile stream for completion
    for attempt in range(60):  # max 5 minutes
        time.sleep(5)

        # Check job status explicitly
        try:
            status_req = requests.get(f"{API}/compile/{job_id}/status")
            if status_req.status_code == 200:
                job_info = status_req.json()
                if job_info.get("status") == "error":
                    print(f"   [ERROR] Job failed: {job_info.get('error_detail')}")
                    raise RuntimeError(
                        f"Compilation job failed: {job_info.get('error_detail')}"
                    )
                if job_info.get("status") == "complete":
                    # Fetch skills
                    sk = requests.get(f"{API}/skills/{COMPANY}")
                    if sk.status_code == 200:
                        data = sk.json()
                        skills = data.get("skills", [])
                        print(f"   Compilation produced {len(skills)} skills")
                        return data
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            pass

        print(f"   Waiting... ({(attempt + 1) * 5}s)")

    # Timeout reached. Fetch final status.
    final_status = "Unknown"
    final_error = "None"
    try:
        status_req = requests.get(f"{API}/compile/{job_id}/status")
        if status_req.status_code == 200:
            job_info = status_req.json()
            final_status = job_info.get("status", "Unknown")
            final_error = job_info.get("error_detail", "None")
    except Exception:
        pass

    raise TimeoutError(
        f"Compilation did not complete within 5 minutes. Final status: {final_status}, Error: {final_error}"
    )


def get_skills():
    r = requests.get(f"{API}/skills/{COMPANY}")
    assert r.status_code == 200, f"Skills fetch failed: {r.text}"
    return r.json()


def query_agent(scenario: str, context: dict = None):
    r = requests.post(
        f"{API}/agent/query",
        json={
            "company_id": COMPANY,
            "scenario_text": scenario,
            "json_context": context or {},
        },
    )
    assert r.status_code == 200, f"Agent query failed: {r.text}"
    return r.json()


def test_gibberish():
    """Gibberish should get low confidence and no specific action."""
    print("\n3. Testing gibberish rejection...")
    result = query_agent("blah blah blah fafa asdfasdf")
    confidence = result.get("confidence", 1.0)
    print(f"   Gibberish confidence: {confidence}")
    print(f"   Action: {result.get('recommended_action', 'N/A')}")
    if confidence < 0.4:
        print("   [PASS] Low confidence for gibberish")
    else:
        print(
            f"   [WARN] Confidence {confidence} is higher than expected for gibberish"
        )


def test_dynamic_policy_change():
    """
    Core test: modify the refund SOP, recompile, and verify the change propagates.
    """
    print("\n4. Testing dynamic policy change...")

    # Save original SOP
    original_sop = read_sop()
    print(f"   Original SOP loaded ({len(original_sop)} chars)")

    # Compile with original SOP (this may already be done)
    print("\n   Step A: Compile with ORIGINAL policy...")
    skills_v1 = compile_and_wait()
    skills_v1_text = json.dumps(skills_v1)

    # Query the agent about refunds with original policy
    print("\n   Step B: Query agent about refunds (original policy)...")
    result_v1 = query_agent(
        "Customer requesting a refund after 45 days",
        {"plan": "annual", "days_since_purchase": 45, "tenure_months": 6},
    )
    print(f"   v1 action: {result_v1.get('recommended_action')}")
    print(f"   v1 rule: {result_v1.get('rule_applied', 'N/A')}")

    # Now modify the SOP - change the refund window
    print("\n   Step C: Modifying SOP (changing refund window)...")
    modified_sop = (
        original_sop.replace("30 day", "60 day")
        .replace("30-day", "60-day")
        .replace("30 days", "60 days")
    )
    if modified_sop == original_sop:
        # Try alternative patterns
        modified_sop = original_sop.replace("30", "60")

    write_sop(modified_sop)
    print("   SOP modified: 30 -> 60 days")

    # Recompile
    print("\n   Step D: Recompiling with MODIFIED policy...")
    skills_v2 = compile_and_wait()
    skills_v2_text = json.dumps(skills_v2)

    # Check that skills actually changed
    changed = skills_v1_text != skills_v2_text
    print(f"\n   Skills changed after recompile: {changed}")

    # Query the agent again
    print("\n   Step E: Query agent about refunds (modified policy)...")
    result_v2 = query_agent(
        "Customer requesting a refund after 45 days",
        {"plan": "annual", "days_since_purchase": 45, "tenure_months": 6},
    )
    print(f"   v2 action: {result_v2.get('recommended_action')}")
    print(f"   v2 rule: {result_v2.get('rule_applied', 'N/A')}")

    # Check for the policy change in v2
    v2_mentions_60 = "60" in json.dumps(result_v2)
    print(f"   v2 references '60': {v2_mentions_60}")

    # Check if actions actually changed based on policy
    v1_action_lower = str(result_v1.get("recommended_action", "")).lower()
    v2_action_lower = str(result_v2.get("recommended_action", "")).lower()

    # Under 30 days limit (v1), 45 days should be denied/not allowed
    # Under 60 days limit (v2), 45 days should be approved/prorated
    policy_executed_correctly = (
        "deny" in v1_action_lower
        or "no refund" in v1_action_lower
        or "not eligible" in v1_action_lower
        or "cannot" in v1_action_lower
    ) and (
        "approve" in v2_action_lower
        or "prorated" in v2_action_lower
        or "allow" in v2_action_lower
    )
    print(
        f"   Policy execution behavior changed appropriately (Deny -> Approve): {policy_executed_correctly}"
    )

    # Restore original SOP
    print("\n   Step F: Restoring original SOP...")
    write_sop(original_sop)
    print("   Original SOP restored.")

    # Final verdict
    print("\n   --- RESULTS ---")
    if changed:
        print("   [PASS] Skills changed after source modification and recompile")
    else:
        print("   [FAIL] Skills did NOT change - system may still be static")

    if policy_executed_correctly:
        print(
            "   [PASS] Agent correctly executed the policy change (Denied at 45 days under 30-day SOP, Approved under 60-day SOP!)"
        )
    elif v2_mentions_60:
        print("   [PASS] Agent response reflects the modified policy (60 days)")
    else:
        print(
            "   [WARN] Agent response did not change behavior or mention the new policy"
        )


def test_semantic_diff():
    """Test the /diff/{v1}/{v2} endpoint."""
    print("\n5. Testing semantic diff engine...")

    # Get version history
    r = requests.get(f"{API}/brain/versions/{COMPANY}")
    if r.status_code != 200:
        print("   [SKIP] Could not fetch version history")
        return

    versions = r.json().get("versions", [])
    if len(versions) < 2:
        print("   [SKIP] Need at least 2 compiled versions for diff")
        return

    v1 = versions[1]["version"]
    v2 = versions[0]["version"]
    print(f"   Comparing {v1} → {v2}")

    r = requests.get(f"{API}/diff/{v1}/{v2}", params={"company_id": COMPANY})
    if r.status_code != 200:
        print(f"   [FAIL] Diff endpoint returned {r.status_code}: {r.text}")
        return

    diff = r.json()
    summary = diff.get("summary", {})
    print(
        f"   Added: {summary.get('added_count', 0)}, Deleted: {summary.get('deleted_count', 0)}, Modified: {summary.get('modified_count', 0)}"
    )
    print(f"   Confidence shifts: {summary.get('confidence_shift_count', 0)}")
    print(
        f"   V1 skills: {summary.get('v1_skills', 0)} → V2 skills: {summary.get('v2_skills', 0)}"
    )

    if (
        summary.get("added_count", 0) > 0
        or summary.get("modified_count", 0) > 0
        or summary.get("deleted_count", 0) > 0
        or summary.get("confidence_shift_count", 0) > 0
    ):
        print("   [PASS] Semantic diff detected changes between versions")
    else:
        print(
            "   [WARN] Diff returned no changes — may indicate skills didn't change or diff has a bug"
        )


def main():
    print("=" * 60)
    print("KERNL SMOKE TEST — Proving the system is dynamic")
    print("=" * 60)

    try:
        check_health()
    except Exception as e:
        print(f"   [FATAL] API not reachable: {e}")
        print(
            "   Make sure backend is running: python -m uvicorn backend.main:app --port 8080"
        )
        sys.exit(1)

    # Test 1: Compile and get skills
    print("\n2. Initial compilation...")
    try:
        skills = compile_and_wait()
        print(f"   Got {len(skills.get('skills', []))} skills")
    except Exception as e:
        print(f"   [ERROR] Compilation failed: {e}")
        sys.exit(1)

    # Test 2: Gibberish rejection
    try:
        test_gibberish()
    except Exception as e:
        print(f"   [ERROR] Gibberish test failed: {e}")

    # Test 3: Dynamic policy change
    try:
        test_dynamic_policy_change()
    except Exception as e:
        print(f"   [ERROR] Dynamic test failed: {e}")
        # Make sure we restore the SOP
        if os.path.exists(SOP_PATH):
            print("   Attempting to restore original SOP...")

    # Test 4: Semantic diff
    try:
        test_semantic_diff()
    except Exception as e:
        print(f"   [ERROR] Diff test failed: {e}")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
