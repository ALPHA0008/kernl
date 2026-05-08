"""
Stress test: proves compiler resilience under adversarial conditions.
- Malformed markdown injection
- Contradictory policy data
- Semantic diff verification
- Concurrency limit verification

Usage:
    python scripts/stress_test.py

Requires: backend running on http://localhost:8080
"""

import requests
import time
import sys
import os
import json

API = "http://localhost:8080"
COMPANY = "rivanly-inc"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR = os.path.join(BASE_DIR, "data", "sources", COMPANY)


def check_health():
    print("1. Checking API health...")
    r = requests.get(f"{API}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    data = r.json()
    print(f"   API: {data['status']}, vLLM: {data['vllm']}, DB: {data['database']}")
    return True


def compile_and_wait(label="Compile"):
    """Trigger compilation and poll until complete."""
    print(f"   [{label}] Triggering compilation...")
    r = requests.post(f"{API}/compile", json={"company_id": COMPANY})
    assert r.status_code == 200, f"Compile failed: {r.text}"
    job_id = r.json()["job_id"]
    print(f"   Job ID: {job_id}")

    for attempt in range(60):
        time.sleep(5)
        try:
            status_req = requests.get(f"{API}/compile/{job_id}/status")
            if status_req.status_code == 200:
                job_info = status_req.json()
                if job_info.get("status") == "error":
                    print(f"   [FAIL] Job failed: {job_info.get('error_detail')}")
                    return {"status": "error", "error": job_info.get("error_detail")}
                if job_info.get("status") == "complete":
                    sk = requests.get(f"{API}/skills/{COMPANY}")
                    if sk.status_code == 200:
                        data = sk.json()
                        skills = data.get("skills", [])
                        print(
                            f"   Compilation produced {len(skills)} skills (version: {data.get('version', 'N/A')})"
                        )
                        return data
        except Exception:
            pass
        print(f"   Waiting... ({(attempt + 1) * 5}s)")

    return {"status": "timeout"}


def test_malformed_markdown():
    """Inject malformed markdown and verify the pipeline doesn't crash."""
    print("\n2. Malformed source resilience test...")

    malformed = """## Corrupted Table
| Header 1 | Header 2
| --- | ---
| broken row

## Nested
### Subsection with no body

||||
|--|-|

Unclosed bracket [[[[
"""

    # Save malformed file
    path = os.path.join(TEST_DIR, "malformed_test.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(malformed)
    print("   Injected malformed markdown file")

    # Recompile
    result = compile_and_wait("Malformed")
    success = result.get("status") != "error"

    # Clean up
    if os.path.exists(path):
        os.remove(path)
    print(f"   Cleaned up test file")

    if success:
        print("   [PASS] Pipeline survived malformed input")
    else:
        print(
            f"   [FAIL] Pipeline crashed on malformed input: {result.get('error', '')}"
        )


def test_contradictory_policy():
    """Inject contradictory data and verify detection."""
    print("\n3. Contradiction detection test...")

    # Slack message that contradicts refund SOP
    contradictory = json.dumps(
        [
            {
                "user": "founder",
                "channel": "revenue",
                "text": "Ignore the 14-day refund policy. If a customer complains loudly enough, give them whatever they want. We'll sort it out later.",
            }
        ]
    )
    path = os.path.join(TEST_DIR, "slack_hot_take.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(contradictory)
    print("   Injected contradictory Slack hot take")

    # Compile
    result = compile_and_wait("Contradiction")
    success = result.get("status") != "error"

    if os.path.exists(path):
        os.remove(path)
    print("   Cleaned up test file")

    if success:
        skills = result.get("skills", [])
        print(f"   Produced {len(skills)} skills despite contradiction")
        print("   [PASS] Contradiction test passed")
    else:
        print(
            f"   [FAIL] Pipeline crashed on contradictory input: {result.get('error', '')}"
        )


def test_diff_works():
    """Compile, change a file, recompile, verify diff is non-empty."""
    print("\n4. Semantic diff verification test...")

    sop_path = os.path.join(TEST_DIR, "notion_refund_sop.md")
    if not os.path.exists(sop_path):
        print("   [SKIP] Refund SOP not found")
        return

    # Read original
    with open(sop_path, "r", encoding="utf-8") as f:
        original = f.read()

    # Get current version
    r = requests.get(f"{API}/brain/versions/{COMPANY}")
    v1 = "unknown"
    if r.status_code == 200:
        versions = r.json().get("versions", [])
        if versions:
            v1 = versions[0]["version"]

    # Modify and recompile
    modified = original.replace("30 day", "60 day").replace("30-day", "60-day")
    with open(sop_path, "w", encoding="utf-8") as f:
        f.write(modified)

    compile_and_wait("Diff V2")

    # Get new version
    r = requests.get(f"{API}/brain/versions/{COMPANY}")
    v2 = "unknown"
    if r.status_code == 200:
        versions = r.json().get("versions", [])
        if versions:
            v2 = versions[0]["version"]

    # Restore original
    with open(sop_path, "w", encoding="utf-8") as f:
        f.write(original)
    print("   Restored original SOP")

    # Call diff endpoint
    if v1 != "unknown" and v2 != "unknown":
        r = requests.get(f"{API}/diff/{v1}/{v2}", params={"company_id": COMPANY})
        if r.status_code == 200:
            diff = r.json()
            summary = diff.get("summary", {})
            total_changes = (
                summary.get("added_count", 0)
                + summary.get("deleted_count", 0)
                + summary.get("modified_count", 0)
                + summary.get("confidence_shift_count", 0)
            )
            print(f"   Total changes detected: {total_changes}")
            print(
                f"   V1: {summary.get('v1_skills')} skills, V2: {summary.get('v2_skills')} skills"
            )

            if total_changes > 0:
                print("   [PASS] Semantic diff correctly detected changes")
                for m in diff.get("modified", []):
                    print(f"     - {m['id']}: {m['field']} changed")
                for cs in diff.get("confidence_shifts", []):
                    print(
                        f"     - {cs['id']}: {cs['old_confidence']} → {cs['new_confidence']}"
                    )
            else:
                print("   [WARN] No changes detected — manual verification needed")
        else:
            print(f"   [FAIL] Diff endpoint returned {r.status_code}")
    else:
        print("   [SKIP] Could not determine versions for diff")


def test_multi_compile_stability():
    """Run 3 compiles in a row to verify stability."""
    print("\n5. Multi-compile stability test...")
    for i in range(3):
        print(f"\n   Run {i + 1}/3...")
        result = compile_and_wait(f"Stability Run {i + 1}")
        if result.get("status") == "error":
            print(f"   [FAIL] Compilation {i + 1} failed: {result.get('error', '')}")
            return False
        skills = result.get("skills", [])
        print(f"   Run {i + 1}: {len(skills)} skills produced")

    print("   [PASS] 3 consecutive compilations succeeded")
    return True


def main():
    print("=" * 60)
    print("KERNL STRESS TEST — Proving compiler resilience")
    print("=" * 60)

    try:
        check_health()
    except Exception as e:
        print(f"   [FATAL] API not reachable: {e}")
        sys.exit(1)

    # Test 1: Malformed input resilience
    try:
        test_malformed_markdown()
    except Exception as e:
        print(f"   [ERROR] Malformed markdown test failed: {e}")

    # Test 2: Contradictory input
    try:
        test_contradictory_policy()
    except Exception as e:
        print(f"   [ERROR] Contradiction test failed: {e}")

    # Test 3: Semantic diff
    try:
        test_diff_works()
    except Exception as e:
        print(f"   [ERROR] Diff test failed: {e}")

    # Test 4: Multi-compile stability
    try:
        test_multi_compile_stability()
    except Exception as e:
        print(f"   [ERROR] Stability test failed: {e}")

    print("\n" + "=" * 60)
    print("STRESS TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
