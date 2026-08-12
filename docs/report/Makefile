# Two passes: the second resolves \ref and \cite forward references.
report: grail_v_report.pdf

grail_v_report.pdf: grail_v_report.tex
	pdflatex -interaction=nonstopmode $< >/dev/null
	pdflatex -interaction=nonstopmode $< >/dev/null
	@echo "built $@"

clean:
	rm -f *.aux *.log *.out *.toc

.PHONY: report clean
