ifeq ($(OS),Windows_NT)
# Backslashes so cmd.exe can run it; quoted in recipes so a POSIX sh (if make picks one) keeps them too.
PYTHON ?= .venv\Scripts\python.exe
else
PYTHON ?= .venv/bin/python
endif

.PHONY: help reset reset-cache

help:
	@echo "make reset        delete all local data: collections, boards, graph layouts and cache (asks first)"
	@echo "make reset-cache  delete only the download cache (Scryfall/EDHREC data, re-downloaded as needed)"

reset:
	"$(PYTHON)" scripts/reset_data.py

reset-cache:
	"$(PYTHON)" scripts/reset_data.py --cache
