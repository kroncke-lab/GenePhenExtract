# CLAUDE.md - AI Assistant Guide for GenePhenExtract

**Last Updated:** 2025-12-02
**Project:** Gene Literature Collector
**Version:** 0.2.0

## Project Overview

GenePhenExtract is a Python-based pipeline for gathering structured publication metadata about genes of interest from PubMed. The tool retrieves matching articles, extracts useful metadata, evaluates whether articles likely report patient-level information, and provides downloadable URLs for literature access.

### Key Features

- Automatic synonym discovery from NCBI Gene database
- LLM-based relevance filtering using Claude AI (Anthropic)
- LLM-based synonym relevance checking
- Patient-level evidence detection using keyword heuristics
- Multiple output formats (JSON, CSV, SQLite, URLs)
- Automated file renaming and organization for downloaded PDFs
- PMC XML availability detection

### Core Use Case

Researchers studying specific genes (e.g., BRCA1, SCN5A, TP53) need to collect relevant literature. This tool automates PubMed searches, filters irrelevant papers (e.g., distinguishing "TTR" as Transthyretin gene vs "time to reimbursement"), and organizes the results for further analysis.

---

## Repository Structure

```
GenePhenExtract/
├── src/gene_literature/         # Main package source
│   ├── __init__.py              # Package exports
│   ├── collector.py             # High-level orchestration and query building
│   ├── pubmed_client.py         # PubMed E-utilities API client
│   ├── synonym_finder.py        # NCBI Gene database synonym discovery
│   ├── synonym_relevance_checker.py  # LLM-based synonym assessment
│   ├── relevance_checker.py     # LLM-based paper relevance filtering
│   └── writer.py                # Output formatting (JSON, CSV, SQLite, URLs)
├── tests/                       # Unit tests
│   └── test_collector.py        # Main test suite
├── collect_literature.py        # CLI entry point for literature collection
├── rename_downloads.py          # CLI tool for organizing downloaded files
├── pyproject.toml               # Package configuration and dependencies
├── README.md                    # User-facing documentation
└── CLAUDE.md                    # This file - AI assistant guide

```

### Key Modules

#### `collector.py`
- **Purpose:** High-level orchestration of literature collection workflow
- **Key Functions:**
  - `build_gene_query()`: Constructs PubMed search queries from gene + synonyms
  - `LiteratureCollector.collect()`: Main entry point - searches PubMed, fetches metadata, filters results
- **Dependencies:** `PubMedClient`, optional `RelevanceChecker`

#### `pubmed_client.py`
- **Purpose:** Direct interaction with NCBI PubMed E-utilities API
- **Key Classes:**
  - `PubMedClient`: HTTP client with retry logic, rate limiting
  - `ArticleMetadata`: Dataclass holding all article metadata fields
- **Rate Limiting:** Respects NCBI guidelines (~3 requests/second)
- **Batching:** Processes PMIDs in batches of 200 to avoid URI length limits (HTTP 414)
- **Retry Logic:** Exponential backoff on failures (up to 3 retries)

#### `synonym_finder.py`
- **Purpose:** Automatic gene synonym discovery from NCBI Gene database
- **Key Functions:**
  - `SynonymFinder.find_gene_synonyms()`: Queries NCBI Gene for aliases
  - `interactive_synonym_selection()`: CLI prompt for synonym selection
- **Integration:** Can optionally use `SynonymRelevanceChecker` for LLM-based filtering

#### `relevance_checker.py`
- **Purpose:** LLM-based filtering of irrelevant papers
- **Model Used:** `claude-3-5-haiku-20241022` (cost-effective)
- **Key Pattern:** Uses Anthropic API to assess if papers are genuinely about the gene vs. abbreviation collisions
- **Fallback:** Gracefully degrades if API key missing or anthropic package unavailable

#### `writer.py`
- **Purpose:** Export collected metadata in multiple formats
- **Formats Supported:**
  - `json`: Pretty-printed JSON with all fields
  - `csv`: Flat CSV with standard fields
  - `sqlite`: SQLite database with `articles` table
  - `urls`: Formatted text file with downloadable URLs

---

## Development Workflows

### Setting Up the Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install package in editable mode
pip install -e .

# Install with optional dependencies
pip install -e ".[relevance]"  # Adds anthropic for LLM features
pip install -e ".[test]"       # Adds pytest for testing
pip install -e ".[dev]"        # Includes test dependencies
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_collector.py

