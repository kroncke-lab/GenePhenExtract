# GenePhenExtract 🧬

**LLM-powered extraction of gene, variant, and phenotype data from PubMed literature**

GenePhenExtract automates the retrieval and interpretation of biomedical text to identify:

- **Genes and variants** (e.g., *KCNH2 p.Tyr54Asn*)
- **Carrier genotypes** (heterozygous, homozygous, compound het)
- **Phenotypic data** relevant to those variants (e.g., QT prolongation, arrhythmia, syncope)
- **Optional attributes** such as age, sex, treatment, and outcomes

It leverages large language models through schema-guided extraction (via [LangExtract](https://github.com/google/langextract)) to return structured JSON outputs suitable for:

- Variant curation and penetrance modeling
- Genotype–phenotype association studies
- Automated database population from case reports

## Getting Started

### Installation

```bash
pip install -e .
```

This will install the `genephenextract` command-line entry point onto your PATH. If you prefer
not to install the package, you can still run the tool in-place with:

```bash
python -m genephenextract --query "KCNH2" --mock
```

To use the LangExtract-backed extractor you will also need to install the optional dependency:

```bash
pip install -e .[langextract]
```

### Command-line usage

```bash
genephenextract --query "KCNH2 AND long QT" --max-results 5 --mock
```

The `--mock` flag runs the built-in mock extractor, which produces deterministic output without calling an external LLM. To use LangExtract instead, omit `--mock` and provide a valid API key:

```bash
genephenextract --query "KCNH2" --api-key $LANGEXTRACT_API_KEY --schema examples/schema.json
```

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
