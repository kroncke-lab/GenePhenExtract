# Gene Literature Collector

This repository provides a focused pipeline for gathering structured publication metadata about genes of interest from PubMed. Given a gene symbol (and optional synonyms), the tool retrieves matching articles, extracts useful metadata, evaluates whether the article likely reports patient-level information, and records whether a PubMed Central XML download is available.

## Features

- **Automatic synonym discovery** - Query NCBI Gene database to find gene aliases and synonyms with interactive selection.
- **LLM-based relevance filtering (NEW!)** - Use Claude AI to filter out irrelevant papers (e.g., "TTR" as "time to reimbursement" vs the gene).
- Build reproducible PubMed queries for a gene and its synonyms.
- Retrieve PubMed metadata including PubMed ID, first author, publication year, and journal name.
- Flag articles that likely contain patient-level information using simple keyword heuristics.
- Detect whether an article includes a PubMed Central XML download.
- **Extract downloadable URLs** (PubMed page, PMC full-text, PMC PDF, DOI/publisher links).
- Export the collected records as JSON, CSV, SQLite, or **URLs list** for batch downloading.
- **Automated file renaming and organization** - rename downloaded PDFs/documents to standardized format.
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
- `--auto-synonyms`: Automatically find gene synonyms using NCBI Gene database and prompt for selection
- `--include-other-designations`: Include verbose 'other designations' when finding synonyms (use with --auto-synonyms)
- `--retmax`: Maximum number of PubMed results to retrieve (default: 100)
- `--email`: Contact email for PubMed API requests (recommended for compliance)
- `--api-key`: NCBI API key for higher rate limits
- `--output`: Output file path (default: literature_results.json)
- `--format`: Output format - json, csv, sqlite, or urls (default: json)
- `--filter-irrelevant`: Use LLM to filter out irrelevant papers (requires ANTHROPIC_API_KEY)
- `--anthropic-api-key`: Anthropic API key for relevance checking
- `--min-relevance-score`: Minimum relevance score (0.0-1.0) to keep papers (default: 0.7)
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

### Automatic Synonym Discovery

The tool can automatically discover gene synonyms from the NCBI Gene database and let you interactively select which ones to include in your PubMed search. This helps ensure comprehensive literature coverage without having to manually research all gene aliases.

**Basic auto-synonym usage:**
```bash
python collect_literature.py BRCA1 --auto-synonyms
```

When you use `--auto-synonyms`, the tool will:
1. Query the NCBI Gene database for the specified gene
2. Retrieve official gene symbols, aliases, and other designations
3. Display an interactive prompt showing all found synonyms grouped by type
4. Let you select which synonyms to include in the search

**Example interactive prompt:**
```
============================================================
Found 8 potential synonyms for 'BRCA1':
============================================================

Official Gene Symbol:
  [1] BRCA1
  → Automatically included in search

Gene Aliases (6 found):
  [1] BRCAI
  [2] BRCC1
  [3] FANCS
  [4] IRIS
  [5] PNCA4
  [6] RNF53

Select synonyms to include in PubMed search:
  - Enter numbers separated by commas (e.g., '1,2,3')
  - Enter 'all' to include all
  - Enter 'aliases' to include all aliases only
  - Enter 'none' to skip synonym expansion
  - Press Enter to accept automatically selected terms

Your selection: aliases
```

**Include verbose designations:**
```bash
python collect_literature.py SCN5A --auto-synonyms --include-other-designations
```

The `--include-other-designations` flag includes longer, more descriptive gene names (e.g., "sodium voltage-gated channel alpha subunit 5"). These can be very comprehensive but may be verbose.

**Combine auto-synonyms with manual ones:**
```bash
python collect_literature.py TP53 \
  --auto-synonyms \
  --synonym "p53" \
  --synonym "tumor suppressor p53" \
  --email your.email@example.com
```

Manual synonyms provided via `--synonym` are automatically included along with any you select from the auto-discovery process.

