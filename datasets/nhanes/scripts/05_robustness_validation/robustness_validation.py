"""Run NHANES specification, cohort, threshold, and missingness checks."""

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import svy


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "04_outcome_analysis"))

from outcome_analysis import load_features
from survey_methods import domain_mean, make_sample
from sensitivity_models import GAUSSIAN, prepare_sensitivity_data, run_scenarios


REPORT_DIR = ROOT / "reports" / "05_robustness_validation"
PREVIOUS_DIR = ROOT / "reports" / "04_outcome_analysis"


def evidence_hashes():
    files = [ROOT / "data" / "processed" / "nhanes_2017_2018_features.csv",
             PREVIOUS_DIR / "analysis_summary.json", PREVIOUS_DIR / "adjusted_hba1c_coefficients.csv",
             PREVIOUS_DIR / "weighted_outcomes.csv"]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def response_coverage(frame):
    data = frame.copy()
    data["hba1c_response"] = frame["LBXGH"].notna().astype(int)
    eligible = frame["RIDAGEYR"].ge(20) & frame["DIQ010"].eq(1) & frame["RIDEXPRG"].ne(1)
    eligible &= frame["WTMEC2YR"].gt(0) & frame[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)
    data["response_eligible"] = eligible.astype(int)
    estimate = make_sample(data).estimation.mean("hba1c_response", where=svy.col("response_eligible") == 1,
                                                method="taylor", drop_nulls=True).to_polars().to_dicts()[0]
    estimate.update({"eligible_examined_diagnosed_adults": int(eligible.sum()),
                     "with_hba1c": int((eligible & frame["LBXGH"].notna()).sum()),
                     "without_hba1c": int((eligible & frame["LBXGH"].isna()).sum()),
                     "note": "Examination-weighted response coverage, not a nonresponse correction or complete population estimate"})
    return pd.DataFrame([estimate])


def complete_case_composition(frame):
    data = prepare_sensitivity_data(frame)
    sample = make_sample(data)
    rows = []
    variables = ("LBXGH", "RIDAGEYR", "BMXBMI", "INDFMPIR", "insulin_use", "oral_diabetes_med_use")
    for complete, label in ((1, "Original model complete cases"), (0, "Excluded for missing predictors")):
        for variable in variables:
            result = domain_mean(sample, outcome=variable, extra_condition=svy.col("model_domain") == complete)
            rows.append({"group": label, "variable": variable,
                         "group_sample_size": int((data["analysis_domain"].eq(1) & data["model_domain"].eq(complete)).sum()),
                         "note": "Descriptive composition; available values vary by variable; not a formal contrast test", **result})
    return pd.DataFrame(rows)


def baseline_table():
    baseline = pd.read_csv(PREVIOUS_DIR / "adjusted_hba1c_coefficients.csv").drop(columns="unit")
    baseline["scenario"] = "initial_adjustment"
    baseline["family"] = GAUSSIAN
    baseline["outcome"] = "LBXGH"
    for column in ("odds_ratio", "or_ci_low", "or_ci_high"):
        baseline[column] = np.nan
    return baseline


def stability_table(coefficients):
    gaussian = coefficients.loc[coefficients["family"].eq(GAUSSIAN)]
    rows = []
    for term in ("insulin_use", "oral_diabetes_med_use", "poverty_ratio", "age_per_10_years"):
        selected = gaussian.loc[gaussian["term"].eq(term)]
        rows.append({
            "parameter": term, "scenarios_with_parameter": len(selected),
            "minimum_coefficient": float(selected["estimate"].min()), "maximum_coefficient": float(selected["estimate"].max()),
            "all_coefficients_positive": bool(selected["estimate"].gt(0).all()),
            "all_coefficients_negative": bool(selected["estimate"].lt(0).all()),
            "individual_95pct_intervals_excluding_zero": int((selected["conf_low"].gt(0) | selected["conf_high"].lt(0)).sum()),
            "within_scenario_fdr_p_below_005": int(selected["fdr_adjusted_p"].lt(0.05).sum()),
        })
    return pd.DataFrame(rows)


