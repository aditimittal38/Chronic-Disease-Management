"""Run the diabetes analysis stages with one interpreter and a recorded run log."""

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUN_LOG = ROOT / "reports" / "pipeline_run.json"
DATA_DIR = ROOT / "data" / "raw"
PACKAGES = {
    "pandas": "pandas", "numpy": "numpy", "scipy": "scipy",
    "statsmodels": "statsmodels", "scikit-learn": "sklearn",
    "matplotlib": "matplotlib", "threadpoolctl": "threadpoolctl",
}
STAGES = (
    ("Dataset audit", "scripts/01_data_audit/data_audit.py"),
    ("Data cleaning", "scripts/02_data_cleaning/data_cleaning.py"),
    ("Feature extraction", "scripts/03_feature_extraction/feature_extraction.py"),
    ("Outcome analysis", "scripts/04_outcome_analysis/outcome_analysis.py"),
    ("Robustness and importance", "scripts/05_robustness_validation/robustness_validation.py"),
)


def raw_fingerprints():
    files = (DATA_DIR / "diabetic_data.csv", DATA_DIR / "IDS_mapping.csv")
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def check_environment():
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or later is required; Python 3.13.14 on Windows is the validated setup.")
    missing = [package for package, module in PACKAGES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise RuntimeError(f"Missing dependencies: {', '.join(missing)}. Install requirements-lock.txt with this interpreter first.")


def package_versions():
    versions = {}
    for package in PACKAGES:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not installed"
    return versions


def workflow_commands():
    tests = ["-m", "unittest", "discover", "-s", "scripts/05_robustness_validation", "-p", "test_validation.py", "-v"]
    return [("Method regression checks", tests)] + [(name, [str(ROOT / script)]) for name, script in STAGES]


def execute_workflow(manifest):
    commands = workflow_commands()
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    for position, (name, arguments) in enumerate(commands, start=1):
        command = [sys.executable, *arguments]
        record = {"name": name, "command": command, "status": "running"}
        manifest["steps"].append(record)
        print(f"\n[{position}/{len(commands)}] {name}", flush=True)
        started = time.perf_counter()
        try:
            subprocess.run(command, cwd=ROOT, env=environment, check=True)
        except subprocess.CalledProcessError:
            record["status"] = "failed"
            raise
        record["status"] = "passed"
        record["duration_seconds"] = round(time.perf_counter() - started, 2)


def main():
    manifest = {
        "mode": "full_workflow",
        "started_utc": datetime.now(timezone.utc).isoformat(), "status": "running",
        "interpreter": sys.executable, "python_version": platform.python_version(),
        "platform": platform.platform(), "package_versions": package_versions(), "steps": [],
    }
    exit_code = 0
    try:
        check_environment()
        manifest["raw_inputs_before"] = raw_fingerprints()
        execute_workflow(manifest)
        manifest["raw_inputs_after"] = raw_fingerprints()
        if manifest["raw_inputs_before"] != manifest["raw_inputs_after"]:
            raise RuntimeError("An original dataset file changed during the workflow.")
        manifest["status"] = "passed"
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        exit_code = 1
        print(f"Workflow stopped: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        exit_code = 130
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    RUN_LOG.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if not exit_code:
        print("\nCompleted. CSV, JSON, and plot outputs updated; Markdown reports are maintained snapshots.")
        print(f"Run record: {RUN_LOG}")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()