"""Summarize full-cohort rates and test one randomly selected encounter per patient."""

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu
from statsmodels.stats.multitest import multipletests


TARGET = "readmitted_30d"
CATEGORICAL_VARIABLES = (
    "inpatient_history_band", "age_group", "gender", "race", "diag_1_group",
    "medication_burden_band", "insulin", "medication_changed",
    "any_drug_dose_changed", "A1Cresult", "max_glu_serum",
)
COUNT_VARIABLES = (
    "number_inpatient", "number_emergency", "number_outpatient", "num_medications",
    "number_diagnoses", "time_in_hospital", "num_lab_procedures", "num_procedures",
)


def add_adjusted_pvalues(table, p_column):
    table["fdr_adjusted_p"] = np.nan
    valid = table[p_column].notna()
    if valid.any():
        table.loc[valid, "fdr_adjusted_p"] = multipletests(table.loc[valid, p_column], method="fdr_bh")[1]
    return table


def grouped_rates(frame, variable):
    clusters = frame.groupby([variable, "patient_nbr"], observed=True)[TARGET].agg(["size", "sum"])
    patients = frame["patient_nbr"].nunique()
    rows = []
    for value, group in clusters.groupby(level=0, observed=True):
        count = int(group["size"].sum())
        events = int(group["sum"].sum())
        rate = events / count
        residual = group["sum"] - rate * group["size"]
        standard_error = np.sqrt((patients / (patients - 1)) * (residual ** 2).sum()) / count
        reliable = len(group) >= 30 and 0 < events < count
        rows.append({
            "variable": variable, "category": str(value), "encounters": count,
            "patients_in_category": len(group), "early_readmissions": events,
            "readmission_percent": 100 * rate,
            "cluster_ci_low_percent": 100 * max(0, rate - 1.96 * standard_error) if reliable else np.nan,
            "cluster_ci_high_percent": 100 * min(1, rate + 1.96 * standard_error) if reliable else np.nan,
            "interval_note": "Approximate patient-clustered 95% interval" if reliable else "Too sparse for this interval",
        })
    return rows


def categorical_test(sample, variable):
    contingency = pd.crosstab(sample[variable], sample[TARGET]).reindex(columns=[0, 1], fill_value=0)
    statistic, probability, degrees, expected = chi2_contingency(contingency, correction=False)
    sparse = bool((expected < 5).any())
    return {
        "variable": variable, "test": "Chi-square", "statistic": float(statistic),
        "degrees_of_freedom": int(degrees), "p_value": np.nan if sparse else float(probability),
        "note": "Sparse expected cells; asymptotic p-value withheld" if sparse else "One encounter per patient",
    }


def numerical_tables(frame, sample):
    comparisons = []
    tests = []
    for variable in COUNT_VARIABLES:
        for outcome, group in frame.groupby(TARGET):
            comparisons.append({
                "variable": variable, "early_readmission": int(outcome), "encounters": len(group),
                "mean": float(group[variable].mean()), "median": float(group[variable].median()),
                "q25": float(group[variable].quantile(0.25)), "q75": float(group[variable].quantile(0.75)),
            })
        positive = sample.loc[sample[TARGET] == 1, variable]
        negative = sample.loc[sample[TARGET] == 0, variable]
        statistic, probability = mannwhitneyu(positive, negative, alternative="two-sided", method="asymptotic")
        tests.append({
            "variable": variable, "test": "Mann-Whitney U", "statistic": float(statistic),
            "degrees_of_freedom": np.nan, "p_value": float(probability),
            "note": "One encounter per patient; distribution comparison, not necessarily a median test",
        })
    return comparisons, tests


def descriptive_tables(frame):
    if frame["patient_nbr"].nunique() < 2 or frame[TARGET].nunique() != 2:
        raise ValueError("Analysis requires multiple patients and both outcome classes.")
    sample = frame.sample(frac=1, random_state=42).drop_duplicates("patient_nbr")
    rate_rows = [row for variable in CATEGORICAL_VARIABLES for row in grouped_rates(frame, variable)]
    tests = [categorical_test(sample, variable) for variable in CATEGORICAL_VARIABLES]
    comparisons, numeric_tests = numerical_tables(frame, sample)
    test_table = add_adjusted_pvalues(pd.DataFrame(tests + numeric_tests), "p_value")
    return pd.DataFrame(rate_rows), pd.DataFrame(comparisons), test_table, len(sample)