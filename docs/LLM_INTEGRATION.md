# LLM Integration Guide

GenePhenExtract now supports multiple LLM providers with cost optimization strategies!

## Supported LLM Providers

1. **Anthropic Claude** - Excellent at structured extraction
2. **OpenAI GPT** - Fast and cost-effective
3. **Google Gemini** - Good for long contexts
4. **Mock** - For testing without API calls

## Quick Start

### Installation

```bash
# Install with specific LLM provider
pip install -e ".[anthropic]"  # For Claude
pip install -e ".[openai]"     # For OpenAI
pip install -e ".[google]"     # For Gemini

# Install all providers
pip install -e ".[all-llms]"
```

### Set API Keys

```bash
export ANTHROPIC_API_KEY="your-key-here"
export OPENAI_API_KEY="your-key-here"
export GOOGLE_API_KEY="your-key-here"
```

## Usage Examples

### Basic Usage with Different Providers

#### Using Claude (Recommended for Accuracy)

```python
from genephenextract import ClaudeExtractor, ExtractionPipeline, PubMedClient, PipelineInput

extractor = ClaudeExtractor(model="claude-3-5-sonnet-20241022")
client = PubMedClient()

with ExtractionPipeline(pubmed_client=client, extractor=extractor) as pipeline:
    results = pipeline.run(PipelineInput(query="KCNH2 AND long QT", max_results=5))

for result in results:
    print(f"PMID: {result.pmid}")
    print(f"Variant: {result.variant}")
    print(f"Phenotypes: {[p.phenotype for p in result.phenotypes]}")
```

####  Using OpenAI (Fast and Cheap)

```python
from genephenextract import OpenAIExtractor

# Use gpt-4o-mini for cost savings
extractor = OpenAIExtractor(model="gpt-4o-mini")

# Use GPT-4 for better accuracy
# extractor = OpenAIExtractor(model="gpt-4o")
```

#### Using Gemini

```python
from genephenextract import GeminiExtractor

extractor = GeminiExtractor(model="gemini-1.5-pro-latest")
# Or use flash for speed: model="gemini-1.5-flash"
```

### Cost Optimization with Two-Stage Extraction

**Problem**: Running expensive LLMs on every article wastes money on irrelevant papers.

**Solution**: Use a cheap model to filter first, then expensive model only on relevant articles.

```python
from genephenextract import (
    ClaudeExtractor,
    RelevanceFilter,
    MultiStageExtractor,
    ExtractionPipeline,
    PubMedClient,
    PipelineInput,
)

# Stage 1: Cheap filter (gpt-4o-mini costs ~$0.15 per 1M input tokens)
relevance_filter = RelevanceFilter(
    provider="openai",
    model="gpt-4o-mini",  # Cheapest option
)

# Stage 2: Expensive extractor (Claude Sonnet costs ~$3 per 1M input tokens)
expensive_extractor = ClaudeExtractor(model="claude-3-5-sonnet-20241022")

# Combine them
multi_stage = MultiStageExtractor(
    filter=relevance_filter,
    extractor=expensive_extractor,
    min_confidence=0.7,  # Only extract if >= 70% confident it's relevant
)

# Use in pipeline
client = PubMedClient()
with ExtractionPipeline(pubmed_client=client, extractor=multi_stage) as pipeline:
    results = pipeline.run(PipelineInput(query="genetics", max_results=100))

# Check savings
stats = multi_stage.get_stats()
print(f"Extracted: {stats['extracted']}")
print(f"Filtered out: {stats['skipped']}")
savings = 100 * stats['skipped'] / (stats['extracted'] + stats['skipped'])
print(f"Cost savings: {savings:.1f}%")
```

### Command-Line Usage

#### Basic extraction with Claude

```bash
python -m genephenextract.cli_enhanced \
  --query "KCNH2 AND long QT syndrome" \
  --extractor claude \
  --api-key $ANTHROPIC_API_KEY \
  --max-results 10 \
  --output results.json
```

#### Cost-optimized extraction

```bash
python -m genephenextract.cli_enhanced \
  --query "genetics" \
  --extractor claude \
  --api-key $ANTHROPIC_API_KEY \
  --filter \
  --filter-provider openai \
  --filter-api-key $OPENAI_API_KEY \
  --filter-confidence 0.8 \
  --max-results 100 \
  --show-filter-stats \
  --output results.json
```

This will:
1. Search for 100 articles
2. Use cheap OpenAI filter on each article
3. Only run expensive Claude extraction if filter confidence ≥ 0.8
4. Show statistics on cost savings

#### Using different models

```bash
# Use Claude Haiku (cheapest Claude model)
python -m genephenextract.cli_enhanced \
  --extractor claude \
  --model claude-3-haiku-20240307 \
  --query "KCNH2"

# Use GPT-4
python -m genephenextract.cli_enhanced \
  --extractor openai \
  --model gpt-4o \
  --query "KCNH2"

# Use Gemini Flash (fast)
python -m genephenextract.cli_enhanced \
  --extractor gemini \
  --model gemini-1.5-flash \
  --query "KCNH2"
```

## Working with PDFs

The PDFUtility is now integrated into the package:

```python
from genephenextract import extract_text_from_pdf, download_pdf
from pathlib import Path

# Extract text from local PDF
text = extract_text_from_pdf(Path("paper.pdf"))

# Download and extract from URL
pdf_path = download_pdf("https://example.com/paper.pdf", "local_copy.pdf")
text = extract_text_from_pdf(pdf_path)

# Use extracted text with any extractor
from genephenextract import ClaudeExtractor

extractor = ClaudeExtractor()
result = extractor.extract(text, pmid="custom")
```

