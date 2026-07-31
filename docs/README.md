# BuEM Documentation

Sphinx source for BuEM's documentation, hosted at
[buem.readthedocs.io](https://buem.readthedocs.io/). Developer-oriented:
aimed at teams integrating BuEM (via its REST API / Docker) or contributing
to the codebase itself.

## Structure

```
docs/
├── README.md              # this file
├── source/                # Sphinx source
│   ├── index.rst          # master toctree
│   ├── conf.py             # Sphinx configuration
│   ├── introduction/      # what BuEM is, how it works
│   ├── installation/      # conda / Docker / dev setup
│   ├── modules/           # code-level reference (thermal, config,
│   │                      #   occupancy, weather, buildings, apis,
│   │                      #   integration, results, technology)
│   ├── api_integration/   # REST API integration guide
│   └── deployment/        # Docker / production deployment
├── build/                  # generated output (gitignored, not committed)
├── requirements.txt        # doc-build deps (ReadTheDocs uses the
│                           #   pyproject.toml [docs] extra instead)
├── Makefile / make.bat     # standard Sphinx build scripts
└── build_docs.bat          # conda-aware Windows build helper
```

## Building locally

```bash
conda activate buem_env
pip install -e ..[docs]      # from docs/, installs buem + sphinx + theme
cd docs
make html                    # or: make.bat html / build_docs.bat
```

Output lands in `docs/build/html/index.html`.

Alternative direct invocation: `sphinx-build -b html source build`.
Live-reloading local server: `sphinx-autobuild source build/html`.

## Contributing

- reStructuredText (`.rst`), one topic per file, following the existing
  `modules/` per-package-reference pattern.
- Build locally and check for Sphinx warnings before submitting —
  `make html` should complete clean.
- `modules/results.rst` and `modules/technology.rst` document
  currently-nonexistent code (`src/buem/results/`, `src/buem/technology/`
  — see `CLAUDE.md`'s "Open follow-ups" in the repo root) — update those
  pages if/when that code is actually implemented, not before.
- See `../CONTRIBUTE.md` for repo-wide contribution guidelines.

## Deployment

Pushes to `main` trigger an automatic ReadTheDocs rebuild
(`../.readthedocs.yaml`). No manual deployment step.
