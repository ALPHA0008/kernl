import subprocess, sys, os

script = r"""
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(override=True)

from backend.tests.eval_harness import run_eval
import json

async def main():
    result = await run_eval()
    out_path = os.path.join(os.path.dirname(__file__), 'tests', 'eval_results_baseline.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f'\nResults saved -> {out_path}')
    print(f'Strict: {result["strict_accuracy_pct"]}%  Relaxed: {result["relaxed_accuracy_pct"]}%')

asyncio.run(main())
"""

with open("run_eval_background.py", "w") as f:
    f.write(script)

print("Starting eval in background...")
subprocess.Popen(
    [sys.executable, "run_eval_background.py"],
    stdout=open("eval_output.log", "w"),
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
)
print("PID:", subprocess.Popen.pid if hasattr(subprocess.Popen, "pid") else "started")
print("Check progress: type 'progress' to see status")
