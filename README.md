# Gene Literature Collector

This repository provides a focused pipeline for gathering structured publication metadata about genes of interest from PubMed. Given a gene symbol (and optional synonyms), the tool retrieves matching articles, extracts useful metadata, evaluates whether the article likely reports patient-level information, and records whether a PubMed Central XML download is available.

## Features

- Build reproducible PubMed queries for a gene and its synonyms.
- Retrieve PubMed metadata including PubMed ID, first author, publication year, and journal name.
- Flag articles that likely contain patient-level information using simple keyword heuristics.
- Detect whether an article includes a PubMed Central XML download.
- Export the collected records as JSON, CSV, or SQLite.
- Clear logging to trace each stage of the collection workflow.

## Installation

The project targets Python 3.9 or later. Install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

Run the end-to-end pipeline via the `collect_literature.py` script:

```bash
python collect_literature.py BRCA1 --synonym "Breast cancer 1" --format csv --output brca1_articles.csv
```

Optional flags include:

- `--retmax`: maximum number of PubMed results to retrieve (default: 100)
- `--email`: contact email for PubMed API requests
- `--api-key`: NCBI API key for higher rate limits
- `--log-level`: logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)

The script writes the collected metadata to the specified output path. JSON and CSV outputs are human-readable, while the SQLite option creates a queryable `articles` table.

## Development

Run the unit tests with:

```bash
pytest
```

Contributions that improve query generation, metadata parsing, or output formats are welcome.