# Run with coverage (if installed)
pytest --cov=gene_literature
```

**Test Patterns:**
- Uses `DummyPubMedClient` for mocking PubMed API calls
- Provides sample XML payloads (`SAMPLE_XML`, `SAMPLE_XML_PMC_FORMAT`)
- Tests both old (`IdType="pmcid"`) and new (`IdType="pmc"`) PubMed formats
- Uses `tmp_path` fixture for file I/O tests

### Git Workflow

**Branch Naming Convention:**
- Feature branches: `claude/feature-description-<session-id>`
- Main branch: `main` (or default branch - check with `git branch -a`)

**Commit Message Patterns:**
Based on recent commits, follow these conventions:
- Use imperative mood: "Add feature" not "Added feature"
- Be descriptive but concise
- Reference purpose/context when helpful

Examples from history:
- "Add LLM-based relevance filtering to remove irrelevant papers"
- "Fix PMCID and XML detection to support multiple PubMed formats"
- "Fix HTTP 414 error by batching PubMed metadata requests"

**Never:**
- Push to `main` directly
- Force push to shared branches
- Commit sensitive API keys or credentials

---

## Code Conventions and Patterns

### Python Style

**Type Hints:**
- Use throughout the codebase
- Import from `__future__ import annotations` for forward references
- Optional types clearly marked with `Optional[T]`

**Example:**
```python
from __future__ import annotations

from typing import List, Optional, Sequence

def build_gene_query(gene: str, synonyms: Optional[Sequence[str]] = None) -> str:
    """Build a simple PubMed query using the provided gene and synonyms."""
    ...
```

**Logging:**
- Use module-level logger: `logger = logging.getLogger(__name__)`
- Log levels:
  - `DEBUG`: Low-level details (query construction, XML parsing)
  - `INFO`: Major workflow steps (searching PubMed, fetching metadata)
  - `WARNING`: Degraded functionality (missing API key, fallback behavior)
  - `ERROR`: Recoverable errors (failed API calls with retry)
  - `CRITICAL`: Not used in this codebase

**Example:**
```python
logger.info("Searching PubMed with query: %s", query)
logger.debug("Constructed PubMed query: %s", query)
logger.warning("Relevance filtering requested but no RelevanceChecker provided")
```

**Dataclasses:**
- Use `@dataclass` for data-holding classes
- Include `to_dict()` method for serialization
- Example: `ArticleMetadata`, `RelevanceScore`, `GeneSynonym`

**Error Handling:**
- Custom exceptions inherit from appropriate base (e.g., `PubMedError(RuntimeError)`)
- Graceful degradation for optional features (LLM checking)
- Retry logic with exponential backoff for network calls

**Docstrings:**
- Use triple-quoted strings for all public functions/classes
- Google-style format preferred
- Include Args, Returns sections when applicable

### API Integration Patterns

**PubMed E-utilities:**
- Base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`
- User-Agent header required: `GeneLiteratureCollector/0.1 (+https://github.com/openai)`
- Rate limiting: ~3 requests/second (0.34s delay between batches)
- Authentication: Optional API key increases rate limits

**Anthropic Claude:**
- Model: `claude-3-5-haiku-20241022` for cost-effectiveness
- API key from environment variable `ANTHROPIC_API_KEY` or parameter
- Short max_tokens (200) for structured responses
- JSON response parsing with regex fallback

### Optional Dependencies Pattern

The project uses optional dependency groups defined in `pyproject.toml`:

```toml
[project.optional-dependencies]
relevance = [
    "anthropic>=0.39.0",
]
test = [
    "pytest>=7.0.0",
]
```

**Pattern for Optional Imports:**
```python
try:
    from .relevance_checker import RelevanceChecker
    RELEVANCE_CHECKER_AVAILABLE = True
except ImportError:
    RELEVANCE_CHECKER_AVAILABLE = False
    logger.debug("RelevanceChecker not available (anthropic package not installed)")
```

This allows the package to work without `anthropic` installed, with graceful degradation.

---

## Common Tasks for AI Assistants

### 1. Adding a New Output Format

**Steps:**
1. Add format choice to `collect_literature.py` argument parser
2. Implement `_write_<format>()` function in `writer.py`
3. Add format handling in `write_metadata()` dispatcher
4. Update tests in `test_collector.py`
5. Document in README.md

**Key Files:**
- `src/gene_literature/writer.py`
- `collect_literature.py`
- `tests/test_collector.py`
- `README.md`

### 2. Adding New Metadata Fields

**Steps:**
1. Add field to `ArticleMetadata` dataclass in `pubmed_client.py`
2. Extract field in `PubMedClient.fetch_metadata()` XML parsing
3. Update CSV fieldnames in `writer.py:_write_csv()`
4. Update SQLite schema in `writer.py:_write_sqlite()`
5. Update test assertions in `test_collector.py`
6. Document in README.md

**Key Patterns:**
- Use `Optional[T]` for fields that may be missing
- Add to end of dataclass to maintain backward compatibility
- Update `to_dict()` automatically via `@dataclass` + `asdict()`

### 3. Modifying PubMed Query Logic

**Location:** `src/gene_literature/collector.py:build_gene_query()`

