"""Step 4: descriptive associations, adjusted regression, and grouped evaluation."""

import hashlib
import importlib.metadata
import json
from pathlib import Path

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from adjusted_model import fit_adjusted_model, evaluate_model, MODEL_FORMULA
from descriptive_analysis import descriptive_tables


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "processed" / "diabetes_features.csv"
REPORT_DIR = ROOT / "reports" / "04_outcome_analysis"
NUMERIC_COLUMNS = (
    "number_inpatient", "number_emergency", "number_outpatient", "num_medications",
    "number_diagnoses", "time_in_hospital", "num_lab_procedures", "num_procedures",
    "readmitted_30d", "medication_changed", "any_drug_dose_changed",
)
MODEL_CATEGORIES = {
    "age_group": ["Under 40", "40-59", "60-79", "80+"],
    "race": ["Caucasian", "AfricanAmerican", "Asian", "Hispanic", "Other", "Unknown"],
    "diag_1_group": ["Other", "Diabetes", "Circulatory", "Respiratory", "Unknown"],
    "insulin": ["No", "Steady", "Up", "Down"],
    "A1Cresult": ["None", "Norm", ">7", ">8"],
}


def load_features():
    if not SOURCE.exists():
        raise FileNotFoundError("Run scripts/03_feature_extraction/feature_extraction.py first.")
    frame = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    if frame.empty or frame["encounter_id"].duplicated().any():
        raise ValueError("Feature data must contain unique encounters.")
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    expected_target = frame["readmitted"].eq("<30").astype(int)
    if not frame["readmitted"].isin(["<30", ">30", "NO"]).all():
        raise ValueError("Unrecognized original outcome label.")
    if not frame["readmitted_30d"].equals(expected_target):
        raise ValueError("The binary target disagrees with recorded readmission.")
    for column, categories in MODEL_CATEGORIES.items():
        if not frame[column].isin(categories).all():
            raise ValueError(f"Unexpected model category in {column}.")
        frame[column] = pd.Categorical(frame[column], categories=categories)
    frame["inpatient_history_band"] = frame["number_inpatient"].clip(upper=2).map({0: "0", 1: "1", 2: "2+"})
    return frame


def save_plots(rates, calibration, curves):
    figure, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    for axis, variable in zip(axes, ("inpatient_history_band", "medication_burden_band", "age_group")):
        groups = rates.loc[rates["variable"] == variable]
        if variable == "medication_burden_band":
            groups = groups.set_index("category").loc[["Low", "Moderate", "High"]].reset_index()
        errors = [groups["readmission_percent"] - groups["cluster_ci_low_percent"], groups["cluster_ci_high_percent"] - groups["readmission_percent"]]
        axis.bar(groups["category"], groups["readmission_percent"], yerr=errors, capsize=3, color="#23786d")
        axis.set(title=variable.replace("_", " "), ylabel="Early readmission (%)")
        axis.set_ylim(bottom=0)
    figure.savefig(REPORT_DIR / "readmission_patterns.png", dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    axes[0].plot(curves["false_positive"], curves["true_positive"], color="#23786d")
    axes[0].plot([0, 1], [0, 1], "--", color="gray")
    axes[0].set(title="Held-out ROC", xlabel="False-positive rate", ylabel="True-positive rate")
    axes[1].plot(curves["recall"], curves["precision"], color="#23786d")
    axes[1].set(title="Held-out precision-recall", xlabel="Recall", ylabel="Precision")
    axes[2].plot(calibration["mean_predicted_probability"], calibration["observed_readmission_rate"], "o-", color="#23786d")
    axes[2].plot([0, 1], [0, 1], "--", color="gray")
    axes[2].set(title="Held-out calibration", xlabel="Mean predicted probability", ylabel="Observed readmission rate")
    figure.savefig(REPORT_DIR / "model_evaluation.png", dpi=160)
    plt.close(figure)


def main():
    frame = load_features()
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    print("1/4: Summarizing rates and patient-separated exploratory tests...", flush=True)
    rates, numeric, tests, sampled_patients = descriptive_tables(frame)
    rates.to_csv(REPORT_DIR / "readmission_rates.csv", index=False)
    numeric.to_csv(REPORT_DIR / "numeric_comparisons.csv", index=False)
    tests.to_csv(REPORT_DIR / "exploratory_tests.csv", index=False)
    print("2/4: Fitting the adjusted model with patient-clustered standard errors...", flush=True)
    result, odds, terms = fit_adjusted_model(frame)
    odds.to_csv(REPORT_DIR / "adjusted_odds_ratios.csv", index=False)
    terms.to_csv(REPORT_DIR / "adjusted_term_tests.csv", index=False)
    (REPORT_DIR / "model_summary.txt").write_text(result.summary().as_text(), encoding="utf-8")
    print("3/4: Evaluating on held-out patients...", flush=True)
    evaluation, predictions, calibration, curves = evaluate_model(frame)
    predictions.to_csv(REPORT_DIR / "held_out_predictions.csv", index=False)
    calibration.to_csv(REPORT_DIR / "calibration.csv", index=False)
    summary = {
        "input_file": SOURCE.relative_to(ROOT).as_posix(), "input_sha256": source_hash,
        "encounters": len(frame), "patients": frame["patient_nbr"].nunique(),
        "early_readmissions": int(frame["readmitted_30d"].sum()),
        "early_readmission_percent": float(100 * frame["readmitted_30d"].mean()),
        "exploratory_test_patients": sampled_patients,
        "model_formula": MODEL_FORMULA, "clustered_by": "patient_nbr",
        "model_converged": bool(result.converged),
        "mcfadden_pseudo_r_squared": float(1 - result.llf / result.llnull),
        "evaluation": evaluation,
        "package_versions": {name: importlib.metadata.version(name) for name in (
            "pandas", "numpy", "scipy", "statsmodels", "scikit-learn", "matplotlib"
        )},
    }
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != source_hash:
        raise ValueError("The feature data changed during analysis.")
    with (REPORT_DIR / "analysis_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, allow_nan=False)
    print("4/4: Saving analysis plots...", flush=True)
    save_plots(rates, calibration, curves)
    print(f"Analyzed {len(frame):,} encounters; model converged: {result.converged}")
    print(f"Held-out ROC-AUC: {evaluation['roc_auc']:.3f}; average precision: {evaluation['average_precision']:.3f}")
    print(f"Analysis outputs: {REPORT_DIR}")


if __name__ == "__main__":
    main()