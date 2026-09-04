PYTHON ?= .venv/bin/python

.PHONY: all pull validate warehouse csv bootstrap xlsx dashboard powerbi memo smoke test clean distclean help

help:
	@echo "make all        Run the full pipeline (pull -> memo)"
	@echo "make pull       Pull raw EIA-930 data (~15 min, needs EIA_API_KEY)"
	@echo "make validate   Data quality report"
	@echo "make warehouse  Build the DuckDB star schema and export parquet"
	@echo "make bootstrap  Block-bootstrap confidence intervals"
	@echo "make csv        Also export CSV copies (Power BI parquet fallback)"
	@echo "make xlsx       Excel assumptions register"
	@echo "make dashboard  HTML dashboard and screenshots"
	@echo "make powerbi    Rebuild the Power BI report pages and theme"
	@echo "make memo       One-page analyst memo PDF"
	@echo "make smoke      Check the EIA API key works"
	@echo "make test       Run the test suite"
	@echo "make clean      Delete generated data and reports (keeps raw pull)"
	@echo "make distclean  Also delete the raw pull"

smoke:
	$(PYTHON) scripts/smoke_api.py

pull:
	$(PYTHON) src/01_pull.py

validate:
	$(PYTHON) src/02_validate.py

warehouse:
	$(PYTHON) src/04_export_for_bi.py

csv:
	$(PYTHON) src/04_export_for_bi.py --csv

bootstrap:
	$(PYTHON) src/03b_bootstrap_intervals.py

xlsx:
	$(PYTHON) src/05_build_assumptions_xlsx.py

dashboard:
	$(PYTHON) src/06_build_dashboard.py

# Rewrites powerbi/grid_stress.Report from src/08_build_powerbi_report.py.
# It does NOT touch the semantic model, and it DOES discard any layout
# changes made inside Power BI Desktop.
powerbi:
	$(PYTHON) src/08_build_powerbi_report.py

memo:
	$(PYTHON) src/07_build_memo.py

# Order matters: the bootstrap reads the exported parquet, and the dashboard
# and memo both read the bootstrap intervals.
all: pull validate warehouse bootstrap xlsx dashboard memo

test:
	$(PYTHON) -m pytest -q

clean:
	rm -rf data/interim/grid.duckdb data/processed/*.parquet
	rm -f reports/data_quality_report.md reports/data_quality_summary.csv
	rm -f reports/bootstrap_intervals.csv reports/assumptions.xlsx reports/memo.pdf
	rm -f reports/memo_chart.png
	rm -rf dashboard/dashboard.html docs/screenshots/*.png

distclean: clean
	rm -f data/raw/*.parquet reports/pull_manifest.csv
