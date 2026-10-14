.PHONY: test lint validate-config smoke-fixtures real-package real-determinants

PYTHON ?= $(HOME)/venvs/rowflow/bin/python
RUFF ?= $(HOME)/venvs/rowflow/bin/ruff
ROWFLOW ?= $(HOME)/venvs/rowflow/bin/rowflow
# Real builds write under BUILD_ROOT; a versioned root (e.g. output/refresh_2026q2) leaves the
# default artifacts untouched. SLT names the TIC SLT Table 3 input.
BUILD_ROOT ?= .
SLT ?= ../buycurve/data/raw/validation/tic/slt_table3_foreign_treasury_holders.txt

test:
	$(PYTHON) -B -m pytest

lint:
	$(RUFF) check src tests

validate-config:
	$(ROWFLOW) validate-config

smoke-fixtures:
	mkdir -p data/derived output/reports output/figures output/tables output/manifests
	$(ROWFLOW) build-tic-row-panel --input tests/fixtures/tic/tic_official_private_monthly.csv --output data/derived/tic_row_monthly.csv
	$(ROWFLOW) build-z1-row-panel --input tests/fixtures/z1/z1_row_official_private_quarterly.csv --output data/derived/z1_row_quarterly.csv
	$(ROWFLOW) build-rowflow-panel --tic-panel data/derived/tic_row_monthly.csv --z1-panel data/derived/z1_row_quarterly.csv --diagnostics tests/fixtures/diagnostics/monthly_diagnostics.csv --tdc-context tests/fixtures/tdcest/tdc_quarterly_context.csv --output data/derived/rowflow_panel.csv
	$(ROWFLOW) write-rowflow-report --panel data/derived/rowflow_panel.csv --z1-panel data/derived/z1_row_quarterly.csv --output-md output/reports/rowflow_accounting_report.md --figure-dir output/figures --table-dir output/tables
	$(ROWFLOW) write-output-manifest --output output/manifests/rowflow_manifest.json
	$(ROWFLOW) validate-rowflow-package --strict

real-package:
	mkdir -p $(BUILD_ROOT)/data/raw/tic $(BUILD_ROOT)/data/raw/z1 $(BUILD_ROOT)/data/raw/fred $(BUILD_ROOT)/data/derived $(BUILD_ROOT)/output/reports $(BUILD_ROOT)/output/figures $(BUILD_ROOT)/output/tables $(BUILD_ROOT)/output/manifests
	rm -f $(BUILD_ROOT)/data/derived/foreign_absorption_determinants_monthly.csv $(BUILD_ROOT)/output/tables/determinant_panel_missingness.csv $(BUILD_ROOT)/output/tables/monthly_tic_determinants.csv $(BUILD_ROOT)/output/tables/monthly_tic_determinants_compact.csv $(BUILD_ROOT)/output/reports/monthly_tic_determinants_compact.md $(BUILD_ROOT)/output/reports/foreign_absorption_determinants.md
	$(ROWFLOW) validate-sibling-sources --sibling-root .. --strict
	$(ROWFLOW) copy-sibling-outputs --root $(BUILD_ROOT) --config-dir config --sibling-root .. --overwrite
	$(ROWFLOW) download-text-source --url https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/tressect.txt --output $(BUILD_ROOT)/data/raw/tic/tressect.txt
	$(ROWFLOW) download-text-source --url 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTWEXBGS' --output $(BUILD_ROOT)/data/raw/fred/dtwexbgs.csv
	$(ROWFLOW) download-z1-fred-transactions --output $(BUILD_ROOT)/data/raw/z1/z1_row_official_private_transactions.csv
	$(ROWFLOW) build-tic-row-panel --input $(BUILD_ROOT)/data/raw/tic/tressect.txt --output $(BUILD_ROOT)/data/derived/tic_row_monthly_legacy_tressect.csv
	$(ROWFLOW) build-tic-row-panel --input $(SLT) --output $(BUILD_ROOT)/data/derived/tic_row_monthly_slt.csv
	$(ROWFLOW) combine-tic-row-panels --input $(BUILD_ROOT)/data/derived/tic_row_monthly_legacy_tressect.csv --input $(BUILD_ROOT)/data/derived/tic_row_monthly_slt.csv --output $(BUILD_ROOT)/data/derived/tic_row_monthly_real.csv
	$(ROWFLOW) build-z1-row-panel --input $(BUILD_ROOT)/data/raw/z1/z1_row_official_private_transactions.csv --transactions-are-quarterly --output $(BUILD_ROOT)/data/derived/z1_row_quarterly_real.csv
	$(ROWFLOW) build-rowflow-panel --tic-panel $(BUILD_ROOT)/data/derived/tic_row_monthly_real.csv --z1-panel $(BUILD_ROOT)/data/derived/z1_row_quarterly_real.csv --diagnostics $(BUILD_ROOT)/data/imported/liqsub/monthly_liquidity_substitution_panel.csv --issuance-diagnostics $(BUILD_ROOT)/data/imported/buycurve/monthly_issuance_maturity_panel.csv --debt-denominators $(BUILD_ROOT)/data/imported/qrawatch/mspd_table_1.csv --fred-diagnostics $(BUILD_ROOT)/data/imported/qrawatch/fred_core_wide.csv --fred-diagnostics $(BUILD_ROOT)/data/raw/fred/dtwexbgs.csv --tdc-context $(BUILD_ROOT)/data/imported/tdcest/tdc_estimates.csv --output $(BUILD_ROOT)/data/derived/rowflow_panel.csv
	$(ROWFLOW) write-rowflow-report --panel $(BUILD_ROOT)/data/derived/rowflow_panel.csv --z1-panel $(BUILD_ROOT)/data/derived/z1_row_quarterly_real.csv --output-md $(BUILD_ROOT)/output/reports/rowflow_accounting_report.md --figure-dir $(BUILD_ROOT)/output/figures --table-dir $(BUILD_ROOT)/output/tables
	$(ROWFLOW) write-output-manifest --root $(BUILD_ROOT) --output $(BUILD_ROOT)/output/manifests/rowflow_manifest.json
	$(ROWFLOW) validate-rowflow-package --root $(BUILD_ROOT) --config-dir config --strict

