# GenePhenExtract: Critical Gaps Analysis

## Core Mission
Extract phenotypes relevant to genotypes for individuals heterozygous for variants in user-inputted genes from PubMed literature.

## Critical Gaps

### 1. ❌ **Variant Normalization & Validation**

**Current State:**
- Extracts variants as free text (e.g., "KCNH2 p.Tyr54Asn")
- No validation that variant notation is correct
- No parsing of HGVS nomenclature
- Same variant in different notations treated as different

**Missing:**
```python
# Can't do this:
variant = parse_variant("KCNH2 c.2717C>T p.(Ser906Leu)")
# Returns: {gene: "KCNH2", cdna: "c.2717C>T", protein: "p.Ser906Leu", ...}

# Can't validate:
is_valid = validate_hgvs("KCNH2 p.Tyr54Asn")  # Not implemented

# Can't normalize:
normalize_variant("KCNH2 Tyr54Asn") → "KCNH2 p.Tyr54Asn"
```

**Impact:** Can't aggregate results for the same variant across papers.

---

### 2. ❌ **Gene-Centric Workflow**

**Current State:**
- Query PubMed with free text
- No structured gene input
- No automatic query generation for gene lists
- No tracking of which variants belong to which genes

**Missing:**
```python
# Can't do this:
results = extract_for_genes(
    genes=["KCNH2", "SCN5A", "KCNQ1"],
    genotypes=["heterozygous"],  # Filter for het carriers
    max_papers_per_gene=100
)

# Can't get gene-specific results:
kcnh2_results = results.filter(gene="KCNH2", genotype="heterozygous")
```

**Impact:** Inefficient for processing multiple genes; no gene-specific filtering.

---

### 3. ❌ **Variant-Phenotype Association Structure**

**Current State:**
- Extracts 1 variant and N phenotypes per paper
- No explicit link between specific variant and specific phenotype
- No tracking of which phenotypes apply to heterozygous vs homozygous

**Missing:**
```python
# Can't represent:
associations = [
    {
        "variant": "KCNH2 p.Ser906Leu",
        "genotype": "heterozygous",
        "phenotypes": ["prolonged QT interval", "syncope"],
        "penetrance": 0.85,  # 85% of het carriers have phenotype
        "n_carriers": 12,
        "n_affected": 10
    }
]

# Can't query:
het_phenotypes = get_phenotypes(variant="KCNH2 p.Ser906Leu", genotype="heterozygous")
hom_phenotypes = get_phenotypes(variant="KCNH2 p.Ser906Leu", genotype="homozygous")
```

**Impact:** Can't distinguish phenotypes by genotype; no penetrance information.

---

### 4. ❌ **Database Integration**

**Current State:**
- No integration with variant databases
- No validation against known variants
- No population frequency data
- No pathogenicity scores

**Missing:**
```python
# Can't do:
clinvar_info = lookup_clinvar("KCNH2 p.Ser906Leu")
# Returns: {pathogenicity: "Pathogenic", disease: "Long QT syndrome 2", ...}

gnomad_freq = lookup_gnomad("KCNH2 p.Ser906Leu")
# Returns: {AF: 0.00001, heterozygotes: 152, homozygotes: 0}

# Can't validate genes:
is_valid_gene = validate_gene("KCNH2")  # Check against HGNC
```

**Impact:** No quality control; no context for variants; can't filter known benign variants.

---

### 5. ❌ **Result Aggregation & Analysis**

**Current State:**
- Individual paper-level results
- No aggregation across papers
- No consensus building
- No confidence scoring

**Missing:**
```python
# Can't do:
summary = aggregate_results(results)
# Returns:
# {
#   "KCNH2 p.Ser906Leu": {
#     "papers": 15,
#     "heterozygous_carriers": 45,
#     "phenotypes": {
#       "prolonged QT interval": {count: 42, penetrance: 0.93},
#       "syncope": {count: 28, penetrance: 0.62},
#       "cardiac arrest": {count: 5, penetrance: 0.11}
#     }
#   }
# }

# Can't compare:
compare_genotypes(variant="KCNH2 p.Ser906Leu")
# Returns: het vs hom phenotype comparison
```

**Impact:** Can't answer "What are the main phenotypes for heterozygous carriers of this variant?"

---

