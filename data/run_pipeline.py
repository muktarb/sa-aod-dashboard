"""One-command data pipeline: ref table -> episodes -> cube (+ map files)."""
import subprocess, sys
for s in ("build_diagnosis_ref.py", "generate_episodes.py", "aggregate.py"):
    print(f"\n=== {s} ===")
    subprocess.run([sys.executable, s], check=True)
