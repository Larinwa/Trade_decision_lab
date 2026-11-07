# Data contract

## Required columns

Each commodity-level input must contain:

- `refYear`
- `flowCode`
- `flowDesc`
- `reporterDesc`
- `partnerCode`
- `partnerDesc`
- `cmdCode`
- `classificationCode`
- `primaryValue`

The schema validator also checks numeric convertibility for numeric fields when present.

## Recommended columns

The following columns improve the scope and quality of the assessment:

- `reporterCode`
- `qty`, `netWgt`, `qtyUnitCode`
- `aggrLevel`
- `cifvalue`, `fobvalue`
- `partner2Code`, `motCode`, `customsCode`
- `isAggregate`, `isReported`
- `isNetWgtEstimated`, `isQtyEstimated` or `legacyEstimationFlag`

## Source traceability

If `source_row` is absent, the pipeline uses the input DataFrame index. If `source_file` is absent, the pipeline records the expected source filename. These fields are added to working copies; source CSV files are not modified.

## Flow separation

The commodity import and export files are processed separately. The total-trade file may contain both flows and is filtered to the matching `flowDesc` for DQ-13.

## Commodity selection

The configured codes are `2710`, `1001`, `8703`, `8517` and `0303`. They are selected from the project's existing analysis configuration. The pipeline does not silently substitute another commodity if one of these codes is absent; the relevant period/commodity output will be empty or unavailable and should be reviewed.