**Tips for using auto-synonyms:**
- Use `--email` to comply with NCBI API usage guidelines
- Start with basic `--auto-synonyms` before adding `--include-other-designations`
- Review the found synonyms carefully - not all aliases may be relevant for your search
- The 'aliases' option typically gives the best balance of coverage and specificity

#### LLM-Based Synonym Relevance Checking (NEW!)

When using `--auto-synonyms`, you can now enable LLM-based relevance checking to automatically assess which synonyms are most relevant for your gene. This helps filter out generic or misleading terms before you select them.

**Enable LLM synonym checking:**
```bash
python collect_literature.py BRCA1 \
  --auto-synonyms \
  --anthropic-api-key YOUR_ANTHROPIC_API_KEY
```

Or set the environment variable:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
python collect_literature.py BRCA1 --auto-synonyms
```

**What it does:**
1. Fetches synonyms from NCBI Gene database as usual
2. For each synonym, uses Claude AI to assess relevance and specificity
3. Displays synonyms with relevance markers (✓ = relevant, ✗ = not relevant) and confidence scores
4. Shows AI reasoning for top aliases to help you make informed selections
5. Adds a 'relevant' option to automatically select only LLM-approved synonyms

**Example interactive prompt with LLM checking:**
```
============================================================
Found 8 potential synonyms for 'BRCA1':
============================================================

Official Gene Symbol:
  [1] BRCA1 [✓ 98%]
  → Automatically included in search

Gene Aliases (6 found):
  [1] BRCC1 [✓ 85%]
      Historical alias commonly used in literature
  [2] FANCS [✓ 90%]
      Fanconi anemia designation, specific to gene function
  [3] breast cancer 1 [✗ 35%]
      Too generic, likely to match irrelevant papers

Legend: ✓ = LLM assessed as relevant, ✗ = not relevant

Select synonyms to include in PubMed search:
  - Enter numbers separated by commas (e.g., '1,2,3')
  - Enter 'all' to include all
  - Enter 'aliases' to include all aliases only
  - Enter 'relevant' to include only LLM-assessed relevant synonyms
  - Enter 'none' to skip synonym expansion
  - Press Enter to accept automatically selected terms

Your selection: relevant
```

**Benefits:**
- Automatically filters out overly generic terms
- Identifies verbose designations that may add noise
- Provides confidence scores to guide your selection
- Saves time by pre-filtering irrelevant synonyms

### Relevance Filtering (NEW!)

PubMed searches sometimes return irrelevant papers where the gene symbol matches a common abbreviation (e.g., "TTR" could mean the gene Transthyretin OR "time to reimbursement"). To filter these out, the tool now supports LLM-based relevance checking using Claude (Anthropic's AI).

**Installation for relevance filtering:**
```bash
pip install -e ".[relevance]"
```

**Set your Anthropic API key:**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

**Basic usage with filtering:**
```bash
python collect_literature.py TTR \
  --filter-irrelevant \
  --min-relevance-score 0.7
```

**What it does:**
1. Fetches papers from PubMed as usual
2. For each paper, sends the title and abstract to Claude (using the cost-effective Haiku model)
3. Claude assesses whether the paper is genuinely about the gene or uses the symbol for something else
4. Papers below the relevance threshold are filtered out
5. Relevance scores and reasoning are saved in the output metadata

**Command-line options:**
- `--filter-irrelevant`: Enable LLM-based relevance filtering
- `--anthropic-api-key`: Anthropic API key (or set ANTHROPIC_API_KEY environment variable)
- `--min-relevance-score`: Minimum score (0.0-1.0) to keep papers (default: 0.7)

**Example with full workflow:**
```bash
# Search for TTR gene with filtering to remove irrelevant papers
python collect_literature.py TTR \
  --auto-synonyms \
  --filter-irrelevant \
  --min-relevance-score 0.8 \
  --format json \
  --output ttr_filtered.json \
  --email your.email@example.com
