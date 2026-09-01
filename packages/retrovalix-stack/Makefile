.PHONY: test sample backtest paper live-check

export PYTHONPATH := $(CURDIR)/src

test:
	python -m unittest discover -s tests -v

sample:
	python -m valixstack.cli generate --out data/sample.csv --rows 1000

backtest: sample
	python -m valixstack.cli backtest --csv data/sample.csv

paper: sample
	python -m valixstack.cli paper --csv data/sample.csv

live-check:
	python -m valixstack.cli live-check
