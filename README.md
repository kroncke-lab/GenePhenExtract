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

- **Penetrance studies** - Extract individual family members (affected AND unaffected carriers)
- **Variant curation** - Build databases of genotype-phenotype associations
- **Pedigree extraction** - Capture clinical characteristics for each individual
- **Large-scale literature mining** - Process hundreds of papers with cost optimization

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

### Quick Start: Unified Extraction (THE CORE USE CASE)

**🔥 Extract genotype-phenotype data with automatic method selection:**

GenePhenExtract supports **two extraction methods** depending on how papers report data:

1. **Cohort-level**: For papers reporting aggregate counts ("50 patients, 35 had long QT")
2. **Individual-level**: For papers with detailed patient information ("Proband: male, age 23, het, long QT")

The `UnifiedExtractor` **automatically** determines which method to use:

```python
from genephenextract import UnifiedExtractor, ClaudeExtractor, extract_gene_data

# Create unified extractor (handles both cohort and individual data)
extractor = UnifiedExtractor(llm_extractor=ClaudeExtractor())

# Extract all data for a gene from PubMed
# Returns BOTH cohort and individual databases
cohort_db, individual_db = extract_gene_data(
    gene="KCNH2",
    extractor=extractor,
    max_papers=50,
    date_range=(2020, 2024)
)

# Analyze cohort data (aggregate counts from large studies)
print("COHORT DATA:")
summary = cohort_db.get_summary(genotype="heterozygous")
print(f"Total cohorts: {summary['total_cohorts']}")
print(f"Total carriers: {summary['total_carriers']}")

for phenotype, stats in summary['phenotype_statistics'].items():
    print(f"  {phenotype}: {stats['affected_count']}/{stats['total_carriers']} ({stats['frequency']:.1%})")

# Analyze individual data (detailed patient characteristics)
print("\nINDIVIDUAL DATA:")
print(f"Family studies: {len(individual_db.studies)}")
print(f"Total individuals: {len(individual_db.get_all_individuals())}")
print(f"Affected carriers: {len(individual_db.get_affected_carriers())}")
print(f"Unaffected carriers: {len(individual_db.get_unaffected_carriers())}")

# Can analyze by age, sex, age at onset, etc.
for ind in individual_db.get_all_carriers()[:5]:
    print(f"  {ind.individual_id}: {ind.genotype}, age {ind.age}, affected={ind.affected}")
```

**Key features:**
- ✅ **Cohort extraction**: Aggregate counts (affected vs unaffected)
- ✅ **Individual extraction**: Detailed patient data (age, sex, age at onset)
- ✅ **Automatic method selection**: Based on how paper reports data
- ✅ **Combined analysis**: Use both approaches together
- ✅ **Genotype filtering**: heterozygous, homozygous, compound heterozygous

See [docs/EXTRACTION_METHODS.md](docs/EXTRACTION_METHODS.md) for detailed guide on when to use each method.

See [examples/unified_extraction_example.py](examples/unified_extraction_example.py) for comprehensive examples.

### Alternative: Gene-Centric Workflow

**Extract phenotypes for HETEROZYGOUS carriers in specific genes:**

```python
from genephenextract import GeneCentricPipeline, ClaudeExtractor

# Define your genes of interest
genes = ["KCNH2", "SCN5A", "KCNQ1"]

# Create pipeline that filters for heterozygous carriers only
with GeneCentricPipeline(
    extractor=ClaudeExtractor(),
    filter_genotypes=["heterozygous"]  # Extract only het carriers!
) as pipeline:
    # Extract all variants and phenotypes for these genes
    database = pipeline.extract_for_genes(
        genes=genes,
        max_papers_per_gene=100,
        date_range=(2010, 2024)
    )

# Analyze results
for gene in genes:
    variants = database.filter_by_gene(gene)
    print(f"\n{gene}: {len(variants)} heterozygous variants")

    for variant in variants[:5]:
        print(f"  {variant.variant}:")
        for pheno in variant.top_phenotypes(n=3):
            print(f"    - {pheno.name} ({pheno.penetrance:.1%} penetrance)")

# Export for analysis
database.export_to_csv("heterozygous_variants.csv")
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
