.PHONY: test lint validate-config smoke-fixtures real-package

PYTHON ?= $(HOME)/venvs/rowflow/bin/python
RUFF ?= $(HOME)/venvs/rowflow/bin/ruff
ROWFLOW ?= $(HOME)/venvs/rowflow/bin/rowflow

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
	mkdir -p data/raw/tic data/raw/z1 data/derived output/reports output/figures output/tables output/manifests
	$(ROWFLOW) validate-sibling-sources --sibling-root .. --strict
	$(ROWFLOW) copy-sibling-outputs --sibling-root .. --overwrite
	$(ROWFLOW) download-text-source --url https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/tressect.txt --output data/raw/tic/tressect.txt
	$(ROWFLOW) download-z1-fred-transactions --output data/raw/z1/z1_row_official_private_transactions.csv
	$(ROWFLOW) build-tic-row-panel --input data/raw/tic/tressect.txt --output data/derived/tic_row_monthly_legacy_tressect.csv
	$(ROWFLOW) build-tic-row-panel --input ../buycurve/data/raw/validation/tic/slt_table3_foreign_treasury_holders.txt --output data/derived/tic_row_monthly_slt.csv
	$(ROWFLOW) combine-tic-row-panels --input data/derived/tic_row_monthly_legacy_tressect.csv --input data/derived/tic_row_monthly_slt.csv --output data/derived/tic_row_monthly_real.csv
	$(ROWFLOW) build-z1-row-panel --input data/raw/z1/z1_row_official_private_transactions.csv --transactions-are-quarterly --output data/derived/z1_row_quarterly_real.csv
	$(ROWFLOW) build-rowflow-panel --tic-panel data/derived/tic_row_monthly_real.csv --z1-panel data/derived/z1_row_quarterly_real.csv --diagnostics data/imported/liqsub/monthly_liquidity_substitution_panel.csv --tdc-context data/imported/tdcest/tdc_estimates.csv --output data/derived/rowflow_panel.csv
	$(ROWFLOW) write-rowflow-report --panel data/derived/rowflow_panel.csv --z1-panel data/derived/z1_row_quarterly_real.csv --output-md output/reports/rowflow_accounting_report.md --figure-dir output/figures --table-dir output/tables
	$(ROWFLOW) write-output-manifest --output output/manifests/rowflow_manifest.json
	$(ROWFLOW) validate-rowflow-package --strict
