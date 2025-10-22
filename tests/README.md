# GenePhenExtract Test Suite

Comprehensive testing documentation for the GenePhenExtract project.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Categories](#test-categories)
- [Coverage](#coverage)
- [Benchmarks](#benchmarks)
- [CI/CD Integration](#cicd-integration)

## Overview

The GenePhenExtract test suite includes:

- **Unit tests**: Fast tests for individual components
- **Integration tests**: Tests with real PubMed API calls
- **Benchmarks**: Performance measurements
- **Edge case tests**: Handling of unusual inputs and error conditions

## Test Structure

```
tests/
├── README.md                      # This file
├── test_models.py                 # Data model tests
├── test_extraction.py             # Basic extraction tests
├── test_extraction_advanced.py    # Advanced extraction edge cases
├── test_extraction_config.py      # Configuration tests
├── test_pubmed.py                 # PubMed client unit tests
├── test_pmc.py                    # PMC full-text tests
├── test_hpo.py                    # HPO mapping tests
├── test_pipeline.py               # Pipeline orchestration tests
├── test_pdf_utility.py            # PDF parsing tests
├── test_integration_pubmed.py     # Integration tests (requires network)
└── test_benchmarks.py             # Performance benchmarks
```

## Running Tests

### Install Test Dependencies

```bash
pip install -e ".[test]"
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
pytest tests/test_pipeline.py
pytest tests/test_extraction_advanced.py
```

### Run Tests by Category

#### Unit Tests Only (Fast)

```bash
pytest -m "not integration and not slow"
```

#### Integration Tests (Requires Network)

```bash
pytest -m integration
```

#### Slow Tests

```bash
pytest -m slow
```

#### Skip Benchmarks

```bash
pytest -m "not benchmark"
```

### Run Benchmarks Only

```bash
pytest tests/test_benchmarks.py --benchmark-only
```

### Compare Benchmarks

```bash
# Save baseline
pytest tests/test_benchmarks.py --benchmark-only --benchmark-save=baseline

# Compare against baseline after changes
pytest tests/test_benchmarks.py --benchmark-only --benchmark-compare=baseline
```

## Test Categories

### Unit Tests

Fast tests that don't require network access. These test individual functions and classes in isolation.

**Files:**
- `test_models.py`
- `test_extraction.py`
- `test_extraction_advanced.py`
- `test_extraction_config.py`
- `test_pubmed.py` (with mocked responses)
- `test_hpo.py`
- `test_pipeline.py` (with dummy clients)
- `test_pdf_utility.py`

**Run with:**
```bash
pytest -m "not integration and not slow"
```

### Integration Tests

Tests that make real API calls to PubMed. These require network access and may be subject to rate limiting.

**Files:**
- `test_integration_pubmed.py`
- `test_pmc.py` (marked tests)

**Run with:**
```bash
pytest -m integration
```

**Important notes:**
- Integration tests add delays between requests to avoid rate limiting
- Some tests may be skipped if test data is unavailable
- Set `GEMINI_API_KEY` environment variable to enable Gemini integration tests

### Benchmarks

Performance tests using `pytest-benchmark`.

**File:**
- `test_benchmarks.py`

**Run with:**
```bash
pytest tests/test_benchmarks.py --benchmark-only
```

**Benchmark categories:**
- Model creation benchmarks
- Extraction benchmarks
- HPO mapping benchmarks
- PubMed client benchmarks
- Pipeline benchmarks
- Stress tests (100+ PMIDs)
- Scaling benchmarks

### Slow Tests

Tests that take a long time to run (typically > 5 seconds).

**Run with:**
```bash
pytest -m slow
```

**Skip with:**
```bash
pytest -m "not slow"
```

## Coverage

### Generate Coverage Report

```bash
pytest --cov=genephenextract --cov-report=html
```

View the report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Generate Coverage Report with Terminal Output

```bash
pytest --cov=genephenextract --cov-report=term-missing
```

### Coverage Goals

- Overall coverage: > 85%
- Core modules (pipeline, extraction, pubmed): > 90%
- Edge cases and error handling: Well covered

### Current Coverage by Module

Run to see current coverage:
```bash
pytest --cov=genephenextract --cov-report=term
```

## Benchmarks

### Available Benchmarks

1. **Model Creation**: Benchmark creation of `PhenotypeObservation` and `ExtractionResult`
2. **Extraction**: Benchmark MockExtractor and payload parsing
3. **HPO Mapping**: Benchmark phenotype enrichment (single and batch)
4. **PubMed Parsing**: Benchmark XML parsing and text extraction
5. **Pipeline**: Benchmark end-to-end processing
6. **Stress Tests**: Large batch processing (100+ PMIDs)
7. **Scaling**: How performance scales with data size

### Running Benchmarks

```bash
# Run all benchmarks
pytest tests/test_benchmarks.py --benchmark-only

# Run only fast benchmarks (exclude stress tests)
pytest tests/test_benchmarks.py --benchmark-only -m "not slow"

# Save baseline for comparison
pytest tests/test_benchmarks.py --benchmark-only --benchmark-save=baseline

# Compare with baseline
pytest tests/test_benchmarks.py --benchmark-only --benchmark-compare=baseline

# Generate histogram
pytest tests/test_benchmarks.py --benchmark-only --benchmark-histogram
```

### Benchmark Output

Benchmarks show:
- **Min/Max**: Fastest and slowest iterations
- **Mean**: Average time
- **StdDev**: Standard deviation
- **Median**: Middle value
- **IQR**: Interquartile range
- **Outliers**: Number of outliers detected
- **OPS**: Operations per second

### Performance Goals

- Single PMID processing: < 100ms (with MockExtractor)
- HPO enrichment (single): < 10ms
- XML parsing: < 5ms
- Batch of 10 PMIDs: < 1 second
- Batch of 100 PMIDs: < 10 seconds

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[test]"

      - name: Run unit tests
        run: |
          pytest -m "not integration and not slow" --cov=genephenextract

      - name: Run integration tests (on main branch only)
        if: github.ref == 'refs/heads/main'
        run: |
          pytest -m integration

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: pytest-check
      name: pytest-check
      entry: pytest
      language: system
      pass_filenames: false
      always_run: true
      args: ["-m", "not integration and not slow"]
```

## Writing New Tests

### Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

### Using Fixtures

```python
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_example(sample_data):
    assert sample_data["key"] == "value"
```

### Marking Tests

```python
import pytest

@pytest.mark.integration
def test_real_api_call():
    # Test that makes real API calls
    pass

@pytest.mark.slow
def test_long_running():
    # Test that takes > 5 seconds
    pass

@pytest.mark.benchmark
def test_performance(benchmark):
    result = benchmark(my_function, arg1, arg2)
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("KCNH2", True),
    ("SCN5A", True),
    ("invalid", False),
])
def test_gene_validation(input, expected):
    assert validate_gene(input) == expected
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch

def test_with_mock():
    with patch("genephenextract.pubmed.urllib.request.urlopen") as mock_urlopen:
        mock_response = Mock()
        mock_response.read.return_value = b'{"result": "data"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Test code here
```

## Troubleshooting

### Tests Failing Due to Rate Limiting

Integration tests include delays, but if you still hit rate limits:

1. Increase the delay in `rate_limit` fixture
2. Run fewer integration tests: `pytest -m integration -k "test_specific"`
3. Use PubMed API key for higher rate limits

### Missing Dependencies

```bash
# Ensure all test dependencies are installed
pip install -e ".[test]"

# For Gemini tests
pip install google-generativeai
```

### Benchmark Comparison Errors

If benchmark comparisons fail:

```bash
# Clear old benchmarks
rm -rf .benchmarks/

# Create new baseline
pytest tests/test_benchmarks.py --benchmark-only --benchmark-save=baseline
```

### Coverage Not Generating

```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Run with explicit coverage
pytest --cov=genephenextract --cov-report=html tests/
```

## Best Practices

1. **Keep unit tests fast**: Unit tests should run in milliseconds
2. **Mock external dependencies**: Don't make real API calls in unit tests
3. **Use fixtures**: Share common test setup with fixtures
4. **Test edge cases**: Empty inputs, None values, invalid data
5. **Test error handling**: Ensure errors are caught and handled properly
6. **Add docstrings**: Explain what each test is verifying
7. **Run tests before committing**: Use pre-commit hooks
8. **Monitor coverage**: Aim for >85% coverage
9. **Update tests with code**: Keep tests in sync with implementation
10. **Document test data**: Explain why specific test values are used

## Contributing

When adding new features:

1. Write tests first (TDD approach recommended)
2. Ensure all existing tests pass
3. Add integration tests for API changes
4. Update this README if adding new test categories
5. Run benchmarks to check for performance regressions

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-benchmark documentation](https://pytest-benchmark.readthedocs.io/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
