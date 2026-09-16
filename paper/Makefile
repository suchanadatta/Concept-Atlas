# Build the paper. `make` produces paper.pdf; `make check` fails loudly if
# LaTeX emitted a single warning, over- or underfull box included.
LATEXMK ?= latexmk
MAIN    := paper
PY      ?= ../.venv/bin/python

.PHONY: all analysis check clean distclean

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex refs.bib generated/numbers.tex
	$(LATEXMK) -pdf -halt-on-error -interaction=nonstopmode -file-line-error $(MAIN).tex

# Every number in the text is generated from the analysis output, never typed.
generated/numbers.tex: analysis/make_numbers.py $(wildcard data/*.json)
	$(PY) analysis/make_numbers.py

analysis:
	$(PY) analysis/a0_dates.py
	$(PY) analysis/a0b_date_validation.py
	$(PY) analysis/a1_corpus.py
	$(PY) analysis/a2_graph.py
	$(PY) analysis/a3_map_vs_vectors.py
	$(PY) analysis/a4_retrieval.py
	$(PY) analysis/a5_diachrony.py
	$(PY) analysis/a6_authorship.py
	$(PY) analysis/make_numbers.py

check: $(MAIN).pdf
	@$(PY) tools/check_log.py $(MAIN).log

clean:
	$(LATEXMK) -c $(MAIN).tex
	rm -f $(MAIN).bbl

distclean: clean
	rm -f $(MAIN).pdf
