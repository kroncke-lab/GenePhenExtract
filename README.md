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

### Command-line Arguments

**Required:**
- `gene`: Primary gene symbol to query (e.g., BRCA1, TP53, SCN5A)

**Optional:**
- `--synonym`: Gene synonym (can be provided multiple times)
- `--retmax`: Maximum number of PubMed results to retrieve (default: 100)
- `--email`: Contact email for PubMed API requests (recommended for compliance)
- `--api-key`: NCBI API key for higher rate limits
- `--output`: Output file path (default: literature_results.json)
- `--format`: Output format - json, csv, or sqlite (default: json)
- `--log-level`: Logging verbosity - DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)

### Examples

**Basic usage with default JSON output:**
```bash
python collect_literature.py SCN5A
```

**Multiple synonyms with CSV output:**
```bash
python collect_literature.py SCN5A \
  --synonym "Sodium voltage-gated channel alpha subunit 5" \
  --synonym "Nav1.5" \
  --format csv \
  --output scn5a_literature.csv
```

**Retrieve more results with API key:**
```bash
python collect_literature.py TP53 \
  --synonym "tumor protein p53" \
  --retmax 500 \
  --email your.email@example.com \
  --api-key YOUR_NCBI_API_KEY \
  --format sqlite \
  --output tp53_articles.db
```

### Output Format

The collected metadata includes:
- **pmid**: PubMed identifier
- **title**: Article title
- **abstract**: Article abstract (when available)
- **first_author**: First author name
- **publication_year**: Year of publication
- **journal**: Journal name
- **xml_available**: Boolean indicating if PMC XML download is available
- **patient_level_evidence**: Boolean indicating if article likely contains patient-level data

The script writes the collected metadata to the specified output path. JSON and CSV outputs are human-readable, while the SQLite option creates a queryable `articles` table.

## Features in Detail

### Patient-Level Evidence Detection

The tool uses keyword heuristics to flag articles that likely contain patient-level information. Articles are marked as having patient-level evidence if their title or abstract contains any of these keywords:

- patient / patients
- case / case report / cases
- cohort
- subjects
- clinical

This simple heuristic helps researchers quickly identify articles with potential clinical data for manual review.

### XML Download Availability

The tool checks whether each article has a PubMed Central (PMC) identifier. Articles with a PMCID can typically be downloaded in XML format for text mining and automated analysis, while those without a PMCID may require manual download or have restricted access.

## Development

Run the unit tests with:

```bash
pytest
```

Contributions that improve query generation, metadata parsing, or output formats are welcome.

## Module Structure

```
src/gene_literature/
├── __init__.py          # Package exports
├── collector.py         # High-level orchestration and query building
├── pubmed_client.py     # PubMed API client and metadata extraction
└── writer.py            # Output formatting (JSON, CSV, SQLite)
```

## Programmatic Usage

You can also use the library programmatically in your Python code:

```python
from gene_literature import LiteratureCollector, PubMedClient

# Initialize the client
client = PubMedClient(
    api_key="YOUR_API_KEY",  # Optional
    email="your.email@example.com"  # Optional but recommended
)

# Create collector and fetch articles
collector = LiteratureCollector(client)
articles = collector.collect(
    gene="BRCA1",
    synonyms=["Breast cancer 1", "BRCA1 gene"],
    retmax=100
)

# Process results
for article in articles:
    print(f"{article.pmid}: {article.title}")
    print(f"  Author: {article.first_author}")
    print(f"  Year: {article.publication_year}")
    print(f"  Patient data: {article.patient_level_evidence}")
    print(f"  XML available: {article.xml_available}")
```
