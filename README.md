# GenePhenExtract 🧬

**Multi-LLM powered extraction of gene, variant, and phenotype data from PubMed literature**

GenePhenExtract automates the retrieval and interpretation of biomedical text to identify:

- **Genes and variants** (e.g., *KCNH2 p.Tyr54Asn*)
- **Carrier genotypes** (heterozygous, homozygous, compound het)
- **Phenotypic data** relevant to those variants (e.g., QT prolongation, arrhythmia, syncope)
- **Optional attributes** such as age, sex, treatment, and outcomes

**Start for FREE with Google Gemini, then upgrade to paid models if needed!**

## 💰 LLM Cost Comparison

| Provider | Model | Cost (per 1M input tokens) | Free Tier | Best For |
|----------|-------|---------------------------|-----------|----------|
| **Groq** | llama-3.3-70b-versatile | $0.59 | ✅ **30 RPM free** | **FASTEST** - Ultra-fast inference |
| **Google Gemini** | gemini-1.5-flash | $0.075 | ✅ **15 RPM free** | Long context, balanced speed |
| **Google Gemini** | gemini-1.5-pro | $1.25 | ✅ **2 RPM free** | Free tier with good accuracy |
| OpenAI | gpt-4o-mini | $0.15 | ❌ Pay-per-use | Cost-effective for production |
| OpenAI | gpt-4o | $2.50 | ❌ Pay-per-use | Better accuracy, moderate cost |
| Anthropic | claude-3-5-haiku | $1.00 | ❌ Pay-per-use | Fast, balanced |
| Anthropic | claude-3-5-sonnet | $3.00 | ❌ Pay-per-use | **Best accuracy** after benchmarking |

**💡 Recommendation:**
- **Try Groq FIRST** - Fastest free option (30 req/min), great for rapid testing
- **Use Gemini** for long papers (huge context windows)
- **Benchmark both** free options before paying for anything

## Key Features

- ✅ **FREE tier available** - Use Google Gemini at no cost for testing
- ✅ **PubMed integration** - Direct API access to XML-formatted publications
- ✅ **Full-text retrieval** - Automatically fetches PMC full-text + supplementary files
- ✅ **Cost optimization** - Two-stage filtering saves 75%+ on API costs
- ✅ **Multiple LLM providers** - Switch between Gemini, OpenAI, Claude
- ✅ **Individual-level extraction** - Get detailed patient data (age, sex, phenotypes)
- ✅ **Cohort-level extraction** - Extract aggregate statistics from large studies

Perfect for:

- **Penetrance studies** - Extract individual family members (affected AND unaffected carriers)
- **Variant curation** - Build databases of genotype-phenotype associations
- **Pedigree extraction** - Capture clinical characteristics for each individual
- **Large-scale literature mining** - Process hundreds of papers with cost optimization

## Getting Started

### Installation

```bash
# Basic installation (required)
pip install -e .

# Install with FREE Groq (FASTEST, recommended to start)
pip install -e ".[groq]"

# Or install with FREE Google Gemini (best for long papers)
pip install -e ".[google]"

# Optional: Install other LLM providers for benchmarking
pip install -e ".[openai]"     # For OpenAI/GPT (paid)
pip install -e ".[anthropic]"  # For Claude (paid)

# Install all providers at once
pip install -e ".[all-llms]"

# Install with testing dependencies
pip install -e ".[test]"
```

### Get Your FREE API Key

