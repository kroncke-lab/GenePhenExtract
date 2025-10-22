# GenePhenExtract Nextflow Pipeline

Complete guide for running GenePhenExtract at scale using Nextflow.

## Overview

The Nextflow pipeline parallelizes GenePhenExtract across multiple genes and papers:

```
Input: genes.txt
  ↓
[SEARCH_PUBMED] - Parallel per gene
  ↓
[FETCH_PAPERS] - Parallel per PMID
  ↓
[EXTRACT_DATA] - Parallel per paper (LLM extraction)
  ↓
[AGGREGATE_BY_GENE] - Combine results per gene
  ↓
[CREATE_FINAL_REPORT] - Final combined output
  ↓
Output: CSV files + HTML report
```

**Key Benefits:**
- ✅ Parallel processing across genes and papers
- ✅ Automatic error handling and retries
- ✅ Resume from checkpoint on failure
- ✅ Works locally or on HPC/cloud
- ✅ Resource management and logging
- ✅ Reproducible with containers

## Quick Start

### 1. Install Nextflow

```bash
# Install Nextflow
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/

# Verify installation
nextflow -version
```

### 2. Prepare Input

Create `genes.txt` with one gene per line:

```
KCNH2
SCN5A
KCNQ1
```

### 3. Set API Keys

```bash
# For Claude
export ANTHROPIC_API_KEY="your-key-here"

# For OpenAI
export OPENAI_API_KEY="your-key-here"

# For Gemini
export GOOGLE_API_KEY="your-key-here"
```

### 4. Run Pipeline

**Local execution (basic):**
```bash
nextflow run main.nf \
  --genes genes.txt \
  --llm_provider claude \
  --max_papers_per_gene 50 \
  --outdir results
```

**With Docker (recommended):**
```bash
# Build Docker image
docker build -t genephenextract:latest .

# Run with Docker profile
nextflow run main.nf \
  -profile standard \
  --genes genes.txt \
  --llm_provider claude \
  --outdir results
```

**Test run (small):**
```bash
nextflow run main.nf \
  -profile test \
  --genes genes.txt \
  --outdir results_test
```

## Configuration

### Parameters

Edit `nextflow.config` or pass via command line:

```bash
nextflow run main.nf \
  --genes genes.txt \
  --max_papers_per_gene 100 \          # Papers per gene
  --date_range_start 2015 \             # Start year
  --date_range_end 2024 \               # End year
  --llm_provider claude \               # LLM: claude, openai, gemini
  --llm_model claude-3-5-sonnet-20241022 \
  --enable_cost_filter true \           # Use cheap filter first
  --use_full_text true \                # Fetch PMC full-text
  --download_pdfs false \               # Download PDFs
  --outdir results
```

### Execution Profiles

**Local (default):**
```bash
nextflow run main.nf --genes genes.txt
```

**Local without Docker:**
```bash
nextflow run main.nf -profile local --genes genes.txt
```

**SLURM cluster:**
```bash
nextflow run main.nf -profile slurm --genes genes.txt
```

**AWS Batch:**
```bash
nextflow run main.nf -profile aws \
  --genes genes.txt \
  -bucket-dir s3://your-bucket/work
```

**Google Cloud:**
```bash
nextflow run main.nf -profile gcp \
  --genes genes.txt \
  -work-dir gs://your-bucket/work
```

**Test mode:**
```bash
nextflow run main.nf -profile test --genes genes.txt
```

## Output Structure

```
results/
├── pubmed_searches/           # PubMed search results per gene
│   ├── KCNH2_pmids.txt
│   ├── KCNH2_search_stats.json
│   └── ...
├── papers/                    # Fetched paper texts
│   ├── KCNH2/
│   │   ├── 12345678_text.txt
│   │   ├── 12345678_metadata.json
│   │   └── ...
│   └── ...
├── extractions/               # LLM extractions
│   ├── KCNH2/
│   │   ├── 12345678_extraction.json
│   │   ├── 12345678_extraction_log.json
│   │   └── ...
│   └── ...
├── aggregated/                # Aggregated data per gene
│   ├── KCNH2_cohort_data.json
│   ├── KCNH2_individual_data.json
│   ├── KCNH2_summary.json
│   └── ...
├── final/                     # Final combined output
│   ├── combined_cohort_data.csv       ← Main cohort output
│   ├── combined_individual_data.csv   ← Main individual output
│   ├── pipeline_report.html           ← Summary report
│   └── summary_statistics.json
└── reports/                   # Nextflow execution reports
    ├── execution_report.html
    ├── timeline.html
    ├── trace.txt
    └── dag.svg
```