### 6. ❌ **Query Optimization for Gene-Variant Discovery**

**Current State:**
- Manual PubMed query construction
- No automatic gene-to-query mapping
- No filtering by publication quality or recency

**Missing:**
```python
# Can't do:
query = build_gene_query(
    gene="KCNH2",
    include_terms=["variant", "mutation", "genotype", "phenotype"],
    exclude_terms=["animal model", "in vitro"],
    date_range=(2010, 2024),
    min_citations=5
)
# Returns optimized PubMed query
```

**Impact:** Retrieves too many irrelevant papers; wastes API costs.

---

### 7. ❌ **Genotype-Specific Extraction**

**Current State:**
- Extracts carrier_status as a field
- Doesn't filter or group by genotype
- Doesn't track compound heterozygotes properly

**Missing:**
```python
# Can't do:
het_only = extract_for_genotype(
    gene="KCNH2",
    genotype="heterozygous",  # Only extract het carriers
    min_carriers=5  # Only papers with ≥5 carriers
)

# Can't handle compound hets:
compound_het = {
    "variant1": "KCNH2 p.Ser906Leu",
    "variant2": "KCNH2 p.Arg534Cys",
    "genotype": "compound_heterozygous",
    "phenotypes": [...]
}
```

**Impact:** Can't focus on heterozygous-specific phenotypes; mixes all genotypes.

---

### 8. ❌ **Data Quality & Confidence Scoring**

**Current State:**
- All extracted data treated equally
- No confidence scores
- No validation of extracted information
- No tracking of extraction quality

**Missing:**
```python
# Can't do:
result = extract_with_confidence(text, pmid="123")
# Returns:
# {
#   "variant": "KCNH2 p.Ser906Leu",
#   "variant_confidence": 0.95,  # High confidence
#   "genotype": "heterozygous",
#   "genotype_confidence": 0.78,  # Medium confidence
#   "phenotypes": [
#     {"name": "prolonged QT", "confidence": 0.92},
#     {"name": "dizziness", "confidence": 0.45}  # Low confidence
#   ]
# }

# Can't filter by quality:
high_quality = results.filter(min_confidence=0.8)
```

**Impact:** No way to prioritize high-quality data; garbage in = garbage out.

---

### 9. ❌ **Pedigree & Family Information**

**Current State:**
- Extracts individual patient data
- No family/pedigree information
- No segregation analysis
- No inheritance pattern extraction

**Missing:**
```python
# Can't extract:
family = {
    "proband": {
        "variant": "KCNH2 p.Ser906Leu",
        "genotype": "heterozygous",
        "phenotypes": ["prolonged QT", "syncope"]
    },
    "family_members": [
        {"relation": "mother", "genotype": "heterozygous", "affected": True},
        {"relation": "father", "genotype": "wild-type", "affected": False},
        {"relation": "sibling", "genotype": "heterozygous", "affected": True}
    ],
    "inheritance": "autosomal_dominant"
}
```

**Impact:** Missing crucial information about variant segregation and inheritance.

---

### 10. ❌ **Structured Output for Clinical Use**

**Current State:**
- JSON output per paper
- No clinical report generation
- No variant database export
- No formats for downstream tools

**Missing:**
```python
# Can't generate:
clinical_report(variant="KCNH2 p.Ser906Leu", genotype="heterozygous")
# Returns formatted clinical report

# Can't export to:
export_to_vcf(results)  # VCF format for variant databases
export_to_clinvar_format(results)  # ClinVar submission format
export_to_csv_for_excel(results)  # For clinical spreadsheets
```

**Impact:** Results not immediately useful for clinical decision-making.

---

## Priority Fixes (Ranked by Impact)

### 🔴 **Critical (Needed for core mission)**

1. **Variant-Phenotype Association Model**
   - Link specific variants to specific phenotypes
   - Track genotype for each association
   - Extract penetrance data

2. **Gene-Centric Workflow**
   - Accept list of genes as input
   - Auto-generate PubMed queries
   - Filter results by gene

3. **Genotype Filtering**
   - Extract only heterozygous carriers (user requirement!)
   - Separate het vs hom phenotypes
   - Handle compound heterozygotes

### 🟡 **High Priority (Needed for quality)**