```

**Cost considerations:**
- Uses Claude Haiku (most cost-effective model)
- Typical cost: $0.001-0.003 per paper checked
- 100 papers ≈ $0.10-0.30
- 500 papers ≈ $0.50-1.50

**What gets saved:**
The filtered results include two new fields:
- `relevance_score`: Confidence score (0.0-1.0) that the paper is about the gene
- `relevance_reasoning`: Brief explanation of why it was classified as relevant/irrelevant

**Tips:**
- Start with `--min-relevance-score 0.7` and adjust based on results
- Higher scores (0.8-0.9) are more strict, lower scores (0.5-0.7) are more permissive
- Review a few filtered papers to calibrate the threshold for your use case
- The tool logs which papers are filtered out and why

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
- **pmcid**: PubMed Central ID (if available)
- **doi**: Digital Object Identifier (if available)
- **pubmed_url**: Link to PubMed article page
- **pmc_url**: Link to PMC full-text HTML (if available)
- **pmc_pdf_url**: Direct link to PMC PDF download (if available)
- **doi_url**: Link to publisher via DOI (if available)
- **relevance_score**: Relevance confidence score 0.0-1.0 (if relevance filtering was used)
- **relevance_reasoning**: Brief explanation of relevance assessment (if relevance filtering was used)

The script writes the collected metadata to the specified output path. JSON and CSV outputs are human-readable, while the SQLite option creates a queryable `articles` table.

### Extracting Downloadable URLs

Use the `--format urls` option to generate a text file containing all downloadable URLs for the collected articles:

```bash
python collect_literature.py BRCA1 --format urls --output brca1_urls.txt
```

This creates a formatted text file with:
- PubMed article pages (always available)
- PMC full-text HTML links (when available)
- PMC PDF download links (when available)
- DOI/publisher links (when available)

Each URL is annotated with the article's PMID, title, author, year, and journal for easy reference. You can:
- Click URLs individually for manual download
- Use with download tools like `wget` or `curl` for batch downloading
- Import into reference managers

**Example URL output:**
```
# PMID: 12345678
# Title: Example Article Title
# Author: Smith J (2023) - Nature Genetics
https://pubmed.ncbi.nlm.nih.gov/12345678/  # PubMed page
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8765432/  # PMC full-text HTML
https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8765432/pdf/  # PMC PDF
https://doi.org/10.1038/s41588-023-01234-5  # DOI (publisher link)
```

## Automated File Renaming and Organization

After downloading literature files (PDFs, Word docs, etc.), use the `rename_downloads.py` script to automatically rename and organize them based on metadata.

### Usage

```bash
python rename_downloads.py GENE_SYMBOL DOWNLOAD_DIR METADATA_FILE [OPTIONS]
```

**Required arguments:**
- `GENE_SYMBOL`: Gene symbol for organizing files into subfolders
- `DOWNLOAD_DIR`: Directory containing downloaded files
- `METADATA_FILE`: Path to metadata file (JSON or SQLite format)

**Optional arguments:**
- `--output-dir PATH`: Base directory for organized files (default: `organized_literature`)
- `--metadata-format {json,sqlite}`: Format of metadata file (default: `json`)
- `--dry-run`: Preview changes without actually moving files
- `--log-file PATH`: Write detailed processing log to file
- `--log-level LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Example Workflow

1. **Collect metadata and URLs:**
```bash
# Get metadata
python collect_literature.py BRCA1 --format json --output brca1_metadata.json

# Get downloadable URLs
python collect_literature.py BRCA1 --format urls --output brca1_urls.txt
```

2. **Download files manually or with a download tool:**
```bash
# Manual: Click URLs from brca1_urls.txt
# OR use wget to download PMC PDFs:
grep "PMC PDF" brca1_urls.txt | awk '{print $1}' | wget -i - -P downloads/
```

