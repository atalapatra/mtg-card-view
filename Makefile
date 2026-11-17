ifeq ($(OS),Windows_NT)
PYTHON ?= .venv/Scripts/python
else
PYTHON ?= .venv/bin/python
endif

.PHONY: help reset reset-cache

help:
	@echo "make reset        delete all local data: collections, boards, graph layouts and cache (asks first)"
	@echo "make reset-cache  delete only the download cache (Scryfall/EDHREC data, re-downloaded as needed)"

reset:
	$(PYTHON) scripts/reset_data.py

reset-cache:
	$(PYTHON) scripts/reset_data.py --cache
