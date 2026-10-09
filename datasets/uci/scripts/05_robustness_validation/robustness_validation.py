"""Step 5: validate robustness and assess model-specific predictive importance."""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import pandas as pd
from threadpoolctl import threadpool_limits
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
for stage in ("02_data_cleaning", "03_feature_extraction", "04_outcome_analysis"):
    sys.path.insert(0, str(ROOT / "scripts" / stage))

from outcome_analysis import SOURCE, load_features
from prediction_models import FEATURES, FEATURE_GROUPS, fit_comparison
from sensitivity_analysis import RAW_SOURCE, run_sensitivities
from uncertainty_importance import bootstrap_metrics, individual_importance, grouped_importance, subgroup_metrics


REPORT_DIR = ROOT / "reports" / "05_robustness_validation"
PREVIOUS_REPORT = ROOT / "reports" / "04_outcome_analysis"
BOOTSTRAP_REPETITIONS = 200
PERMUTATION_REPETITIONS = 5
PREDICTIONS_FILENAME = "held_out_predictions.csv"


def input_fingerprints():
    paths = [SOURCE, RAW_SOURCE, PREVIOUS_REPORT / "analysis_summary.json", PREVIOUS_REPORT / PREDICTIONS_FILENAME, PREVIOUS_REPORT / "adjusted_odds_ratios.csv"]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def save_importance_plot(importance):
    figure, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for axis, name in zip(axes, ("expanded_logistic", "hist_gradient_boosting")):
        selected = importance.loc[(importance["model"] == name) & (importance["metric"] == "average_precision")]
        selected = selected.nlargest(10, "mean_score_drop").sort_values("mean_score_drop")
        axis.barh(selected["feature"], selected["mean_score_drop"], xerr=selected["permutation_sd"], color="#23786d", capsize=2)
        axis.axvline(0, color="gray", linewidth=1)
        axis.set(title=name.replace("_", " "), xlabel="Average-precision drop after permutation")
    figure.savefig(REPORT_DIR / "predictive_importance.png", dpi=160)
    plt.close(figure)


def run_validation():
    fingerprints = input_fingerprints()
    previous_summary = json.loads((PREVIOUS_REPORT / "analysis_summary.json").read_text(encoding="utf-8"))
    if previous_summary["input_sha256"] != hashlib.sha256(SOURCE.read_bytes()).hexdigest():
        raise ValueError("Step 4 results refer to different feature data; rerun that stage first.")
    frame = load_features()
    previous_predictions = pd.read_csv(PREVIOUS_REPORT / PREDICTIONS_FILENAME, dtype={"encounter_id": str, "patient_nbr": str})
    baseline_odds = pd.read_csv(PREVIOUS_REPORT / "adjusted_odds_ratios.csv")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    print("1/5: Comparing fixed models on held-out patients...", flush=True)
    models, test, predictors, predictions, metrics, split = fit_comparison(frame, previous_predictions)
    metrics.to_csv(REPORT_DIR / "model_comparison.csv", index=False)
    predictions.to_csv(REPORT_DIR / PREDICTIONS_FILENAME, index=False)
    print("2/5: Bootstrapping whole held-out patients...", flush=True)
    intervals, differences = bootstrap_metrics(predictions, BOOTSTRAP_REPETITIONS)
    intervals.to_csv(REPORT_DIR / "bootstrap_intervals.csv", index=False)
    differences.to_csv(REPORT_DIR / "paired_model_differences.csv", index=False)
    print("3/5: Measuring single-predictor and grouped predictive importance...", flush=True)
    importance = individual_importance(models, predictors, test["readmitted_30d"], PERMUTATION_REPETITIONS)
    groups = grouped_importance(models, predictors, test["readmitted_30d"], PERMUTATION_REPETITIONS)
    importance.to_csv(REPORT_DIR / "predictive_importance.csv", index=False)
    groups.to_csv(REPORT_DIR / "grouped_importance.csv", index=False)
    subgroup_metrics(test, predictions).to_csv(REPORT_DIR / "subgroup_performance.csv", index=False)
    print("4/5: Checking adjusted-model and cohort sensitivity...", flush=True)
    sensitivity, scenarios = run_sensitivities(frame, baseline_odds)
    sensitivity.to_csv(REPORT_DIR / "sensitivity_odds_ratios.csv", index=False)
    if input_fingerprints() != fingerprints:
        raise ValueError("An input or previous result changed during validation.")
    summary = {
        "input_fingerprints": fingerprints, "split": split,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "permutation_repetitions": PERMUTATION_REPETITIONS,
        "predictors": FEATURES, "feature_groups": FEATURE_GROUPS,
        "model_settings": {name: model.named_steps["classifier"].get_params() for name, model in models.items()},
        "sensitivity_scenarios": scenarios,
        "package_versions": {name: importlib.metadata.version(name) for name in (
            "pandas", "numpy", "scipy", "statsmodels", "scikit-learn", "matplotlib", "threadpoolctl"
        )},
    }
    with (REPORT_DIR / "validation_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, allow_nan=False)
    print("5/5: Saving importance plots...", flush=True)
    save_importance_plot(importance)
    print(metrics.to_string(index=False))
    print(f"Validation outputs: {REPORT_DIR}")


def main():
    with threadpool_limits(limits=2):
        run_validation()


if __name__ == "__main__":
    main()