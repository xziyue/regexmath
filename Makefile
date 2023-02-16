SHELL:=/bin/bash
PY_BUILD_CMD=python3 pyl3helper2/api.py
TEX_BUILD_CMD=latexmk -pdflatex -interaction=nonstopmode -shell-escape
INPUT_FILE=regexmath/regexmath.sty
PKG_NAME=regexmath
PKG_NAME_UPPER=ReM
OUTPUT_FILE=regexmath.sty
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
TEST_CALL:=cd $(ROOT_DIR)/test && TEXINPUTS=$(ROOT_DIR)/build:$(TEXINPUTS) $(TEX_BUILD_CMD)

all: regexmath pkg_doc

prepare_build_directory:
	mkdir -p build

regexmath: prepare_build_directory
	PYTHONPATH=$(ROOT_DIR):$(PYTHONPATH) $(PY_BUILD_CMD) $(INPUT_FILE) -n $(PKG_NAME) -N $(PKG_NAME_UPPER) -o build/$(OUTPUT_FILE)

pkg_doc: regexmath
	cd $(ROOT_DIR)/doc && TEXINPUTS=$(ROOT_DIR)/build:$(TEXINPUTS) $(TEX_BUILD_CMD) regexmath.tex

test-regexmath: regexmath
	$(TEST_CALL) test.tex

