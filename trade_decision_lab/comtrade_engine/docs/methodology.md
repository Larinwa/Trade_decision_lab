# Methodology

## Research logic

The implementation follows the research sequence:

1. Assess the quality conditions present in the supplied trade data.
2. Test whether alternative, explicitly described treatments change analytical outputs.
3. Assess the potential relevance of those changes to trade-related interpretation.

The sequence is implemented as three modules. The Trade Decision Lab dashboard communicates their outputs; it is not a fourth analytical model.

## Model A — Data quality assessment

Model A validates the Comtrade input structure, standardises data types, preserves source rows and evaluates the registered checks in `quality.py`.

Finding classes are:

- `condition`: a measurable condition is present, such as missing values or duplicate records.
- `potential_anomaly`: a pattern is flagged but is not established as an error.
- `informational`: a source characteristic or analytical limitation is recorded.
- `not_assessed`: the supplied extracts do not support the check.

A finding class is not a claim that the source publisher made an error. For example, missing net weight can limit weight-based analysis while leaving a reported trade value available for value-based analysis.

The unit-value screen calculates `primaryValue / netWgt` and compares the result with the annual commodity median within the same classification version. Ratios above 3 or below one third are flagged. A second flag uses only records whose net weights are not marked as estimated. Both are screens, not confirmed errors.

World reconciliation includes all non-World partner records, including non-country aggregates such as `Other Asia, nes`. A group is assessable only when it has exactly one World record, at least one non-World partner record and no missing `primaryValue` values. The configured absolute tolerance is project-defined and is not treated as proof of error.

The 50% reported-weight value-share reference is used only to qualify weight-dependent evidence. It is used by analogy to the UNSD unit-value reliability discussion and is not a universal data-quality pass/fail threshold.

## Model B — Analytical comparison

The primary ranking is calculated from country partners only and uses `primaryValue`. Missing or estimated weights do not remove a record from a trade-value ranking.

The comparison includes these treatments:

- `country_only_baseline`: primary value, country partners only.
- `all_partner_labels_diagnostic`: includes World and aggregate labels; not a valid country ranking.
- `reported_weight_only_sensitivity`: retains records whose net weight is explicitly marked as reported.
- `missing_weight_excluded_sensitivity`: excludes records with missing or zero net weight.
- `reported_weight_uv_screen_sensitivity`: excludes unit-value screen flags calculated from non-estimated weights.
- `notebook_uv_screen_sensitivity`: excludes all notebook-style unit-value flags, including those based on estimated weights.

The weight and unit-value exclusions are sensitivity tests. They are not recommended as automatic corrections to trade-value records.

For each commodity, flow, scenario and classification version, the module reports partner values, shares, ranks, HHI and CR5. Scenario A is 2016–2024 and Scenario B is 2022–2024. If multiple classification versions occur in a scenario, results are partitioned by the observed `classificationCode`. Cross-version code equivalence is not assumed.

## Model C — Decision implications

Model C compares each sensitivity treatment with the country-only baseline. It records whether the leading partner, top-five membership, HHI or CR5 changes.

The labels describe sensitivity to the tested treatments. They do not represent a sourcing recommendation, a forecast, a causal estimate or evidence that a real decision-maker changed a decision.

The module also reports the value share supported by reported, estimated and missing weights. The 50% reference is used to qualify unit-value evidence, not to invalidate value-based trade analysis.

## Reproducibility

The pipeline records the configured years, selected commodity codes, input shapes and treatment definitions. Outputs are saved separately for imports and exports. Each Model A finding includes source-row references where applicable.