**Option 1: Groq (FREE tier - FASTEST)**
1. Go to [Groq Console](https://console.groq.com/)
2. Sign up and get your API key
3. Export it: `export GROQ_API_KEY='your-key-here'`
4. Free tier: 30 requests/minute (most generous free tier!)

**Option 2: Google Gemini (FREE tier - best for long papers)**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Get API Key" and create a new key
3. Export it: `export GOOGLE_API_KEY='your-key-here'`
4. Free tier: 15 requests/minute for gemini-1.5-flash, 2 requests/minute for gemini-1.5-pro

**Option 3: OpenAI (Paid)**
- Get key from [OpenAI Platform](https://platform.openai.com/api-keys)
- Export: `export OPENAI_API_KEY='your-key-here'`

**Option 4: Anthropic Claude (Paid)**
- Get key from [Anthropic Console](https://console.anthropic.com/)
- Export: `export ANTHROPIC_API_KEY='your-key-here'`

### Quick Start: FREE Tier Examples

**🚀 Option A: Use Groq (FASTEST free option - 30 req/min):**

```python
import os
from genephenextract import PubMedClient, GroqExtractor

# Initialize FREE Groq extractor (ultra-fast!)
api_key = os.getenv("GROQ_API_KEY")
extractor = GroqExtractor(api_key=api_key, model="llama-3.3-70b-versatile")

# Search PubMed
client = PubMedClient()
pmids = client.search("KCNH2 AND long QT syndrome", retmax=10)

print(f"Found {len(pmids)} papers")

# Extract from each paper (very fast with Groq!)
for pmid in pmids[:3]:
    text, source = client.fetch_text(pmid, prefer_full_text=True)
    result = extractor.extract(text, pmid=pmid)

    if result.variant and result.phenotypes:
        print(f"\n✓ PMID {pmid}:")
        print(f"  Variant: {result.variant}")
        print(f"  Phenotypes: {[p.phenotype for p in result.phenotypes[:3]]}")
```

**📚 Option B: Use Google Gemini (best for long papers with huge context):**

GenePhenExtract supports **two extraction methods** depending on how papers report data:

1. **Cohort-level**: For papers reporting aggregate counts ("50 patients, 35 had long QT")
2. **Individual-level**: For papers with detailed patient information ("Proband: male, age 23, het, long QT")

The `UnifiedExtractor` **automatically** determines which method to use:

```python
import os
from genephenextract import UnifiedExtractor, GeminiExtractor, extract_gene_data

# Use FREE Google Gemini (15 requests/min free tier)
api_key = os.getenv("GOOGLE_API_KEY")
extractor = UnifiedExtractor(
    llm_extractor=GeminiExtractor(api_key=api_key, model="gemini-1.5-flash")
)

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
import os
from genephenextract import GeneCentricPipeline, GeminiExtractor

# Define your genes of interest
genes = ["KCNH2", "SCN5A", "KCNQ1"]

# Create pipeline that filters for heterozygous carriers only
# Using FREE Gemini tier
api_key = os.getenv("GOOGLE_API_KEY")
with GeneCentricPipeline(
    extractor=GeminiExtractor(api_key=api_key, model="gemini-1.5-flash"),
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

### Simple PubMed Search Example

**Basic example: Search PubMed and extract from individual papers**

```python
import os
from genephenextract import PubMedClient, GeminiExtractor

# Initialize FREE Gemini extractor
api_key = os.getenv("GOOGLE_API_KEY")
extractor = GeminiExtractor(api_key=api_key, model="gemini-1.5-flash")

# Search PubMed for papers
client = PubMedClient()
pmids = client.search("KCNH2 AND long QT syndrome", retmax=10)

print(f"Found {len(pmids)} papers")

# Extract data from each paper
for pmid in pmids[:3]:  # Just first 3 for demo
    # Get full text (or abstract if full text unavailable)
    text, source = client.fetch_text(pmid, prefer_full_text=True)

    # Extract structured data
    result = extractor.extract(text, pmid=pmid)

    # Check if paper contains relevant genetic data
    if result.variant and result.phenotypes:
        print(f"\n✓ PMID {pmid} has genetic variant data:")
        print(f"  Variant: {result.variant}")
        print(f"  Genotype: {result.carrier_status}")
        print(f"  Phenotypes: {[p.phenotype for p in result.phenotypes[:3]]}")
        if result.age:
            print(f"  Patient age: {result.age}")
    else:
        print(f"\n✗ PMID {pmid} - no variant data found")
```

## Advanced Usage (After Benchmarking)

Once you've tested with the free tier and want to improve accuracy or scale up, consider these options:

### Cost-Optimized Two-Stage Extraction

Save money by filtering irrelevant articles before expensive extraction:

```python
from genephenextract import (
    ClaudeExtractor,
    GeminiExtractor,
    RelevanceFilter,
    MultiStageExtractor,
)

# Stage 1: FREE Gemini filter (or cheap OpenAI)
filter = RelevanceFilter(provider="google", model="gemini-1.5-flash")

# Stage 2: Expensive extraction ONLY if relevant
# Use Claude after you've benchmarked and confirmed it's worth the cost
extractor = MultiStageExtractor(
    filter=filter,
    extractor=ClaudeExtractor(),  # Only used on filtered papers
    min_confidence=0.7,  # Only extract if 70%+ confident
)

# This can save 75%+ on API costs!
```

### Switching to Paid Models

After benchmarking with free tier, you might want better accuracy:

```python
from genephenextract import ClaudeExtractor, OpenAIExtractor

# Option 1: Claude (best accuracy, highest cost)
extractor = ClaudeExtractor(model="claude-3-5-sonnet-20241022")

# Option 2: OpenAI (good balance of cost and accuracy)
extractor = OpenAIExtractor(model="gpt-4o")

# Option 3: OpenAI mini (cheapest paid option)
extractor = OpenAIExtractor(model="gpt-4o-mini")
```

## Troubleshooting

### Common Issues

**Problem: "API key is required for GeminiExtractor"**
```bash
# Make sure you've exported your API key
export GOOGLE_API_KEY='your-key-here'

# Verify it's set
echo $GOOGLE_API_KEY
```

**Problem: "Rate limit exceeded" or "429 error"**
- Free tier limits: 15 requests/min for gemini-1.5-flash, 2 requests/min for gemini-1.5-pro
- Solution: Add a small delay between requests or upgrade to paid tier
```python
import time
for pmid in pmids:
    result = extractor.extract(text, pmid=pmid)
    time.sleep(4)  # Wait 4 seconds between requests for free tier
```

**Problem: "No text content available for PMID"**
- Some papers don't have abstracts or full text available
- Solution: The code will skip these automatically; check the logs

**Problem: "Failed to parse extraction result"**
- The LLM sometimes returns malformed JSON
- Solution: This is more common with free models; retry or switch to a more reliable model

**Problem: Gemini model not available**
- Override the model selection:
```python
extractor = GeminiExtractor(api_key=api_key, model="gemini-1.5-flash")
```
- Or set environment variable:
```bash
export GENEPHENEXTRACT_GEMINI_MODEL="gemini-1.5-flash"
```

### Tips for Best Results

1. **Start small**: Test with 5-10 papers before scaling up
2. **Use full text when available**: Set `prefer_full_text=True` for more complete data
3. **Check extraction quality**: Manually review a sample of results before processing hundreds of papers
4. **Benchmark models**: Try free Gemini first, then compare against paid models on your specific use case
5. **Monitor costs**: Track API usage in your provider's dashboard

## Advanced Features

### Supplementary Material Extraction

GenePhenExtract automatically downloads and extracts text from supplementary files:
- **Supported formats**: DOCX, TXT, CSV, TSV, XML
- **Automatic integration**: Supplementary text is appended to full-text
- **Use case**: Many papers put patient tables and pedigrees in supplementary files

This happens automatically when using `fetch_full_text()` or `fetch_text()`.

### Configuring Gemini Model Selection

You can override which Gemini model to use:

**Method 1: In code**
```python
extractor = GeminiExtractor(api_key=api_key, model="gemini-1.5-flash")
```

**Method 2: Environment variable**
```bash
export GENEPHENEXTRACT_GEMINI_MODEL="gemini-1.5-flash"
```

The extractor will automatically fall back to the best available model if your first choice isn't available.

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