## Cost Comparison

Based on current pricing (as of 2024):

| Provider | Model | Input (per 1M tokens) | Output (per 1M tokens) | Use Case |
|----------|-------|----------------------|------------------------|----------|
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | **Filtering** |
| OpenAI | gpt-4o | $2.50 | $10.00 | Extraction |
| Anthropic | Claude 3 Haiku | $0.25 | $1.25 | Filtering |
| Anthropic | Claude 3.5 Sonnet | $3.00 | $15.00 | **Best extraction** |
| Google | Gemini 1.5 Flash | $0.075 | $0.30 | **Cheapest** |
| Google | Gemini 1.5 Pro | $1.25 | $5.00 | Long context |

### Example Cost Calculation

Processing 1000 abstracts (~500 tokens each = 500K tokens total):

**Without filtering:**
- Claude Sonnet: 500K tokens × $3/1M = **$1.50**

**With filtering (80% filtered out):**
- gpt-4o-mini filter: 500K × $0.15/1M = $0.075
- Claude Sonnet (20%): 100K × $3/1M = $0.30
- **Total: $0.375** (75% savings!)

## Best Practices

### 1. Choose the Right Model

- **For accuracy**: Claude 3.5 Sonnet
- **For cost**: GPT-4o-mini or Gemini Flash
- **For long texts**: Gemini 1.5 Pro (2M token context)
- **For filtering**: Always use cheapest (gpt-4o-mini or Gemini Flash)

### 2. Use Filtering for Large Batches

```python
# Bad: No filtering on 1000 articles
extractor = ClaudeExtractor()  # Expensive on all articles

# Good: Filter first
filter = RelevanceFilter(provider="openai")
extractor = MultiStageExtractor(filter=filter, extractor=ClaudeExtractor())
```

### 3. Adjust Confidence Threshold

```python
# Strict: Fewer false positives, higher cost savings
MultiStageExtractor(min_confidence=0.9)

# Lenient: Fewer false negatives, lower savings
MultiStageExtractor(min_confidence=0.6)

# Balanced: Good middle ground
MultiStageExtractor(min_confidence=0.7)  # Default
```

### 4. Use Full-Text When Available

Full-text articles contain more information than abstracts:

```python
# Prefer full-text from PMC
client = PubMedClient()
text, source = client.fetch_text(pmid, prefer_full_text=True)

print(f"Using {source}")  # 'full_text' or 'abstract'
```

### 5. Batch Processing with Progress Tracking

```python
from genephenextract import ExtractionPipeline, PubMedClient, ClaudeExtractor, PipelineInput

pmids = ["12345", "67890", ...]  # Your list

extractor = ClaudeExtractor()
client = PubMedClient()

results = []
for i, pmid in enumerate(pmids, 1):
    print(f"Processing {i}/{len(pmids)}: {pmid}")

    with ExtractionPipeline(pubmed_client=client, extractor=extractor) as pipeline:
        result = pipeline.run(PipelineInput(pmids=[pmid]))[0]
        results.append(result)

    # Save incrementally
    if i % 10 == 0:
        with open("results_partial.json", "w") as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
```

## Advanced Usage

### Custom Extraction Schema

```python
from pathlib import Path

custom_schema = {
    "variant": "string",
    "phenotypes": [{"name": "string", "severity": "string"}],
    "family_history": "boolean",
}

Path("custom_schema.json").write_text(json.dumps(custom_schema))

result = extractor.extract(
    text,
    pmid="12345",
    schema_path=Path("custom_schema.json")
)
```

### Mixing Providers

```python
# Use different providers for filter and extraction
openai_filter = RelevanceFilter(
    api_key=os.getenv("OPENAI_API_KEY"),
    provider="openai",
)

claude_extractor = ClaudeExtractor(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)

multi_stage = MultiStageExtractor(
    filter=openai_filter,
    extractor=claude_extractor,
)
```

### Error Handling

```python
from genephenextract.extraction import ExtractorError

try:
    result = extractor.extract(text, pmid="12345")
except ExtractorError as e:
    print(f"Extraction failed: {e}")
    # Fall back to mock or skip
```

## Environment Variables

All extractors check environment variables for API keys:

```bash
# Set keys
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="..."

# Now you don't need to pass api_key parameter
extractor = ClaudeExtractor()  # Uses ANTHROPIC_API_KEY automatically
```

## Troubleshooting

### "ImportError: anthropic package not installed"

```bash
pip install anthropic
# or
pip install -e ".[anthropic]"
```

### "API key required"

Set the appropriate environment variable or pass `api_key` parameter.

### High costs

Use filtering! See cost optimization section above.

### Rate limiting

Add delays between requests:

```python
import time

for pmid in pmids:
    result = extractor.extract(text, pmid=pmid)
    time.sleep(1)  # Wait 1 second between requests
```

## Future Enhancements

- [ ] Streaming responses for real-time processing
- [ ] Caching extracted results to avoid re-processing
- [ ] Batch API support for providers that offer it
- [ ] Local model support (Ollama, etc.)
- [ ] Ensemble extraction (combine multiple models)

## Contributing

To add support for a new LLM provider:

1. Create a new extractor class inheriting from `BaseExtractor`
2. Implement the `extract()` method
3. Add optional dependency to `pyproject.toml`
4. Update this documentation

See `ClaudeExtractor`, `OpenAIExtractor`, or `GeminiExtractor` as examples.