**Current Pattern:**
```python
terms = [gene, *(synonyms or [])]
quoted = [f'"{term}"[Title/Abstract]' for term in sanitized]
query = " OR ".join(quoted)
```

**Considerations:**
- PubMed search field tags: `[Title/Abstract]`, `[MeSH Terms]`, etc.
- Boolean operators: `OR`, `AND`, `NOT`
- Quote terms for exact matching
- Test with actual PubMed API to verify syntax

### 4. Improving Relevance Filtering

**Location:** `src/gene_literature/relevance_checker.py:check_relevance()`

**Current Approach:**
- Sends title + abstract to Claude Haiku
- Uses structured prompt with JSON response format
- Parses JSON with regex fallback

**Improvement Ideas:**
- Batch processing (currently sequential)
- Caching results to avoid re-checking same papers
- Fine-tuning prompt based on specific gene types
- Adding few-shot examples to prompt

**Cost Optimization:**
- Current: ~$0.001-0.003 per paper
- Uses Haiku model (cheapest)
- max_tokens=200 keeps responses short
- Consider batching to reduce API overhead

### 5. Adding New CLI Options

**Steps:**
1. Add argument in `collect_literature.py:parse_args()`
2. Pass argument through to relevant function
3. Update help text
4. Document in README.md examples section

**Naming Convention:**
- Use `--kebab-case` for CLI flags
- Use `snake_case` for Python variable names
- Boolean flags: use `action="store_true"`

### 6. Handling XML Format Changes

**Context:** PubMed periodically updates XML schema

**Key Patterns:**
- Check both uppercase and lowercase attribute names: `IdType` vs `idtype`
- Support multiple identifier formats: `"pmc"` and `"pmcid"`
- Use robust XPath selectors: `.//ArticleIdList/ArticleId`
- Add defensive `None` checks

**Example from codebase:**
```python
id_type = article_id.get("IdType") or article_id.get("idtype") or ""
id_type_lower = id_type.lower()
if id_type_lower in ("pmc", "pmcid"):
    # Handle both formats
```

---

## Dependencies and Requirements

### Core Dependencies
- **Python:** >= 3.9
- **Standard Library Only:** No dependencies for basic functionality
  - `urllib` for HTTP requests
  - `xml.etree.ElementTree` for XML parsing
  - `sqlite3` for database export
  - `json`, `csv` for data serialization

### Optional Dependencies
- **anthropic** >= 0.39.0: Required for LLM-based relevance filtering and synonym checking
- **pytest** >= 7.0.0: Required for running tests

### External APIs
- **NCBI E-utilities:** PubMed search and metadata retrieval
  - Free tier: ~3 requests/second
  - With API key: ~10 requests/second
  - Email recommended for compliance
- **Anthropic Claude API:** LLM-based filtering
  - Requires API key
  - Uses Haiku model for cost optimization

---

## Testing Strategy

### Test Coverage

**Current Test File:** `tests/test_collector.py`

**Patterns:**
- Mock PubMed API with `DummyPubMedClient` class
- Use sample XML payloads for predictable parsing
- Test both success paths and error handling
- Use `pytest.mark.parametrize` for multiple test cases

**What to Test:**
- Query construction with various inputs
- XML parsing for different PubMed formats
- Output format generation
- Error handling and edge cases

**What NOT to Test:**
- Actual PubMed API calls (use mocks)
- Actual Claude API calls (use mocks or skip if API key missing)
- Network-dependent behavior

### Adding Tests

**Pattern:**
```python
def test_feature_name(tmp_path: Path):
    # Arrange
    client = DummyPubMedClient(["12345"], SAMPLE_XML)
    collector = LiteratureCollector(client)

    # Act
    results = collector.collect("GENE")

    # Assert
    assert len(results) == 1
    assert results[0].pmid == "12345"
```

---

## Important Implementation Details

### Rate Limiting and Batching

**Why:** NCBI requires respectful API usage

**Implementation:**
- 0.34 second delay between batches (≈3 requests/second)
- Batch size: 200 PMIDs per request (avoids HTTP 414 URI Too Long)
- Located in: `pubmed_client.py:fetch_metadata()`

**Pattern:**
```python
for batch_num in range(total_batches):
    # ... fetch batch ...
    if batch_num < total_batches - 1:
        time.sleep(0.34)  # Respect rate limits
```

### XML Parsing Robustness

**Challenge:** PubMed XML schema has evolved over time

**Solutions:**
- Check multiple attribute name variations (uppercase/lowercase)
- Accept multiple identifier types (`"pmc"` and `"pmcid"`)
- Gracefully handle missing fields with `Optional` types
- Use defensive `None` checks throughout

