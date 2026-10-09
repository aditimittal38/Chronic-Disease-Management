"""Variable-specific NHANES rules; retain response reasons separately from values."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


OBSERVED = "observed"
NOT_RECORDED = "not_recorded"
ACTIVITY_DOMAINS = (
    ("PAQ605", "PAQ610", "PAD615"), ("PAQ620", "PAQ625", "PAD630"),
    ("PAQ635", "PAQ640", "PAD645"), ("PAQ650", "PAQ655", "PAD660"),
    ("PAQ665", "PAQ670", "PAD675"),
)
DESIGN_COLUMNS = ("SEQN", "WTMEC2YR", "WTINT2YR", "SDMVSTRA", "SDMVPSU", "RIDSTATR")
MONITORING_COLUMNS = ("DIQ230", "DIQ240", "DID250", "DID260", "DIQ260U", "DIQ275", "DIQ280", "DIQ291", "DIQ080", "DID040")


@dataclass(frozen=True)
class Rule:
    allowed: tuple | None = None
    minimum: float | None = None
    maximum: float | None = None
    specials: dict = field(default_factory=dict)
    integral: bool = False


def categorical_rule(allowed, refused=7, unknown=9):
    return Rule(allowed=tuple(allowed), specials={refused: "refused", unknown: "dont_know"}, integral=True)


def count_rule(refused, unknown, minimum=0, maximum=None):
    return Rule(minimum=minimum, maximum=maximum, specials={refused: "refused", unknown: "dont_know"}, integral=True)


def make_rules():
    rules = {
        "SEQN": Rule(minimum=1, integral=True), "RIDAGEYR": Rule(minimum=0, maximum=80, integral=True),
        "RIAGENDR": Rule(allowed=(1, 2)), "RIDRETH3": Rule(allowed=(1, 2, 3, 4, 6, 7)),
        "DMDEDUC2": categorical_rule(range(1, 6)), "INDFMPIR": Rule(minimum=0, maximum=5),
        "RIDEXPRG": Rule(allowed=(1, 2), specials={3: "cannot_ascertain"}),
        "RIDSTATR": Rule(allowed=(1, 2)), "WTMEC2YR": Rule(minimum=0), "WTINT2YR": Rule(minimum=0),
        "SDMVSTRA": Rule(minimum=1, integral=True), "SDMVPSU": Rule(allowed=(1, 2)),
        "DIQ010": categorical_rule((1, 2, 3)),
        "DID040": Rule(minimum=1, maximum=80, integral=True, specials={666: "age_below_one_interval", 777: "refused", 999: "dont_know"}),
        "DIQ050": categorical_rule((1, 2)), "DIQ070": categorical_rule((1, 2)),
        "DIQ230": categorical_rule(range(1, 6)), "DIQ240": categorical_rule((1, 2)),
        "DID250": count_rule(7777, 9999), "DID260": count_rule(777, 999),
        "DIQ260U": Rule(allowed=(1, 2, 3, 4)), "DIQ275": categorical_rule((1, 2)),
        "DIQ280": Rule(minimum=0.01, specials={777: "refused", 999: "dont_know"}),
        "DIQ291": categorical_rule(range(1, 7), refused=77, unknown=99),
        "DIQ080": categorical_rule((1, 2)), "LBXGH": Rule(minimum=0.01), "BMXBMI": Rule(minimum=0.01),
        "PAD680": count_rule(7777, 9999, maximum=1439),
        "HUQ010": categorical_rule(range(1, 6)), "HUQ030": categorical_rule((1, 2, 3)),
        "HUQ041": categorical_rule(range(1, 7), refused=77, unknown=99),
        "HUQ051": categorical_rule(range(0, 9), refused=77, unknown=99),
        "HUQ071": categorical_rule((1, 2)), "HUD080": categorical_rule(range(1, 7), refused=77777, unknown=99999),
    }
    for gate, days, minutes in ACTIVITY_DOMAINS:
        rules[gate] = categorical_rule((1, 2))
        rules[days] = count_rule(77, 99, minimum=1, maximum=7)
        rules[minutes] = count_rule(7777, 9999, minimum=10, maximum=1439)
    return rules


def clean_column(raw, rule):
    values = pd.to_numeric(raw, errors="raise").astype(float).copy()
    statuses = pd.Series(np.where(values.notna(), OBSERVED, NOT_RECORDED), index=raw.index)
    for code, reason in rule.specials.items():
        mask = values.eq(code)
        statuses.loc[mask] = reason
        values.loc[mask] = np.nan
    invalid = pd.Series(False, index=raw.index)
    if rule.allowed is not None:
        invalid |= values.notna() & ~values.isin(rule.allowed)
    if rule.minimum is not None:
        invalid |= values.lt(rule.minimum)
    if rule.maximum is not None:
        invalid |= values.gt(rule.maximum)
    if rule.integral:
        invalid |= values.notna() & values.mod(1).ne(0)
    values.loc[invalid] = np.nan
    statuses.loc[invalid] = "invalid_value"
    return values, statuses


def label_blank(statuses, column, condition, reason):
    mask = statuses[column].eq(NOT_RECORDED) & condition
    statuses.loc[mask, column] = reason


def route_followup(raw, values, statuses, column, skipped, skip_reason, gate_unknown):
    label_blank(statuses, column, skipped, skip_reason)
    label_blank(statuses, column, gate_unknown, "gate_unknown")
    conflict = skipped & raw[column].notna()
    statuses.loc[conflict, column] = "routing_conflict"
    values.loc[conflict, column] = np.nan


def apply_routing(raw, values, statuses):
    for gate, days, minutes in ACTIVITY_DOMAINS:
        for column in (days, minutes):
            route_followup(raw, values, statuses, column, values[gate].eq(2), "skip_no_activity", values[gate].isna())
    route_followup(raw, values, statuses, "DID250", values["DIQ240"].eq(2), "skip_no_usual_diabetes_doctor", values["DIQ240"].isna())
    route_followup(raw, values, statuses, "HUQ041", values["HUQ030"].eq(2), "skip_no_usual_healthcare_place", values["HUQ030"].isna())
    route_followup(raw, values, statuses, "HUD080", values["HUQ071"].eq(2), "skip_no_hospitalization", values["HUQ071"].isna())
    for column in ("DIQ280", "DIQ291"):
        route_followup(raw, values, statuses, column, values["DIQ275"].eq(2), "skip_no_reported_a1c_test", values["DIQ275"].isna())
    label_blank(statuses, "DIQ260U", values["DID260"].eq(0), "skip_never_checks_glucose")
    label_blank(statuses, "DIQ260U", values["DID260"].gt(0), "missing_required_unit")


def apply_eligibility(raw, values, statuses, module_members):
    minimum_ages = {"DMDEDUC2": 20, "LBXGH": 12, "BMXBMI": 2, "DIQ010": 1, "DIQ050": 1, "DIQ070": 1, "DIQ080": 12}
    for gate, days, minutes in ACTIVITY_DOMAINS:
        minimum_ages.update({gate: 18, days: 18, minutes: 18})
    minimum_ages["PAD680"] = 18
    for column, minimum in minimum_ages.items():
        missing = raw[column].isna() & raw["RIDAGEYR"].lt(minimum)
        statuses.loc[missing, column] = "not_age_eligible"
    pregnancy_eligible = raw["RIAGENDR"].eq(2) & raw["RIDAGEYR"].between(20, 44)
    statuses.loc[raw["RIDEXPRG"].isna() & ~pregnancy_eligible, "RIDEXPRG"] = "not_released_for_group"
    for column in MONITORING_COLUMNS:
        label_blank(statuses, column, raw["DIQ010"].ne(1), "outside_diagnosed_diabetes_domain")
    for column in ("LBXGH", "BMXBMI", "RIDEXPRG"):
        label_blank(statuses, column, raw["RIDSTATR"].eq(1), "not_examined")
    for module, columns in module_members.items():
        present = raw["SEQN"].isin(columns["participants"])
        for column in set(columns["variables"]) & set(values):
            label_blank(statuses, column, ~present, "no_component_record")
    statuses.loc[values["RIDAGEYR"].eq(80), "RIDAGEYR"] = "top_coded"
    statuses.loc[values["INDFMPIR"].eq(5), "INDFMPIR"] = "top_coded"
    statuses.loc[values["DID040"].eq(80), "DID040"] = "top_coded"
    statuses.loc[values["HUD080"].eq(6), "HUD080"] = "top_coded"
    statuses.loc[values["DIQ291"].eq(6), "DIQ291"] = "provider_did_not_specify_goal"


def clean_frame(raw, module_members):
    rules = make_rules()
    if not set(rules).issubset(raw):
        raise ValueError(f"Missing required variables: {sorted(set(rules) - set(raw))}")
    values = pd.DataFrame(index=raw.index)
    statuses = pd.DataFrame(index=raw.index)
    for column, rule in rules.items():
        values[column], statuses[column] = clean_column(raw[column], rule)
    apply_routing(raw, values, statuses)
    apply_eligibility(raw, values, statuses, module_members)
    for column in DESIGN_COLUMNS:
        if not np.allclose(values[column], raw[column], equal_nan=True):
            raise ValueError(f"Survey design/identifier changed: {column}")
    if not np.allclose(values["LBXGH"], raw["LBXGH"], equal_nan=True):
        raise ValueError("Invalid measured HbA1c requires review before export.")
    values["SEQN"] = values["SEQN"].astype("int64")
    domain = values["RIDAGEYR"].ge(20) & values["DIQ010"].eq(1) & values["LBXGH"].notna()
    domain &= raw["RIDEXPRG"].ne(1) & values["WTMEC2YR"].gt(0)
    domain &= values[["SDMVSTRA", "SDMVPSU"]].notna().all(axis=1)
    values["analysis_domain"] = domain.astype(int)
    values["pregnancy_uncertain"] = raw["RIDEXPRG"].eq(3).astype(int)
    values["analysis_domain_known_pregnancy_status_sensitivity"] = (domain & ~raw["RIDEXPRG"].eq(3)).astype(int)
    return values, statuses, rules