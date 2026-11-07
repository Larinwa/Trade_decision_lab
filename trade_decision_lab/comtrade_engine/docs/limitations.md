# Limitations

- The partner-country classification is a text/code heuristic. It is not an authoritative UN M49 country/area reference table. Review `is_country` classifications before treating them as final.
- `World` is an aggregate. Other non-country partner labels can also be aggregates; they are retained in reconciliation but excluded from country rankings.
- The downloaded files do not provide revision history. DQ-18 is not assessed.
- Partner-reported mirror data were not supplied. DQ-19 and bilateral asymmetry are not assessed.
- The unit-value ratio is a screening statistic. It does not account for product quality, specification, freight, insurance, contract terms, timing or valuation differences. A flagged record is not necessarily erroneous.
- Net weights can be estimated. The estimation flags are used where available; absence of an estimation indicator does not prove that a weight was reported.
- The 50% reported-weight value-share reference is a qualification rule used by analogy. It is not a universal standard for all commodities or decisions.
- Missing quantity or net weight does not automatically make `primaryValue` unusable. Removing such rows from value rankings can introduce selection effects; those filters are sensitivity tests only.
- H4/H6 classification labels are kept separate in Model B. The package does not perform HS concordance or establish cross-version equivalence.
- A commodity-level World total may differ from a total-trade World total because detailed trade may be confidential, unclassified or otherwise not itemised. A shortfall is not automatically an error.
- Scenario A and Scenario B are the windows used in the existing project analysis. Their suitability should be reconsidered if the study period or source coverage changes.
- Model C identifies potential decision relevance from observed analytical changes. It does not establish actual behavioural, procurement or policy impact.
- The tests use synthetic fixtures to verify implementation behaviour. They do not validate the accuracy of the underlying Comtrade data or prove the rules detect every possible data-quality problem.
