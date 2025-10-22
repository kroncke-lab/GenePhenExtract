# GenePhenExtract 🧬

**Multi-LLM powered extraction of gene, variant, and phenotype data from PubMed literature**

GenePhenExtract automates the retrieval and interpretation of biomedical text to identify:

- **Genes and variants** (e.g., *KCNH2 p.Tyr54Asn*)
- **Carrier genotypes** (heterozygous, homozygous, compound het)
- **Phenotypic data** relevant to those variants (e.g., QT prolongation, arrhythmia, syncope)
- **Optional attributes** such as age, sex, treatment, and outcomes

It supports multiple LLM providers with cost optimization strategies:

- ✅ **Anthropic Claude** - Best accuracy for medical text
- ✅ **OpenAI GPT** - Fast and cost-effective
- ✅ **Google Gemini** - Long context support
- ✅ **Two-stage extraction** - Filter with cheap model, extract with expensive model
- ✅ **PDF support** - Extract from supplementary PDFs
- ✅ **Full-text retrieval** - Use PMC full-text when available

Perfect for:

- Variant curation and penetrance modeling
- Genotype–phenotype association studies
- Automated database population from case reports
- Large-scale literature mining with cost optimization

## Getting Started

### Installation

```bash
# Basic installation
pip install -e .

# Install with specific LLM provider
pip install -e ".[anthropic]"  # For Claude
pip install -e ".[openai]"     # For OpenAI/GPT
pip install -e ".[google]"     # For Gemini

# Install with all LLM providers
pip install -e ".[all-llms]"

# Install with testing dependencies
pip install -e ".[test]"
```

### Quick Start

```python
from genephenextract import ClaudeExtractor, ExtractionPipeline, PubMedClient, PipelineInput

# Set up extractor (or use OpenAIExtractor, GeminiExtractor)
extractor = ClaudeExtractor()  # Requires ANTHROPIC_API_KEY env var

# Run extraction
with ExtractionPipeline(pubmed_client=PubMedClient(), extractor=extractor) as pipeline:
    results = pipeline.run(PipelineInput(query="KCNH2 AND long QT", max_results=5))

for result in results:
    print(f"PMID: {result.pmid}, Variant: {result.variant}")
```

### Cost-Optimized Extraction

Save money by filtering irrelevant articles before expensive extraction:

```python
from genephenextract import (
    ClaudeExtractor,
    RelevanceFilter,
    MultiStageExtractor,
)

# Stage 1: Cheap filter
filter = RelevanceFilter(provider="openai", model="gpt-4o-mini")

# Stage 2: Expensive extraction (only if relevant)
extractor = MultiStageExtractor(
    filter=filter,
    extractor=ClaudeExtractor(),
    min_confidence=0.7,  # Only extract if 70%+ confident
)

# This can save 75%+ on API costs!
```

See [docs/LLM_INTEGRATION.md](docs/LLM_INTEGRATION.md) for complete documentation.

#### Configuring Gemini model selection

When using the direct Gemini integration you may need to target a model version that is available to your
Google AI Studio project. GenePhenExtract defaults to `gemini-1.5-pro-latest`, but will automatically fall back to
the best model your API key can access if that default is unavailable. You can override the model in two ways:

1. Pass the `model` argument when instantiating `GeminiExtractor` in Python code.
2. Set the `GENEPHENEXTRACT_GEMINI_MODEL` environment variable when using the CLI or test script.

If a specific model is unavailable (for example when forcing a value via the environment variable), the extractor
raises a clear error that includes the models your API key is authorised to use. You can also visit Google AI Studio
to manage model access.

#### Supplementary material ingestion

Many case reports place key cohort details (e.g., index patients, QTc measurements, or pedigree tables) in
supplementary files instead of the article body. When a PMC article links DOCX, TXT, CSV, TSV, or XML
supplementary assets, GenePhenExtract now downloads those files and appends their text to the full-text payload
handed to the extractor. This makes it easier for downstream LLMs to surface details that only appear in
supplementary appendices. Files in unsupported formats (such as PDF) are skipped gracefully, so you can still
download them manually if needed.

### Command-line usage

```bash
genephenextract --query "KCNH2 AND long QT" --max-results 5 --mock
```

The `--mock` flag runs the built-in mock extractor, which produces deterministic output without calling an external LLM. To use LangExtract instead, omit `--mock` and provide a valid API key:

```bash
genephenextract --query "KCNH2" --api-key $LANGEXTRACT_API_KEY --schema examples/schema.json
```

The CLI defaults to the `gemini-pro` model identifier. If your account requires a
different model, set the `GENEPHENEXTRACT_GEMINI_MODEL` environment variable or
pass `--model your-model-name` on the command line. Bare Gemini names are
automatically expanded to the fully qualified `models/...` identifiers expected
by the public API, so both `gemini-pro` and `models/gemini-pro` are accepted.

You can also process specific PMIDs:

```bash
genephenextract --pmids 12345678 98765432 --mock --output results.json
```

To disable HPO post-processing or provide a custom ontology mapping file:

```bash
genephenextract --query "KCNH2" --mock --no-hpo
# or
genephenextract --query "KCNH2" --mock --hpo-map /path/to/custom_hpo.json
```

### Python API

```python
from genephenextract import ExtractionPipeline, PipelineInput, MockExtractor, PubMedClient

payload = PipelineInput(query="KCNH2", max_results=2)

with ExtractionPipeline(pubmed_client=PubMedClient(), extractor=MockExtractor()) as pipeline:
    results = pipeline.run(payload)

for record in results:
    print(record.to_dict())
```

### Project structure

- `genephenextract.pubmed`: lightweight client for PubMed E-utilities
- `genephenextract.extraction`: interfaces for LangExtract integration and local mock extractor
- `genephenextract.hpo`: utilities for mapping phenotypes to HPO identifiers
- `genephenextract.pipeline`: orchestration logic that ties retrieval and extraction together
- `examples/`: placeholder for sample schemas and configuration files
- `tests/`: pytest-based unit tests covering data models and pipeline behavior

### Testing

Run the automated test suite with:

```bash
pytest
```

### Roadmap

- [x] PubMed retrieval
- [x] LLM-based structured extraction
- [x] Phenotype ontology mapping (HPO integration)
- [ ] Batch processing and caching
- [ ] Streamlit demo app

## License

MIT License — free to use and adapt.

Developed by Brett Kroncke (Vanderbilt University Medical Center)