real-determinants: real-package
	$(ROWFLOW) write-source-regime-ledger --tic-panel $(BUILD_ROOT)/data/derived/tic_row_monthly_real.csv --z1-panel $(BUILD_ROOT)/data/derived/z1_row_quarterly_real.csv --output-csv $(BUILD_ROOT)/output/tables/source_regime_ledger.csv --output-md $(BUILD_ROOT)/output/reports/source_regime_ledger.md
	$(ROWFLOW) write-episode-absorption --panel $(BUILD_ROOT)/data/derived/rowflow_panel.csv --z1-panel $(BUILD_ROOT)/data/derived/z1_row_quarterly_real.csv --episodes config/episodes.yml --output $(BUILD_ROOT)/output/tables/episode_absorption.csv
	$(ROWFLOW) build-determinant-panel --panel $(BUILD_ROOT)/data/derived/rowflow_panel.csv --spec config/determinant_specs.yml --output $(BUILD_ROOT)/data/derived/foreign_absorption_determinants_monthly.csv --missingness-output $(BUILD_ROOT)/output/tables/determinant_panel_missingness.csv
	$(ROWFLOW) write-determinant-tables --panel $(BUILD_ROOT)/data/derived/foreign_absorption_determinants_monthly.csv --spec config/determinant_specs.yml --output $(BUILD_ROOT)/output/tables/monthly_tic_determinants.csv
	$(ROWFLOW) write-compact-determinant-table --determinants $(BUILD_ROOT)/output/tables/monthly_tic_determinants.csv --output $(BUILD_ROOT)/output/tables/monthly_tic_determinants_compact.csv
	$(ROWFLOW) write-compact-determinant-markdown --compact $(BUILD_ROOT)/output/tables/monthly_tic_determinants_compact.csv --output-md $(BUILD_ROOT)/output/reports/monthly_tic_determinants_compact.md
	$(ROWFLOW) write-determinant-report --panel $(BUILD_ROOT)/data/derived/foreign_absorption_determinants_monthly.csv --ledger $(BUILD_ROOT)/output/tables/source_regime_ledger.csv --episodes $(BUILD_ROOT)/output/tables/episode_absorption.csv --determinants $(BUILD_ROOT)/output/tables/monthly_tic_determinants.csv --output-md $(BUILD_ROOT)/output/reports/foreign_absorption_determinants.md
	$(ROWFLOW) write-output-manifest --root $(BUILD_ROOT) --output $(BUILD_ROOT)/output/manifests/rowflow_manifest.json
	$(ROWFLOW) validate-rowflow-package --root $(BUILD_ROOT) --config-dir config --strict
