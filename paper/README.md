# Paper — arXiv build

LaTeX source for the gridpulse preprint. Content is a faithful transcription of
[`../PAPER.md`](../PAPER.md); every number traces to committed outputs
(`../data/multiverse_*.csv`, `../data/gap.json`, `../data/mef_triangulation.csv`,
`../FINDINGS.md`).

## Files

- `paper.tex` — self-contained source. Manual `thebibliography` (no BibTeX pass),
  so it compiles in one shot.
- `figs/` — the four figures, copied from `../docs/figs/`.
- `paper.pdf` — the built preprint (8 pages, letter).

## Build

Uses [tectonic](https://tectonic-typesetting.github.io) (single binary, pulls
packages on demand; no full TeX Live needed):

```sh
brew install tectonic      # once
cd paper && tectonic paper.tex
```

That writes `paper.pdf`. Any LaTeX engine works too: `pdflatex paper.tex` twice
(no `bibtex` step needed).

## Submit to arXiv

arXiv wants the source, not the PDF. Bundle `paper.tex` + `figs/`:

```sh
cd paper && tar --disable-copyfile -czf arxiv-submission.tar.gz paper.tex figs/
```

Upload `arxiv-submission.tar.gz`; arXiv compiles it server-side. The tarball is
regenerated on demand and is git-ignored. Verified to compile from a clean
extract.

Suggested categories: primary `eess.SY`, cross-list `econ.EM`.

## Regenerating figures

The figures come from the pipeline, not from here:

```sh
gridpulse phase3        # regenerates docs/figs/*.png
cp ../docs/figs/{spec_curve,validation_aef,aef_vs_mef,rank_scatter}.png figs/
```