## Key Output Files

### 1. combined_cohort_data.csv

Cohort-level data (aggregate counts):

| gene  | pmid     | variant      | genotype      | total_carriers | phenotype    | affected_count | unaffected_count |
|-------|----------|--------------|---------------|----------------|--------------|----------------|------------------|
| KCNH2 | 12345678 | p.Tyr54Asn   | heterozygous  | 50             | long QT      | 35             | 15               |

### 2. combined_individual_data.csv

Individual-level data (detailed patient info):

| gene  | pmid     | variant    | individual_id | genotype      | affected | phenotypes | age | sex    | age_at_onset |
|-------|----------|------------|---------------|---------------|----------|------------|-----|--------|--------------|
| KCNH2 | 87654321 | p.Tyr54Asn | proband       | heterozygous  | true     | long QT    | 23  | male   | 18           |
| KCNH2 | 87654321 | p.Tyr54Asn | mother        | heterozygous  | false    |            | 45  | female | null         |

### 3. pipeline_report.html

Interactive HTML report with:
- Summary statistics
- Per-gene results
- Success/error rates
- Links to output files

## Advanced Usage

### Resume Failed Pipeline

If pipeline fails, resume from last checkpoint:

```bash
nextflow run main.nf -resume --genes genes.txt
```

### Process Subset of Genes

```bash
# Create subset
echo "KCNH2" > kcnh2_only.txt

nextflow run main.nf --genes kcnh2_only.txt
```

### Cost Optimization

Use two-stage extraction (cheap filter + expensive extraction):

```bash
nextflow run main.nf \
  --enable_cost_filter true \
  --llm_provider claude \
  --genes genes.txt
```

This filters irrelevant papers with a cheap model before expensive extraction.

### Custom Resource Allocation

Edit `nextflow.config`:

```groovy
process {
    withName: EXTRACT_DATA {
        cpus = 2
        memory = '8 GB'
        maxForks = 50  // Increase parallel LLM calls
    }
}
```

### Run on HPC Cluster

For SLURM:

```bash
nextflow run main.nf \
  -profile slurm \
  --genes genes.txt \
  -w /scratch/$USER/work
```

Edit cluster queue in `nextflow.config`:

```groovy
profiles {
    slurm {
        process.queue = 'your-queue-name'
        process.clusterOptions = '--account=your-account'
    }
}
```

## Monitoring

### View Logs

```bash
# Tail Nextflow log
tail -f .nextflow.log

# View specific process logs
ls -la work/  # Find process work directory
cat work/a1/b2c3d4.../  # View stdout/stderr
```

### Execution Reports

After completion, view:

```bash
# Execution timeline
open results/reports/timeline.html

# Resource usage
open results/reports/execution_report.html

# Process DAG
open results/reports/dag.svg
```

### Monitor Progress

```bash
# Watch output directory
watch -n 5 'find results/extractions -name "*_extraction.json" | wc -l'
```

## Troubleshooting

### Issue: "Command error" in EXTRACT_DATA

**Cause:** LLM API key not set or rate limit exceeded

**Solution:**
```bash
# Set API key
export ANTHROPIC_API_KEY="your-key"

# Reduce parallel calls
# Edit nextflow.config:
process {
    withName: EXTRACT_DATA {
        maxForks = 5  # Lower concurrency
    }
}
```

### Issue: "Out of memory"

**Cause:** Process needs more RAM

**Solution:**
```bash
# Edit nextflow.config
process {
    withName: EXTRACT_DATA {
        memory = '8 GB'  # Increase from 4 GB
    }
}
```

### Issue: PubMed rate limiting

**Cause:** Too many concurrent PubMed requests

**Solution:**
```bash
# Edit nextflow.config
process {
    withName: FETCH_PAPERS {
        maxForks = 5  # Reduce from 10
    }
}

# Or get PubMed API key
# Set in environment:
export NCBI_API_KEY="your-key"
```

### Issue: Pipeline stalls

**Cause:** One process waiting for resources

