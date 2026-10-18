#!/usr/bin/env python3
"""Build course-uploadable ZIPs without putting generated archives in Git."""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "dist" / "submissions"
FILES = ("bot.py", "referee.py", "GPL-2.0.txt")
sys.path.insert(0, str(ROOT.parent / "evals"))
from catalog import load_policies  # noqa: E402


def main() -> None:
    policies = [policy for policy in load_policies() if policy.get("status") == "ready" and policy.get("run_sh")]
    if not policies:
        raise SystemExit("No ready submission archives are stored in D1")
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for policy in policies:
        script = policy["run_sh"] if policy["run_sh"].endswith("\n") else policy["run_sh"] + "\n"
        archive = OUT / policy["archive_name"]
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for filename in FILES:
                bundle.write(ROOT / filename, filename)
            bundle.writestr("run.sh", script)
            if policy.get("build_sh"):
                bundle.writestr("build.sh", policy["build_sh"] if policy["build_sh"].endswith("\n") else policy["build_sh"] + "\n")
    print(f"built {len(policies)} archives in {OUT}")


if __name__ == "__main__":
    main()
