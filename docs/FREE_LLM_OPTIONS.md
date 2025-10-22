# Free LLM Options for Testing GenePhenExtract

Complete guide to using **free LLM APIs** for development and testing without spending money.

## Quick Comparison

| Provider | Free Tier | Speed | Quality | Best For |
|----------|-----------|-------|---------|----------|
| **Google Gemini** ⭐⭐⭐ | 1,500 req/day | Medium | Good | **Best overall free option** |
| **Groq** ⭐⭐⭐ | 14,400 req/day | **Very Fast** | Good | Speed + high volume |
| **Ollama** ⭐⭐ | Unlimited | Medium | Medium | Offline, complete privacy |
| **OpenAI Free Tier** | $5 credit (expires) | Medium | Excellent | Short-term testing |

---

## Option 1: Google Gemini (RECOMMENDED) ⭐⭐⭐

**Already supported in GenePhenExtract!**

### Free Tier Limits:
- **15 requests per minute**
- **1,500 requests per day**
- **1 million tokens per day**
- **No credit card required!**
- **No expiration**

### Setup:

```bash
# 1. Get API key (FREE, no credit card):
# Visit: https://makersuite.google.com/app/apikey
# Click "Create API key"

# 2. Set environment variable
export GOOGLE_API_KEY="your-api-key-here"

# 3. Use in GenePhenExtract
python
```

```python
from genephenextract import GeminiExtractor, UnifiedExtractor

# Use fastest free model
extractor = UnifiedExtractor(llm_extractor=GeminiExtractor(
    model="gemini-1.5-flash"  # Fast and free!
))

# Or for better quality (still free)
extractor = UnifiedExtractor(llm_extractor=GeminiExtractor(
    model="gemini-1.5-pro"
))
```

### Free Models:

| Model | Speed | Quality | Context |
|-------|-------|---------|---------|
| `gemini-1.5-flash` | **Fast** | Good | 1M tokens |
| `gemini-1.5-pro` | Medium | **Better** | 2M tokens |
| `gemini-1.0-pro` | Medium | Good | 32k tokens |

### Test with Nextflow:

```bash
export GOOGLE_API_KEY="your-key"

nextflow run main.nf \
  --llm_provider gemini \
  --llm_model gemini-1.5-flash \
  --genes genes.txt \
  --max_papers_per_gene 10
```

### Daily Capacity:

With 1,500 requests/day, you can process:
- **~30 genes** with 50 papers each per day
- **~150 genes** with 10 papers each per day

---

## Option 2: Groq (Super Fast + Free) ⭐⭐⭐

**NEW: Now supported in GenePhenExtract!**

### Free Tier Limits:
- **30 requests per minute**
- **14,400 requests per day**
- **10x faster than OpenAI/Claude** (!)
- No credit card required

### Setup:

```bash
# 1. Get API key (FREE):
# Visit: https://console.groq.com/keys
# Sign up (no credit card)
# Create API key

# 2. Set environment variable
export GROQ_API_KEY="your-api-key-here"

# 3. Install groq package
pip install groq
```

### Use in GenePhenExtract:

```python
from genephenextract import GroqExtractor, UnifiedExtractor

# Fastest free option!
extractor = UnifiedExtractor(llm_extractor=GroqExtractor(
    model="llama-3.1-70b-versatile"  # Best free model
))

# Or smaller/faster model
extractor = UnifiedExtractor(llm_extractor=GroqExtractor(
    model="llama-3.1-8b-instant"  # Super fast
))
```

### Free Models on Groq:

| Model | Params | Speed | Quality |
|-------|--------|-------|---------|
| `llama-3.1-70b-versatile` | 70B | **Very Fast** | Excellent |
| `llama-3.1-8b-instant` | 8B | **Ultra Fast** | Good |
| `mixtral-8x7b-32768` | 47B | Very Fast | Excellent |

### Why Groq is Amazing:

- **10x faster** inference than OpenAI (uses custom chips)
- **14,400 requests/day** = enough for 280+ genes with 50 papers each!
- High-quality Llama 3.1 models
- No cost, no expiration

### Test with Nextflow:

```bash
export GROQ_API_KEY="your-key"

nextflow run main.nf \
  --llm_provider groq \
  --llm_model llama-3.1-70b-versatile \
  --genes genes.txt
```

---

## Option 3: Ollama (Completely Free, Local) ⭐⭐

**Run LLMs on your own machine - 100% free, 100% private**

### Setup:

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Download a model
ollama pull llama3.1:8b       # 8B model (~4GB)
ollama pull llama3.1:70b      # 70B model (~40GB, needs good GPU)
ollama pull mistral:7b        # Alternative

# 3. Start Ollama server
ollama serve
```

### Use in GenePhenExtract:

```python
from genephenextract import OllamaExtractor, UnifiedExtractor

# Use local model
extractor = UnifiedExtractor(llm_extractor=OllamaExtractor(
    model="llama3.1:8b"
))
```

### Recommended Models:

| Model | Size | RAM Needed | Quality |
|-------|------|------------|---------|
| `llama3.1:8b` | 4.7GB | 8GB | Good |
| `llama3.1:70b` | 40GB | 48GB+ | Excellent |
| `mistral:7b` | 4.1GB | 8GB | Good |
| `mixtral:8x7b` | 26GB | 32GB | Excellent |

### Benefits:
- ✅ **Completely free** (no API costs)
- ✅ **No rate limits**
- ✅ **Full privacy** (data never leaves your machine)
- ✅ **Works offline**

### Downsides:
- ⚠️ Needs good hardware (GPU recommended)
- ⚠️ Slower than API services
- ⚠️ Quality depends on model size

---

## Option 4: OpenAI Free Tier (Limited Time)

### Free Tier:
- **$5 in free credits** for new accounts
- **Expires after 3 months**
- Credit card required (won't be charged)

### Setup:

```bash
# 1. Sign up: https://platform.openai.com/signup
# 2. Get API key: https://platform.openai.com/api-keys
export OPENAI_API_KEY="your-key"
```

### Use cheapest models:

```python
from genephenextract import OpenAIExtractor, UnifiedExtractor