**Pattern:**
```python
def _find_text(root: ET.Element, selector: str) -> Optional[str]:
    element = root.find(selector)
    if element is None:
        return None
    text = element.text or ""
    text = text.strip()
    return text or None
```

### Patient-Level Evidence Detection

**Method:** Simple keyword heuristics

**Keywords:**
```python
PATIENT_KEYWORDS = {
    "patient", "patients", "case", "case report", "cases",
    "cohort", "subjects", "clinical"
}
```

**Limitation:** Basic pattern matching, may have false positives/negatives

**Future Improvement Opportunity:** Could use LLM-based detection similar to relevance checking

### Relevance Filtering Prompt Strategy

**Key Insight:** The prompt is tuned to err on the side of inclusion

**Pattern:**
- Explicitly lists what to EXCLUDE (non-genetic topics, wrong abbreviation usage)
- States "when uncertain, treat it as relevant"
- Asks for JSON response format for structured parsing
- Includes confidence score to allow threshold tuning

**Customization Point:** The prompt in `relevance_checker.py` can be tuned for specific research needs

---

## Environment Variables

- `ANTHROPIC_API_KEY`: Required for LLM-based relevance filtering and synonym checking
- `NCBI_API_KEY`: Optional, increases PubMed API rate limits (can also pass via `--api-key`)

---

## Debugging Tips

### Enable Debug Logging

```bash
python collect_literature.py GENE --log-level DEBUG
```

This shows:
- Exact PubMed query constructed
- Number of PMIDs returned
- XML parsing details
- Relevance check results for each paper

### Common Issues

**Issue:** HTTP 414 URI Too Long
**Solution:** Already fixed via batching in `pubmed_client.py`
**Commit:** `27d26d1 Fix HTTP 414 error by batching PubMed metadata requests`

**Issue:** PMCID not detected
**Solution:** Support both `IdType="pmc"` and `IdType="pmcid"`
**Commit:** `9c16760 Fix PMCID and XML detection to support multiple PubMed formats`

**Issue:** Relevance filtering not working
**Check:**
1. Is `anthropic` package installed? (`pip install anthropic`)
2. Is `ANTHROPIC_API_KEY` set?
3. Is `--filter-irrelevant` flag used?

**Issue:** Too many/few papers filtered
**Solution:** Adjust `--min-relevance-score` threshold (default: 0.7)

---

## Key Conventions Summary

### When Writing Code
- Use type hints consistently
- Import with `from __future__ import annotations`
- Add docstrings to public functions
- Use module-level loggers
- Handle optional dependencies gracefully
- Prefer dataclasses for data structures

### When Modifying Features
- Read existing code first to understand patterns
- Maintain backward compatibility for data formats
- Update all affected files (module, CLI, tests, docs)
- Test with actual PubMed API when changing query logic
- Consider rate limiting and API costs

### When Adding Tests
- Use `DummyPubMedClient` for mocking
- Use `tmp_path` for file I/O
- Test edge cases and error handling
- Don't rely on network/external APIs

### When Updating Documentation
- Update README.md for user-facing changes
- Update CLAUDE.md for architectural changes
- Include examples in CLI help text
- Document cost implications for LLM features

---

## Recent Development History

Based on recent commits:

1. **Relevance Filtering** (PR #22, #21): Adjusted LLM prompt for better filtering criteria
2. **LLM Synonym Checking** (PR #20): Added LLM-based relevance checking for auto-discovered synonyms
3. **Initial Relevance Filtering** (PR #19): Implemented LLM-based paper filtering
4. **Synonym Discovery** (PR #18): Added automatic NCBI Gene synonym discovery
5. **PMCID Detection Fix** (PR #17): Fixed XML parsing for multiple PubMed formats
6. **Batching Fix** (PR #16): Fixed HTTP 414 errors via batching
7. **URL Extraction** (PR #15): Added URL output format and file renaming tool

---

## Contact and Resources

- **Repository:** https://github.com/kroncke-lab/GenePhenExtract (assumed based on branch structure)
- **PubMed E-utilities Documentation:** https://www.ncbi.nlm.nih.gov/books/NBK25501/
- **Anthropic API Documentation:** https://docs.anthropic.com/
- **Package Name:** gene-literature-collector

---

## AI Assistant Quick Reference

### When asked to add a feature:
1. Read relevant module files first
2. Understand existing patterns
3. Maintain consistency with current code style
4. Update tests, docs, and CLI together
5. Consider backward compatibility

### When asked to fix a bug:
1. Check if similar issues were fixed before (see git log)
2. Add test case that reproduces the bug
3. Fix the bug
4. Verify test passes
5. Check for similar patterns elsewhere in codebase

### When asked about the project:
1. Refer to README.md for user-facing information
2. Refer to this CLAUDE.md for architecture and conventions
3. Check module docstrings for implementation details
4. Look at tests for usage examples

---

**End of CLAUDE.md**
