PYTHON ?= python

all: build

clean:
	$(PYTHON) setup.py clean

test: build
	$(PYTHON) test.py

sdist:
	$(PYTHON) setup.py sdist

build:
	CYTHONIZE_MPACK=1 $(PYTHON) setup.py build_ext --inplace

.PHONY: all build test clean