# Cheapest model
extractor = UnifiedExtractor(llm_extractor=OpenAIExtractor(
    model="gpt-4o-mini"  # $0.15 per 1M tokens input
))
```

### With $5 credit:
- **~3,000-5,000 papers** can be processed before credit runs out
- Good for initial testing/development

---

## Recommended Development Workflow

### Phase 1: Initial Development (Gemini Free)

```bash
# Use Gemini for initial testing (no cost, no expiration)
export GOOGLE_API_KEY="your-key"

# Test with small dataset
nextflow run main.nf \
  -profile test \
  --llm_provider gemini \
  --llm_model gemini-1.5-flash \
  --genes test_genes.txt \
  --max_papers_per_gene 5
```

### Phase 2: Larger Testing (Groq)

```bash
# Switch to Groq for higher volume + speed
export GROQ_API_KEY="your-key"

# Process more genes
nextflow run main.nf \
  --llm_provider groq \
  --llm_model llama-3.1-70b-versatile \
  --genes genes.txt \
  --max_papers_per_gene 50
```

### Phase 3: Production (Paid API if needed)

```bash
# If you need highest quality for final results
export ANTHROPIC_API_KEY="your-key"

nextflow run main.nf \
  --llm_provider claude \
  --genes genes.txt
```

---

## Cost Estimation

### Free Tier Capacity Per Day:

**Gemini (1,500 req/day):**
- 30 genes × 50 papers = 1,500 papers
- Processing time: ~2-3 hours
- **Cost: $0**

**Groq (14,400 req/day):**
- 288 genes × 50 papers = 14,400 papers
- Processing time: ~4-6 hours (very fast!)
- **Cost: $0**

**Ollama (unlimited):**
- Limited only by your hardware
- Slower but free
- **Cost: $0**

### If You Need to Pay (Comparison):

For 5,000 papers:

| Provider | Model | Cost |
|----------|-------|------|
| Gemini | gemini-1.5-flash | ~$5 |
| Groq | llama-3.1-70b | **$0 (free tier)** |
| OpenAI | gpt-4o-mini | ~$7.50 |
| Anthropic | claude-sonnet | ~$25 |

---

## Tips for Maximizing Free Tiers

### 1. Use Rate Limiting

```groovy
// In nextflow.config
process {
    withName: EXTRACT_DATA {
        maxForks = 10  // Don't exceed rate limits
    }
}
```

### 2. Filter Papers First

Use cheaper model to filter, then expensive model to extract:

```python
from genephenextract import RelevanceFilter, MultiStageExtractor, GroqExtractor

# Stage 1: Fast filter with Groq
filter = RelevanceFilter(provider="groq", model="llama-3.1-8b-instant")

# Stage 2: Extract only relevant papers
extractor = MultiStageExtractor(
    filter=filter,
    extractor=GroqExtractor(model="llama-3.1-70b-versatile")
)
```

### 3. Cache Results

```bash
# Nextflow automatically caches - use -resume
nextflow run main.nf -resume --llm_provider groq
```

### 4. Start Small

```bash
# Test with 1 gene first
echo "KCNH2" > test.txt
nextflow run main.nf --genes test.txt --max_papers_per_gene 10
```

---

## Example: Complete Free Workflow

```bash
#!/bin/bash

# 1. Get free API keys (one-time setup)
echo "Get Gemini key: https://makersuite.google.com/app/apikey"
echo "Get Groq key: https://console.groq.com/keys"

# 2. Set environment
export GOOGLE_API_KEY="your-gemini-key"
export GROQ_API_KEY="your-groq-key"

# 3. Test with Gemini (small test)
nextflow run main.nf \
  -profile test \
  --llm_provider gemini \
  --llm_model gemini-1.5-flash \
  --genes test_genes.txt \
  --max_papers_per_gene 5

# 4. Scale up with Groq (faster + higher limits)
nextflow run main.nf \
  --llm_provider groq \
  --llm_model llama-3.1-70b-versatile \
  --genes my_genes.txt \
  --max_papers_per_gene 50 \
  --outdir results_groq

# Total cost: $0
```

---

## Troubleshooting

### "Rate limit exceeded"

**Gemini:**
```bash
# Reduce concurrent requests
# Edit nextflow.config:
process {
    withName: EXTRACT_DATA {
        maxForks = 5  # Lower from 20
    }
}
```

**Groq:**
```bash
# 30 RPM limit, so:
maxForks = 15  # Stay safely under limit
```

### "API key invalid"

```bash
# Check environment variable
echo $GOOGLE_API_KEY
echo $GROQ_API_KEY

# Re-export if needed
export GOOGLE_API_KEY="your-key"
```

### "Model not available"

**Groq models change, check available:**
```bash
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" | jq
```

---

## Summary

**For CV building / development:**

1. **Start with Gemini** (gemini-1.5-flash)
   - Free, no credit card
   - Good for initial testing

2. **Scale with Groq** (llama-3.1-70b-versatile)
   - 10x faster
   - Higher daily limits
   - Still 100% free

3. **Use Ollama** for complete privacy/offline work
   - No cost ever
   - Full control

**You can build and test the entire GenePhenExtract pipeline without spending a cent!**