3. **Rename and organize downloaded files:**
```bash
python rename_downloads.py BRCA1 downloads/ brca1_metadata.json \
  --output-dir organized_literature \
  --log-file rename_log.txt
```

### File Naming Convention

Files are renamed to the format: `PMID_LastName_Year_Journal.ext`

**Example:**
- Original: `PMC8765432.pdf` or `download (3).pdf`
- Renamed: `12345678_Smith_2023_Nature_Genetics.pdf`

### How File Matching Works

The script attempts to match downloaded files to metadata records by:
1. Looking for PMID in the filename (e.g., `PMID12345678.pdf`, `12345678.pdf`)
2. Checking against the metadata database
3. Extracting author, year, and journal from metadata
4. Generating standardized filename
5. Moving file to gene-specific subfolder

### Tips for Successful File Matching

- When downloading from PMC, try to keep the PMID in the filename
- If your browser names files generically (e.g., `download.pdf`), rename them to include the PMID first
- Use `--dry-run` to preview changes before committing
- Check the log file to identify any unmatched files

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
├── synonym_finder.py    # Automatic gene synonym discovery from NCBI Gene
├── relevance_checker.py # LLM-based relevance assessment for filtering
└── writer.py            # Output formatting (JSON, CSV, SQLite)
```

## Programmatic Usage

You can also use the library programmatically in your Python code:

### Basic Literature Collection

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
    print(f"  Journal: {article.journal}")
    print(f"  Patient data: {article.patient_level_evidence}")
    print(f"  XML available: {article.xml_available}")
    print(f"  PubMed URL: {article.pubmed_url}")
    if article.pmc_pdf_url:
        print(f"  PMC PDF: {article.pmc_pdf_url}")
    if article.doi_url:
        print(f"  DOI: {article.doi_url}")
```

### Automatic Synonym Discovery

```python
from gene_literature import SynonymFinder, interactive_synonym_selection

# Initialize synonym finder
finder = SynonymFinder(
    email="your.email@example.com",  # Recommended
    api_key="YOUR_API_KEY"  # Optional
)

# Find synonyms for a gene
synonyms = finder.find_gene_synonyms(
    gene="BRCA1",
    include_other_designations=False  # Set to True for verbose names
)

# Display found synonyms
print(f"Found {len(synonyms)} synonyms:")
for syn in synonyms:
    print(f"  - {syn.term} (source: {syn.source})")

# Interactive selection (for CLI scripts)
selected = interactive_synonym_selection("BRCA1", synonyms)

# Or programmatically select synonyms
selected_terms = [syn.term for syn in synonyms if syn.source in ["official_symbol", "alias"]]

# Use selected synonyms in literature collection
articles = collector.collect(
    gene="BRCA1",
    synonyms=selected_terms,
    retmax=100
)
```

### Relevance Filtering (Programmatic)

```python
from gene_literature import LiteratureCollector, PubMedClient
from gene_literature.relevance_checker import RelevanceChecker

# Initialize clients
pubmed_client = PubMedClient(
    api_key="YOUR_NCBI_API_KEY",
    email="your.email@example.com"
)

relevance_checker = RelevanceChecker(
    api_key="YOUR_ANTHROPIC_API_KEY",  # Or set ANTHROPIC_API_KEY env var
    model="claude-3-5-haiku-20241022"  # Cost-effective model
)

# Create collector with relevance checking
collector = LiteratureCollector(
    pubmed_client,
    relevance_checker=relevance_checker
)

# Collect articles with filtering
articles = collector.collect(
    gene="TTR",
    synonyms=["Transthyretin"],
    retmax=100,
    filter_irrelevant=True,
    min_relevance_score=0.7
)

# Process results
print(f"Found {len(articles)} relevant articles after filtering")
for article in articles:
    print(f"\nPMID: {article.pmid}")
    print(f"Title: {article.title}")
    print(f"Relevance: {article.relevance_score:.2f}")
    print(f"Reasoning: {article.relevance_reasoning}")
```
