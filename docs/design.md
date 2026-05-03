# rowflow design note

`rowflow` is the bounded Project 6 build for the TDC project family. Its role is to split rest-of-world Treasury absorption into foreign official and foreign private components and to carry that split into the existing TDC diagnostic ecosystem.

## Data model

The project starts with three public-facing panels:

1. `tic_row_monthly.csv`: monthly TIC official/private Treasury net-flow panel.
2. `z1_row_quarterly.csv`: quarterly Z.1 official/private ROW comparison panel, using transaction series when available or explicitly labeled level changes when only level caches are available.
3. `rowflow_panel.csv`: monthly diagnostic panel joining TIC flows with bill share, WAM, TGA, reserves, deposits, MMFs, ON RRP, Z.1 sidecars, and TDC anchors.

The package intentionally does not start with regressions. The first package is accounting infrastructure: source contracts, transforms, validation gates, and a compact report.

## Frequency design

TIC is the monthly headline frequency. Z.1 is the quarterly validation/comparison frequency. Quarterly Z.1 and TDC anchors are attached to months by quarter in the merged panel. Any quarterly-vs-monthly reconciliation should be reported as a measurement gap, not forced into a strict identity. Level-change Z.1 context is useful for direction and accounting scale, but it is not the same source concept as a transaction series.

## Sibling reuse

The default rule is to copy from sibling outputs before downloading or transforming new data. `source_contracts.yml` documents the preferred artifacts. Missing optional artifacts should be reported, not treated as fatal blockers.

## Naming convention

- `tic_` variables preserve the TIC sign convention.
- `z1_` variables preserve the Z.1/FRED source definition after converting SAAR transactions to quarter-flow amounts.
- diagnostic variables stay plain (`bill_share`, `wam_years`, etc.) when imported from sibling panels.

## Claim boundary

Report language must say that the output is descriptive accounting only and does not identify causal domestic liquidity effects. That phrase is enforced by package validation.