**Solution:**
```bash
# Check what's running
nextflow log

# Kill and resume
nextflow log -f trace
# Find stuck process, kill it
nextflow run main.nf -resume
```

## Best Practices

### 1. Start Small

Test with a few genes first:

```bash
# Create test file
echo "KCNH2" > test_genes.txt

# Run test
nextflow run main.nf \
  -profile test \
  --genes test_genes.txt \
  --max_papers_per_gene 5
```

### 2. Use Containers

Always use Docker/Singularity for reproducibility:

```bash
# Build container
docker build -t genephenextract:latest .

# Run with container
nextflow run main.nf -profile standard
```

### 3. Monitor Costs

Track LLM API usage:

```bash
# After run, check logs
grep "Successfully extracted" results/extractions/*/*.json | wc -l
```

### 4. Version Control

Commit Nextflow files to git:

```bash
git add main.nf nextflow.config
git commit -m "Add Nextflow pipeline"
```

### 5. Save Intermediate Results

Set publish mode to 'copy' to keep all intermediate files:

```groovy
params.publish_mode = 'copy'  // vs 'symlink'
```

## Example Workflows

### Scenario 1: Extract 10 Genes Locally

```bash
# Create gene list
cat > my_genes.txt <<EOF
KCNH2
SCN5A
KCNQ1
CACNA1C
RYR2
PKP2
DSP
DSG2
DSC2
JUP
EOF

# Run locally with Claude
nextflow run main.nf \
  --genes my_genes.txt \
  --llm_provider claude \
  --max_papers_per_gene 50 \
  --date_range_start 2015 \
  --date_range_end 2024 \
  --outdir results_10_genes
```

**Expected time:** ~2-4 hours (depends on API speed)
**Expected cost:** ~$10-20 (Claude API)

### Scenario 2: Large-Scale HPC Processing

```bash
# 100 genes, 100 papers each = 10,000 papers
nextflow run main.nf \
  -profile slurm \
  --genes large_gene_list.txt \
  --max_papers_per_gene 100 \
  --enable_cost_filter true \
  -w /scratch/$USER/genephen_work \
  --outdir /data/$USER/genephen_results
```

**Expected time:** ~12-24 hours (parallel processing)
**Expected cost:** ~$500-1000 (with cost filter)

### Scenario 3: AWS Batch Cloud Processing

```bash
# Configure AWS (one-time setup)
# - Create ECR repository
# - Push Docker image
# - Create Batch compute environment
# - Create job queue

# Run on AWS
nextflow run main.nf \
  -profile aws \
  --genes genes.txt \
  -bucket-dir s3://my-bucket/genephen-work \
  -with-tower  # Optional: Nextflow Tower monitoring
```

## Performance Tips

### Maximize Parallelism

```groovy
process {
    withName: EXTRACT_DATA {
        maxForks = 100  // High for cloud
    }
}
```

### Use Faster Storage

```bash
# Use fast local storage for work directory
nextflow run main.nf -w /tmp/nextflow-work
```

### Cache PubMed Results

```bash
# First run caches PubMed results
# Subsequent runs reuse if -resume
nextflow run main.nf -resume --llm_provider claude
```

## Integration with Databricks

After pipeline completes, upload to Databricks:

```bash
# Upload CSV files to DBFS
databricks fs cp results/final/combined_cohort_data.csv \
  dbfs:/data/genephen/cohort_data.csv

databricks fs cp results/final/combined_individual_data.csv \
  dbfs:/data/genephen/individual_data.csv
```

Then in Databricks notebook:

```python
# Read data
cohort_df = spark.read.csv("dbfs:/data/genephen/cohort_data.csv", header=True)
individual_df = spark.read.csv("dbfs:/data/genephen/individual_data.csv", header=True)

# Write to Delta Lake
cohort_df.write.format("delta").save("/mnt/delta/genephen_cohort")
individual_df.write.format("delta").save("/mnt/delta/genephen_individual")
```

## Further Reading

- [Nextflow Documentation](https://www.nextflow.io/docs/latest/)
- [Nextflow Patterns](https://nextflow-io.github.io/patterns/)
- [nf-core Best Practices](https://nf-co.re/docs/contributing/guidelines)

## Support

For issues with the pipeline:
1. Check `.nextflow.log` for errors
2. Review execution reports in `results/reports/`
3. Open issue on GitHub with logs
