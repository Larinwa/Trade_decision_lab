RULES = {
    "DQ-00": ("Integrity", "Required Comtrade structure", "Structural"),
    "DQ-01": ("Completeness", "Missing primaryValue", "Project-defined"),
    "DQ-02": ("Completeness", "Missing CIF/FOB auxiliary values", "Project-defined"),
    "DQ-03": ("Completeness", "Quantity and net-weight availability and estimation", "Documented"),
    "DQ-04": ("Completeness", "Missing key identifiers", "Structural"),
    "DQ-05": ("Validity", "Zero or negative primaryValue", "Documented"),
    "DQ-06": ("Validity", "Commodity-code structure and HS4 eligibility", "Structural"),
    "DQ-07": ("Validity", "Reporter, flow and year scope", "Structural"),
    "DQ-08": ("Consistency", "Partner-code and partner-description mapping", "Structural"),
    "DQ-09": ("Uniqueness", "Exact duplicate records", "Project-defined"),
    "DQ-10": ("Uniqueness", "Duplicate trade keys with conflicting values", "Structural"),
    "DQ-11": ("Consistency", "Aggregate and non-country partner records", "Informational"),
    "DQ-12": ("Consistency", "World-to-partner reconciliation", "Documented"),
    "DQ-13": ("Consistency", "Commodity World totals versus total-trade World totals", "Documented"),
    "DQ-14": ("Comparability", "HS classification versions across years", "Informational"),
    "DQ-15": ("Plausibility", "Unit-value screening anomalies", "Project-defined"),
    "DQ-17": ("Coverage", "Candidate partial years", "Project-defined"),
    "DQ-18": ("Coverage", "Historical revision assessment", "Not assessed"),
    "DQ-19": ("Coverage", "Mirror-data comparison", "Not assessed"),
}

RETIRED_RULES = {"DQ-16": "Pooled IQR outlier screening was retired because it was not sufficiently justified for heterogeneous trade values."}

FINDING_CLASSES = {
    "condition": "A measurable data condition is present; this does not always mean an erroneous record.",
    "potential_anomaly": "A rule identified a pattern that needs interpretation or corroboration.",
    "informational": "A dataset characteristic or limitation is documented without asserting an error.",
    "not_assessed": "The available data do not support this assessment.",
}
