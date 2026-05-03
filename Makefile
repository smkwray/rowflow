.PHONY: test lint validate-config smoke-fixtures

test:
	python -m pytest

lint:
	ruff check src tests

validate-config:
	rowflow validate-config

smoke-fixtures:
	mkdir -p data/derived output/reports output/figures output/manifests
	rowflow build-tic-row-panel --input tests/fixtures/tic/tic_official_private_monthly.csv --output data/derived/tic_row_monthly.csv
	rowflow build-z1-row-panel --input tests/fixtures/z1/z1_row_official_private_quarterly.csv --output data/derived/z1_row_quarterly.csv
	rowflow build-rowflow-panel --tic-panel data/derived/tic_row_monthly.csv --z1-panel data/derived/z1_row_quarterly.csv --diagnostics tests/fixtures/diagnostics/monthly_diagnostics.csv --tdc-context tests/fixtures/tdcest/tdc_quarterly_context.csv --output data/derived/rowflow_panel.csv
	rowflow write-rowflow-report --panel data/derived/rowflow_panel.csv --z1-panel data/derived/z1_row_quarterly.csv --output-md output/reports/rowflow_accounting_report.md --figure-dir output/figures
	rowflow write-output-manifest --output output/manifests/rowflow_manifest.json
	rowflow validate-rowflow-package --strict