def save_plot(coefficients):
    selected = coefficients.loc[coefficients["family"].eq(GAUSSIAN)]
    figure, axes = plt.subplots(1, 2, figsize=(14, 5), constrained_layout=True)
    for axis, parameter in zip(axes, ("insulin_use", "oral_diabetes_med_use")):
        rows = selected.loc[selected["term"].eq(parameter)]
        errors = [rows["estimate"] - rows["conf_low"], rows["conf_high"] - rows["estimate"]]
        axis.errorbar(rows["estimate"], rows["scenario"], xerr=errors, fmt="o", capsize=3, color="#23786d")
        axis.axvline(0, linestyle="--", color="gray")
        axis.set(title=parameter.replace("_", " "), xlabel="Adjusted HbA1c percentage-point association")
    figure.savefig(REPORT_DIR / "sensitivity_associations.png", dpi=160)
    plt.close(figure)


def main():
    fingerprints = evidence_hashes()
    frame, feature_record, _ = load_features()
    previous = json.loads((PREVIOUS_DIR / "analysis_summary.json").read_text())
    if previous["input_sha256"] != feature_record["output_sha256"]:
        raise ValueError("The initial analysis belongs to different feature data.")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    print("1/3: Describing outcome response and complete-case composition...", flush=True)
    coverage = response_coverage(frame)
    composition = complete_case_composition(frame)
    coverage.to_csv(REPORT_DIR / "hba1c_response_coverage.csv", index=False)
    composition.to_csv(REPORT_DIR / "complete_case_composition.csv", index=False)
    print("2/3: Fitting fixed alternative models with full-design covariance...", flush=True)
    alternatives, scenarios, _ = run_scenarios(frame)
    coefficients = pd.concat([baseline_table(), alternatives], ignore_index=True)
    coefficients.to_csv(REPORT_DIR / "sensitivity_coefficients.csv", index=False)
    pd.DataFrame([{key: value for key, value in scenario.items() if key != "predictors"} for scenario in scenarios]).to_csv(REPORT_DIR / "scenario_inventory.csv", index=False)
    stability = stability_table(coefficients)
    stability.to_csv(REPORT_DIR / "coefficient_stability.csv", index=False)
    if evidence_hashes() != fingerprints:
        raise ValueError("Original analysis or feature data changed during sensitivity checks.")
    summary = {
        "cycle": "2017-2018", "universe_participants": len(frame), "analysis_domain": int(frame["analysis_domain"].sum()),
        "initial_complete_cases": previous["model_complete_cases"], "initial_residual_survey_df": previous["model_residual_survey_df"],
        "alternative_models": len(scenarios), "scenarios": scenarios, "input_fingerprints": fingerprints,
        "package_versions": {name: importlib.metadata.version(name) for name in ("svy", "svy-rs", "pandas", "numpy", "scipy", "statsmodels")},
        "notes": [
            "Fixed exploratory sensitivity specifications; not selection of a final model using p-values.",
            "All models use MEC weights, strata and PSUs; full-universe where-domain inference is retained.",
            "Reduced same-case model isolates adjustment changes from complete-case sample changes.",
            "Top-code flags permit separate shifts for age 80+ and poverty ratio 5+ without inventing actual values.",
            "Omitting income increases completeness but removes socioeconomic adjustment; not a remedy for missingness.",
            "Secondary logit models use original complete cases; their log-odds/ORs are not comparable to Gaussian percentage-point effects.",
            "FDR is computed within each model, not across all sensitivity scenarios; this is not confirmatory testing.",
            "Response coverage and composition tables do not adjust item nonresponse or establish missing-at-random assumptions.",
            "No imputation, prediction validation, external evaluation, or causal treatment effects are established.",
        ],
    }
    (REPORT_DIR / "validation_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("3/3: Saving sensitivity plots...", flush=True)
    save_plot(coefficients)
    print(pd.DataFrame([{key: value for key, value in scenario.items() if key in ("scenario", "model_participants", "residual_survey_df")} for scenario in scenarios]).to_string(index=False))
    print(stability.to_string(index=False))
    print(f"Robustness outputs: {REPORT_DIR}")


if __name__ == "__main__":
    main()