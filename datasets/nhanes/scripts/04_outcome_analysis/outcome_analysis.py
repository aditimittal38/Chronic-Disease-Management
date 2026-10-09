"""Survey-aware descriptive and adjusted HbA1c analysis with CSV outputs."""

import hashlib
import importlib.metadata
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import svy

from survey_methods import (
    DESIGN_FIELDS, MODEL_PREDICTORS, SOURCE_PREDICTORS,
    domain_mean, domain_proportion, fit_adjusted_model, make_sample,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "04_outcome_analysis"
GROUP_VARIABLES = (
    "age_group", "bmi_group", "poverty_ratio_group", "education_group",
    "insulin_use", "oral_diabetes_med_use", "usual_diabetes_professional",
    "a1c_test_past_year", "activity_at_least_150_equivalent_minutes", "RIAGENDR", "RIDRETH3",
)
MODEL_UNITS = {
    "_intercept_": "Model intercept, not a clinical baseline risk",
    "age_per_10_years": "Per 10 recorded years; ages 80+ are top-coded",
    "female": "Female versus male recorded category",
    "bmi_per_5_units": "Per 5 BMI units",
    "poverty_ratio": "Per unit of income-to-poverty ratio; 5 is top-coded",
    "insulin_use": "Reported insulin use versus no use",
    "oral_diabetes_med_use": "Reported diabetic pill use versus no use",
    "usual_diabetes_professional": "Usual diabetes professional versus none",
    "a1c_test_past_year": "Reported past-year A1C test versus no test",
    "log1p_glucose_checks": "Per unit of log(1 + daily-equivalent glucose checks)",
    "log1p_activity_equivalents": "Per unit of log(1 + weekly moderate-equivalent activity minutes)",
}


def load_features():
    feature_record = json.loads((ROOT / "reports" / "03_feature_extraction" / "feature_summary.json").read_text())
    source = ROOT / feature_record["output_file"]
    if hashlib.sha256(source.read_bytes()).hexdigest() != feature_record["output_sha256"]:
        raise ValueError("Feature data changed; rerun the feature stage first.")
    frame = pd.read_csv(source, dtype={"SEQN": "int64"})
    if frame["SEQN"].duplicated().any() or len(frame) != feature_record["universe_participants"]:
        raise ValueError("The survey participant universe is inconsistent.")
    domain = frame["analysis_domain"].eq(1)
    if int(domain.sum()) != feature_record["analysis_domain"] or frame.loc[domain, "LBXGH"].isna().any():
        raise ValueError("The measured-HbA1c domain is inconsistent.")
    return frame, feature_record, source


def overall_estimates(sample):
    mean = domain_mean(sample)
    rows = [{"outcome": "Measured HbA1c mean", "unit": "HbA1c percentage points", **mean}]
    for outcome in ("hba1c_at_least_8", "hba1c_at_least_7"):
        proportion = domain_proportion(sample, outcome)
        proportion.pop(outcome)
        rows.append({"outcome": outcome, "unit": "Proportion from 0 to 1", **proportion})
    return pd.DataFrame(rows)


def group_estimates(frame, sample):
    domain = frame["analysis_domain"].eq(1)
    rows = []
    for variable in GROUP_VARIABLES:
        for category in sorted(frame.loc[domain, variable].dropna().unique(), key=str):
            mask = domain & frame[variable].eq(category)
            count = int(mask.sum())
            if count < 30:
                result = {"est": float(np.average(frame.loc[mask, "LBXGH"], weights=frame.loc[mask, "WTMEC2YR"])),
                          "se": np.nan, "lci": np.nan, "uci": np.nan, "cv": np.nan, "df": np.nan, "n": count}
                note = "Interval withheld: fewer than 30 sample members"
            else:
                value = category.item() if isinstance(category, np.generic) else category
                result = domain_mean(sample, extra_condition=svy.col(variable) == value)
                note = "Descriptive group estimate; not a formal between-group test"
            rows.append({"variable": variable, "category": str(category), "domain_missing_this_variable": int((domain & frame[variable].isna()).sum()),
                         "precision_note": note, **result})
    return pd.DataFrame(rows)


def missing_predictors(frame, prepared):
    domain = frame["analysis_domain"].eq(1)
    return pd.DataFrame([
        {"model_predictor": predictor, "source_variable": SOURCE_PREDICTORS[predictor],
         "domain_missing": int(prepared.loc[domain, predictor].isna().sum()),
         "domain_observed": int(prepared.loc[domain, predictor].notna().sum())}
        for predictor in MODEL_PREDICTORS
    ])


def save_plot(frame, groups):
    domain = frame["analysis_domain"].eq(1)
    figure, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    axes[0].hist(frame.loc[domain, "LBXGH"], bins=np.arange(4, 16.6, 0.5),
                 weights=frame.loc[domain, "WTMEC2YR"], density=True, color="#23786d", edgecolor="white")
    axes[0].set(title="Survey-weighted HbA1c distribution", xlabel="Measured HbA1c (%)", ylabel="Weighted density")
    selected = groups.loc[groups["variable"].eq("age_group")]
    errors = [selected["est"] - selected["lci"], selected["uci"] - selected["est"]]
    axes[1].errorbar(selected["category"], selected["est"], yerr=errors, fmt="o", capsize=4, color="#23786d")
    axes[1].set(title="Age-group means with survey 95% intervals", xlabel="Recorded age group", ylabel="Mean HbA1c (%)")
    figure.savefig(REPORT_DIR / "weighted_hba1c.png", dpi=160)
    plt.close(figure)


def main():
    frame, feature_record, source = load_features()
    sample = make_sample(frame)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    print("1/3: Estimating survey-weighted HbA1c summaries...", flush=True)
    overall = overall_estimates(sample)
    groups = group_estimates(frame, sample)
    overall.to_csv(REPORT_DIR / "weighted_outcomes.csv", index=False)
    groups.to_csv(REPORT_DIR / "weighted_group_means.csv", index=False)
    print("2/3: Fitting the prespecified complete-case survey model...", flush=True)
    result, coefficients, prepared = fit_adjusted_model(frame)
    coefficients["unit"] = coefficients["term"].map(MODEL_UNITS)
    coefficients.to_csv(REPORT_DIR / "adjusted_hba1c_coefficients.csv", index=False)
    missing_predictors(frame, prepared).to_csv(REPORT_DIR / "model_predictor_missingness.csv", index=False)
    (REPORT_DIR / "model_summary.txt").write_text(str(result), encoding="utf-8")
    domain = frame["analysis_domain"].eq(1)
    complete = prepared["model_domain"].eq(1)
    design_counts = frame.groupby("SDMVSTRA")["SDMVPSU"].nunique()
    metadata = {
        "cycle": "2017-2018", "universe_participants": len(frame), "analysis_domain": int(domain.sum()),
        "strata": len(design_counts), "stratum_psu_pairs": int(design_counts.sum()),
        "full_design_df": int((design_counts - 1).sum()),
        "model_complete_cases": int(complete.sum()), "model_excluded_missing_predictors": int((domain & ~complete).sum()),
        "model_residual_survey_df": float(coefficients["df"].iloc[0]),
        "model_predictors": list(MODEL_PREDICTORS), "model_family": "Gaussian", "model_link": "Identity",
        "covariance": "svy Taylor-linearized design-based covariance with strata and PSUs",
        "model_iterations": int(result.fitted.stats.iterations),
        "model_in_sample_weighted_r_squared": float(result.fitted.stats.r_squared),
        "input_file": feature_record["output_file"], "input_sha256": feature_record["output_sha256"],
        "weight_variable": "WTMEC2YR", "stratum_variable": "SDMVSTRA", "psu_variable": "SDMVPSU",
        "package_versions": {name: importlib.metadata.version(name) for name in ("svy", "svy-rs", "polars", "pandas", "numpy", "scipy", "statsmodels")},
        "notes": [
            "Design bound to the full 9254-person universe; where selects outcome/model domains without prefiltering rows.",
            "Weighted estimates describe the measured-HbA1c domain; unaddressed HbA1c item nonresponse limits population interpretation.",
            "Model uses 10 prespecified slopes, complete cases, and library residual survey df; FDR excludes the intercept.",
            "No imputation or additional item-nonresponse adjustment; complete-case estimates may reflect selection bias.",
            "Age and poverty ratio top codes are treated numerically in this initial specification; sensitivity remains pending.",
            "No external or predictive validation, causal effects, or individualized treatment thresholds are established.",
        ],
    }
    if hashlib.sha256(source.read_bytes()).hexdigest() != feature_record["output_sha256"]:
        raise ValueError("Feature input changed during analysis.")
    (REPORT_DIR / "analysis_summary.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("3/3: Saving weighted descriptive plots...", flush=True)
    save_plot(frame, groups)
    print(overall[["outcome", "est", "lci", "uci", "df", "n"]].to_string(index=False))
    print(f"Adjusted model: {metadata['model_complete_cases']} complete cases; residual survey df={metadata['model_residual_survey_df']:g}")
    print(f"Analysis outputs: {REPORT_DIR}")


if __name__ == "__main__":
    main()