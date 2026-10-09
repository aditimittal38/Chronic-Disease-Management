"""Quantify patient-level evaluation uncertainty and predictive importance."""

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from prediction_models import FEATURE_GROUPS, TARGET, metric_values


METRICS = ("roc_auc", "average_precision", "brier_score")


def patient_bootstrap_weights(patient_ids, generator):
    codes, patients = pd.factorize(patient_ids, sort=True)
    draws = generator.integers(0, len(patients), size=len(patients))
    multiplicities = np.bincount(draws, minlength=len(patients))
    return multiplicities[codes]


def bootstrap_metrics(predictions, repetitions=200):
    generator = np.random.default_rng(42)
    outcome = predictions[TARGET].to_numpy()
    names = [column for column in predictions if column not in ("encounter_id", "patient_nbr", TARGET)]
    distributions = {(name, metric): [] for name in names for metric in METRICS}
    points = {name: metric_values(outcome, predictions[name].to_numpy()) for name in names}
    for _ in range(repetitions):
        weights = patient_bootstrap_weights(predictions["patient_nbr"], generator)
        if np.unique(outcome[weights > 0]).size != 2:
            continue
        for name in names:
            values = metric_values(outcome, predictions[name].to_numpy(), weights)
            for metric, value in values.items():
                distributions[(name, metric)].append(value)
    rows = []
    for (name, metric), samples in distributions.items():
        if len(samples) < 0.9 * repetitions:
            raise ValueError("Too many bootstrap draws lacked both outcome classes.")
        lower, upper = np.quantile(samples, [0.025, 0.975])
        rows.append({
            "model": name, "metric": metric, "estimate": points[name][metric],
            "ci_low": float(lower), "ci_high": float(upper), "valid_repetitions": len(samples),
        })
    comparisons = []
    pairs = [
        ("hist_gradient_boosting", "expanded_logistic"),
        ("expanded_logistic", "initial_logistic"),
        ("hist_gradient_boosting", "initial_logistic"),
    ]
    for candidate, reference in pairs:
        for metric in METRICS:
            differences = np.asarray(distributions[(candidate, metric)]) - np.asarray(distributions[(reference, metric)])
            lower, upper = np.quantile(differences, [0.025, 0.975])
            comparisons.append({
                "candidate": candidate, "reference": reference, "metric": metric,
                "difference": points[candidate][metric] - points[reference][metric],
                "ci_low": float(lower), "ci_high": float(upper),
            })
    return pd.DataFrame(rows), pd.DataFrame(comparisons)


def individual_importance(models, predictors, outcome, repetitions=5):
    rows = []
    for name, model in models.items():
        print(f"  Permuting individual predictors: {name}...", flush=True)
        results = permutation_importance(
            model, predictors, outcome, scoring=["average_precision", "roc_auc"],
            n_repeats=repetitions, random_state=42, n_jobs=1,
        )
        for metric, result in results.items():
            for index, feature in enumerate(predictors.columns):
                rows.append({
                    "model": name, "feature": feature, "metric": metric,
                    "mean_score_drop": float(result.importances_mean[index]),
                    "permutation_sd": float(result.importances_std[index]),
                    "repetitions": repetitions,
                })
    return pd.DataFrame(rows)


def grouped_importance(models, predictors, outcome, repetitions=5):
    rows = []
    for name, model in models.items():
        generator = np.random.default_rng(42)
        baseline = metric_values(outcome, model.predict_proba(predictors)[:, 1])
        for group_name, columns in FEATURE_GROUPS.items():
            scores = {metric: [] for metric in ("average_precision", "roc_auc")}
            for _ in range(repetitions):
                permutation = generator.permutation(len(predictors))
                shuffled = predictors.copy()
                shuffled[columns] = predictors.iloc[permutation][columns].to_numpy()
                values = metric_values(outcome, model.predict_proba(shuffled)[:, 1])
                for metric in scores:
                    scores[metric].append(baseline[metric] - values[metric])
            for metric, drops in scores.items():
                rows.append({
                    "model": name, "feature_group": group_name, "metric": metric,
                    "mean_score_drop": float(np.mean(drops)), "permutation_sd": float(np.std(drops)),
                    "repetitions": repetitions, "columns": ", ".join(columns),
                })
    return pd.DataFrame(rows)


def subgroup_metrics(test, predictions):
    rows = []
    names = [column for column in predictions if column not in ("encounter_id", "patient_nbr", TARGET)]
    aligned = test.set_index("encounter_id").loc[predictions["encounter_id"]].reset_index()
    for variable in ("age_group", "gender", "race"):
        for category, group in aligned.groupby(variable, observed=True):
            positions = group.index.to_numpy()
            outcome = predictions.iloc[positions][TARGET].to_numpy()
            events = int(outcome.sum())
            enough_data = events >= 30 and len(outcome) - events >= 30
            for name in names:
                probabilities = predictions.iloc[positions][name].to_numpy()
                values = metric_values(outcome, probabilities) if enough_data else {metric: np.nan for metric in METRICS}
                rows.append({
                    "variable": variable, "category": str(category), "model": name,
                    "encounters": len(group), "patients": int(group["patient_nbr"].nunique()),
                    "early_readmissions": events, "prevalence": float(outcome.mean()), **values,
                    "note": "Point estimates only" if enough_data else "Withheld: fewer than 30 events or nonevents",
                })
    return pd.DataFrame(rows)