4. **Variant Normalization**
   - Parse HGVS nomenclature
   - Validate variant syntax
   - Deduplicate same variant, different notation

5. **Result Aggregation**
   - Aggregate across papers
   - Calculate penetrance
   - Build variant database

6. **Database Integration**
   - Validate against ClinVar
   - Check population frequencies (gnomAD)
   - Filter known benign variants

### 🟢 **Medium Priority (Nice to have)**

7. **Confidence Scoring**
   - Score extraction quality
   - Filter low-confidence results
   - Prioritize high-quality data

8. **Query Optimization**
   - Auto-generate optimal queries
   - Filter by publication quality
   - Exclude irrelevant papers

9. **Clinical Output Formats**
   - Generate reports
   - Export to clinical formats
   - Summary tables

### 🔵 **Low Priority (Future)**

10. **Pedigree Extraction**
    - Family information
    - Segregation analysis
    - Inheritance patterns

---

## Proposed Enhancements

### Phase 1: Core Variant-Genotype-Phenotype Model

```python
@dataclass
class VariantPhenotypeAssociation:
    """Link between a variant, genotype, and phenotype."""
    variant: str  # Normalized HGVS
    gene: str
    genotype: str  # heterozygous, homozygous, compound_heterozygous
    phenotype: PhenotypeObservation
    n_carriers: Optional[int] = None
    n_affected: Optional[int] = None
    penetrance: Optional[float] = None
    confidence: Optional[float] = None
    pmid: str
    evidence_text: Optional[str] = None  # Supporting quote from paper
```

### Phase 2: Gene-Centric Extraction

```python
class GeneCentricPipeline:
    """Extract phenotypes for variants in specific genes."""

    def extract_for_genes(
        self,
        genes: List[str],
        genotypes: Optional[List[str]] = None,
        max_papers_per_gene: int = 100,
        date_range: Optional[Tuple[int, int]] = None,
    ) -> GeneVariantDatabase:
        """Extract all variants and phenotypes for specified genes."""
        pass

    def filter_by_genotype(
        self,
        results: List[ExtractionResult],
        genotype: str
    ) -> List[ExtractionResult]:
        """Filter results to specific genotype."""
        pass
```

### Phase 3: Aggregation & Analysis

```python
class VariantAggregator:
    """Aggregate results across multiple papers."""

    def aggregate(
        self,
        results: List[ExtractionResult]
    ) -> Dict[str, VariantSummary]:
        """Group by variant, calculate penetrance."""
        pass

    def build_variant_database(
        self,
        results: List[ExtractionResult]
    ) -> pd.DataFrame:
        """Create structured variant-phenotype database."""
        pass
```

---

## Example Ideal Workflow

```python
from genephenextract import GeneCentricPipeline, ClaudeExtractor

# Step 1: Define genes of interest
genes = ["KCNH2", "SCN5A", "KCNQ1"]

# Step 2: Extract for heterozygous carriers only
pipeline = GeneCentricPipeline(extractor=ClaudeExtractor())

database = pipeline.extract_for_genes(
    genes=genes,
    genotypes=["heterozygous"],  # Focus on het carriers
    max_papers_per_gene=100,
    date_range=(2010, 2024),
    validate_variants=True,  # Check against ClinVar
    min_confidence=0.7
)

# Step 3: Get variant-specific phenotypes
kcnh2_variants = database.filter(gene="KCNH2")

for variant in kcnh2_variants:
    print(f"\n{variant.name} (heterozygous carriers):")
    print(f"  Papers: {variant.n_papers}")
    print(f"  Total carriers: {variant.n_carriers}")
    print(f"  Top phenotypes:")
    for pheno in variant.top_phenotypes(n=5):
        print(f"    - {pheno.name}: {pheno.penetrance:.1%} penetrance")

# Step 4: Export for clinical use
database.export_to_csv("variant_database.csv")
database.generate_clinical_report("KCNH2 p.Ser906Leu", "clinical_report.pdf")
```

---

## Conclusion

**Current state:** Good foundation for extracting structured data from papers.

**Missing for core mission:**
1. Variant-genotype-phenotype linking
2. Gene-centric workflow
3. Heterozygous-specific filtering
4. Result aggregation
5. Database integration

**Recommendation:** Implement Phases 1-2 immediately to make the tool useful for the stated purpose.
